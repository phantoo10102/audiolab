import logging
from pathlib import Path

import streamlit as st

# Imports
from utils.os_utils import fmt_time, open_folder
from actions import editor_actions
from actions import separation_actions

# [UPDATED IMPORTS] Import check_whisperx_job
from actions.whisperx_actions import run_whisperx_callback, check_whisperx_job
from ui.editor_components.export_section import render_export_section
from ui.editor_components.input_section import render_input_section
from ui.editor_components.processing_section import render_processing_section
from ui.waveform_view import render_waveform

logger = logging.getLogger(__name__)


# [FIX BUG-011] Fragment polling: Tự động refresh mỗi 2s để check job
# Đặt hàm này ở ngoài cùng (module level)
@st.fragment(run_every="2s")
def poll_background_jobs():
    """
    Check trạng thái của tất cả background jobs.
    """
    is_denoising = editor_actions.check_denoise_job()
    is_trimming = editor_actions.check_trim_job()
    is_separating = separation_actions.check_separation_job()
    is_whisperx = check_whisperx_job()

    # [NEW] Check Import
    is_importing = editor_actions.check_import_job()

    is_processing = (
        is_denoising or is_trimming or is_separating or is_whisperx or is_importing
    )

    if is_processing:
        st.caption("⏳ Background tasks running...")


