import os

import streamlit as st

from actions.job_utils import check_background_job
from jobs import job_runner
from services.separation_service import SeparationService
from state.schemas import SeparationResult, SeparationStem
from state.session_manager import get_manager


def get_state_objects():
    manager = get_manager()
    return manager, manager.state


# --- CALLBACKS ---


def start_separation_callback():
    manager, state = get_state_objects()

    if not state.audio.is_loaded:
        st.error("No audio loaded.")
        return

    # Clear old results
    if "separation_result" in st.session_state:
        del st.session_state["separation_result"]

    # Submit Job
    job_id = job_runner.submit(
        SeparationService.run_separation,
        input_path=state.audio.current_path,
        job_id=f"sep_{int(os.path.getmtime(state.audio.current_path))}",  # Unique based on file
        model_name="htdemucs",
    )

    st.session_state["sep_job_id"] = job_id
    st.toast("🚀 AI Separation started in background...")
    # Trigger poll
    # st.rerun()


def load_selected_stem_callback():
    """
    Callback cho nút 'Load Stem'.
    Lấy stem đang chọn ở dropdown và load vào editor.
    """
    manager, state = get_state_objects()

    # 1. Lấy kết quả và lựa chọn hiện tại
    result = st.session_state.get("separation_result")
    selected_name = st.session_state.get("sep_selected_stem_name")  # Key của dropdown

    if not result or not selected_name:
        st.warning("Please select a stem first.")
        return

    # 2. Tìm object Stem tương ứng với tên đã chọn
    target_stem = next((s for s in result.stems if s.name == selected_name), None)

    if not target_stem or not os.path.exists(target_stem.path):
        st.error(f"Stem file not found: {selected_name}")
        return

    # 3. Push History (SSOT)
    manager.push_history(
        current_path=state.audio.current_path,
        original_path=state.audio.original_path,
        duration=state.audio.duration,
    )

    # 4. Load Audio mới
    processor = st.session_state.processor
    try:
        # Load file stem (thường là wav nên rất nhanh)
        processor.load_audio(target_stem.path)
        new_duration = processor.duration

        # 5. Update State & Restore Selection
        # Logic clamp selection: Nếu vùng chọn cũ vượt quá độ dài stem mới -> reset hoặc co lại
        old_start = state.selection.start
        old_end = state.selection.end

        # Nếu selection hợp lệ với file mới thì giữ nguyên, không thì reset
        if old_end <= new_duration:
            pass  # Giữ nguyên start/end
        elif old_start < new_duration:
            # Co end lại
            # [FIXED] Thêm source="stem_clamp" để khớp với chữ ký set_selection
            manager.set_selection(old_start, new_duration, source="stem_clamp")
        else:
            # Reset toàn bộ nếu start vượt quá duration
            # [FIXED] Thêm source="stem_reset"
            manager.set_selection(0.0, new_duration, source="stem_reset")

        manager.set_audio(
            path=target_stem.path,
            original_path=state.audio.original_path,  # Giữ gốc để user biết context
            duration=new_duration,
        )

        st.toast(f"✅ Loaded stem: {selected_name.capitalize()}")

    except Exception as e:
        st.error(f"Failed to load stem: {e}")


# --- POLLING ---


def check_separation_job():
    job_id = st.session_state.get("sep_job_id")

    def _on_completed(info):
        result_dict = info["result"]

        # Convert Dict back to Schema Object
        stems_obj = [SeparationStem(**s) for s in result_dict["stems"]]
        res_obj = SeparationResult(
            model_name=result_dict["model_name"],
            input_path=result_dict["input_path"],
            output_dir=result_dict["output_dir"],
            stems=stems_obj,
        )

        st.session_state["separation_result"] = res_obj

        st.toast("✅ Separation Complete!")
        st.rerun()

    def _on_failed(info):
        error = info.get("error")
        st.error(f"❌ Separation Failed: {error}")

    return check_background_job(
        job_id,
        "sep_job_id",
        on_completed=_on_completed,
        on_failed=_on_failed,
    )