def render_editor_view(manager):
    """
    Render toàn bộ giao diện Tab Editor.
    """
    # 1. Initial Check
    is_denoising = editor_actions.check_denoise_job()
    is_trimming = editor_actions.check_trim_job()
    is_separating = separation_actions.check_separation_job()
    is_whisperx = check_whisperx_job()
    is_importing = bool(st.session_state.get("import_job_id"))

    is_processing = (
        is_denoising or is_trimming or is_separating or is_whisperx or is_importing
    )

    # Lấy state từ tham số manager được truyền vào
    state = manager.state

    main_col, side_col = st.columns([3, 1], gap="large")

    with main_col:
        # --- A. IMPORT SECTION ---
        render_input_section(manager, state, is_processing)

        # --- B. EDITOR BODY ---
        if state.audio.is_loaded:
            # Atomic Check: Try to access file instead of checking existence
            try:
                # [CRITICAL FIX] Validate path before using it
                if not state.audio.current_path:
                    raise FileNotFoundError("Audio path is None")

                with open(state.audio.current_path, "rb"):
                    pass
            except (FileNotFoundError, OSError, TypeError):
                st.warning("⚠️ File missing or state reset. Please reload audio.")
                # Reset state safely to prevent further crashes
                manager.set_audio(None, None, 0.0)
                st.rerun()
                return

            # 1. WAVEFORM
            render_waveform(manager, state)

            # 2. CONTROLS
            if state.audio.duration is None:
                st.error("Audio duration is invalid.")
                return

            curr_dur = state.audio.duration

            def safe_clamp(val, max_v):
                v = float(val)
                if v < 0.0:
                    v = 0.0
                if v > max_v:
                    v = max_v
                return round(v, 4)

            # Sync inputs
            if "input_start" in st.session_state:
                st.session_state["input_start"] = safe_clamp(
                    st.session_state["input_start"], curr_dur
                )
            if "input_end" in st.session_state:
                st.session_state["input_end"] = safe_clamp(
                    st.session_state["input_end"], curr_dur
                )

            # Layout Controls
            with st.container(border=True):
                c_crop_opt, c_start, c_end, c_trim, c_undo, c_reset = st.columns(
                    [0.7, 0.4, 0.4, 0.5, 0.3, 0.3], vertical_alignment="bottom"
                )

                with c_crop_opt:
                    st.selectbox(
                        "After crop",
                        ["Stay on source", "Load cropped file"],
                        key="after_crop",
                        label_visibility="collapsed",
                        disabled=is_processing,
                    )

                with c_start:
                    st.number_input(
                        "Start (s)",
                        min_value=0.0,
                        max_value=curr_dur,
                        step=0.1,
                        format="%.2f",
                        key="input_start",
                        on_change=manager.on_input_change,
                        disabled=is_processing,
                    )

                with c_end:
                    st.number_input(
                        "End (s)",
                        min_value=0.0,
                        max_value=curr_dur,
                        step=0.1,
                        format="%.2f",
                        key="input_end",
                        on_change=manager.on_input_change,
                        disabled=is_processing,
                    )

                crop_disabled = (
                    (state.selection.start >= state.selection.end)
                    or ((state.selection.end - state.selection.start) < 0.1)
                    or is_processing
                )

                with c_trim:
                    st.button(
                        "✂️ CROP",
                        type="primary",
                        use_container_width=True,
                        disabled=crop_disabled,
                        on_click=editor_actions.crop_audio_callback,
                    )
                with c_undo:
                    st.button(
                        "↩️ Undo",
                        disabled=not st.session_state.history or is_processing,
                        use_container_width=True,
                        on_click=editor_actions.undo_audio_callback,
                    )
                with c_reset:
                    st.button(
                        "🔄 Reset",
                        disabled=is_processing,
                        use_container_width=True,
                        on_click=editor_actions.reset_audio_callback,
                    )

            # 3. WHISPERX OPTIONS (REFACTORED UI)
            with st.expander("WhisperX", expanded=True):
                # Load default model preference from Settings
                user_settings = st.session_state.get("user_settings", {})
                default_model_code = user_settings.get("models", {}).get(
                    "default_asr_model", "small"
                )

                # Mapping config value -> UI label
                model_map = {
                    "tiny": "Tiny",
                    "base": "base",
                    "small": "small",
                    "medium": "medium",
                    "large-v2": "large",
                    "large-v3": "large",
                    "turbo-v3": "Turbo V3",
                }
                default_label = model_map.get(default_model_code, "small")
                model_options = ["Tiny", "base", "small", "medium", "large", "Turbo V3"]

                vad_default = user_settings.get("whisperx", {}).get(
                    "vad_enabled", False
                )
                if "whisperx_vad" not in st.session_state:
                    st.session_state["whisperx_vad"] = "ON" if vad_default else "OFF"

                # Layout: 5 Settings + 1 Run Button
                c_lang, c_model, c_export, c_align, c_vad, c_btnRun = st.columns(
                    [0.18, 0.18, 0.18, 0.18, 0.12, 0.16],
                    vertical_alignment="bottom",
                )

                with c_lang:
                    from utils.whisperx_languages import (
                        LANGUAGE_LABELS,
                        LANGUAGE_OPTION_CODES,
                    )

                    st.selectbox(
                        "Language",
                        LANGUAGE_OPTION_CODES,
                        key="whisperx_language",
                        disabled=is_processing,
                        format_func=lambda code: LANGUAGE_LABELS.get(
                            code, code or "Auto"
                        ),
                    )
                with c_model:
                    # Code cũ...
                    model_options = [
                        "Tiny",
                        "base",
                        "small",
                        "medium",
                        "large",
                        "Turbo V3",
                    ]
                    st.selectbox(
                        "Model",
                        model_options,
                        key="whisperx_model",
                        disabled=is_processing,
                    )
                with c_export:
                    st.selectbox(
                        "Export Script",
                        ["Text", "SRT", "JSON"],
                        key="whisperx_export_format",
                        disabled=is_processing,
                    )
                with c_align:
                    st.selectbox(
                        "Alignment",
                        ["Đoạn", "Câu", "Từ"],
                        key="whisperx_alignment",
                        disabled=is_processing,
                    )
                with c_vad:
                    st.selectbox(
                        "VAD",
                        ["OFF", "ON"],
                        key="whisperx_vad",
                        disabled=is_processing,
                    )
                with c_btnRun:
                    st.button(
                        "🚀 Run Whisk",
                        type="primary",
                        use_container_width=True,
                        on_click=run_whisperx_callback,
                        disabled=is_processing or not state.audio.is_loaded,
                    )

            # 4. RESULT DISPLAY SECTION (Conditionally Rendered)
            if (
                "whisperx_result" in st.session_state
                and st.session_state.whisperx_result
            ):
                result = st.session_state.whisperx_result

                st.divider()
                title = f"Transcript Result - {result.get('input_file', 'Unknown')}"

                with st.expander(title, expanded=True):
                    export_format = result.get(
                        "export_format",
                        st.session_state.get("whisperx_export_format", "Text"),
                    )
                    preview_value = result.get("full_text", "")
                    if str(export_format).strip().lower() == "srt":
                        try:
                            from utils.srt_formatter import segments_to_srt

                            preview_value = segments_to_srt(
                                result.get("segments", []),
                                lang=result.get("language"),
                            )
                        except Exception:
                            preview_value = result.get("full_text", "")

                    # 1. Text Area
                    st.text_area(
                        "Nội dung phiên âm",
                        value=preview_value,
                        height=300,
                        disabled=True,
                    )

                    # 2. Open Folder Button
                    output_path = result.get("output_path", "")
                    if output_path:
                        folder = str(Path(output_path).parent)
                        if st.button(
                            "📂 Mở Thư Mục Output",
                            key="btn_open_output",
                            use_container_width=True,
                        ):
                            open_folder(folder)

            # Status Bar
            st.divider()
            msg = "✅ Ready"
            if is_denoising:
                msg = "⏳ Denoising..."
            if is_trimming:
                msg = "✂️ Trimming Silence..."
            if is_separating:
                msg = "🎸 Separating Stems..."
            if is_whisperx:
                msg = "📝 Transcribing (WhisperX)..."
            if is_importing:
                msg = "⬇️ Downloading from URL..."

            st.caption(
                f"Status: **{msg}** | Selection: {fmt_time(state.selection.start)} - {fmt_time(state.selection.end)}"
            )

        else:
            st.info("👆 Please upload audio or import from link.")

    # SIDEBAR
    with side_col:
        render_processing_section(state, is_processing)
        render_export_section(state)

    # Fragment polling
    poll_background_jobs()
