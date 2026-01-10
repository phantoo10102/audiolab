import logging
from pathlib import Path

import streamlit as st

from actions import editor_actions
from utils.constants import DATA_TEMP_DIR

logger = logging.getLogger(__name__)


def render_input_section(manager, state, is_processing):
    with st.expander(
        "📥 Import Audio / Change Source", expanded=(not state.audio.is_loaded)
    ):
        uploaded_file = st.file_uploader(
            "Audio File",
            type=["mp3", "wav", "ogg", "m4a", "flac"],
            label_visibility="collapsed",
            disabled=is_processing,
        )

        # Import Logic (Local)
        if uploaded_file and not is_processing:
            # Check duplicate
            is_new_file = True
            if (
                state.audio.original_path
                and Path(state.audio.original_path).name
                == f"original_{uploaded_file.name}"
            ):
                is_new_file = False

            if is_new_file:
                try:
                    processor = st.session_state.processor

                    # Save file to temp
                    temp_path = DATA_TEMP_DIR / f"original_{uploaded_file.name}"
                    uploaded_file.seek(0)
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.read())

                    # Load & Update State
                    str_path = str(temp_path)
                    duration = processor.load_audio(str_path)

                    # Gọi set_audio với path == original_path -> History sẽ được clear
                    manager.set_audio(
                        path=str_path, original_path=str_path, duration=duration
                    )
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Error during upload: {e}")

        # Import Logic (Link)
        st.divider()
        col_link_in, col_link_btn = st.columns([3, 1])
        with col_link_in:
            link_url = st.text_input(
                "Or paste YouTube/TikTok URL",
                placeholder="https://...",
                label_visibility="collapsed",
                disabled=is_processing,  # [Auto disabled when running]
            )
        with col_link_btn:
            if st.button(
                "Download Link", disabled=is_processing, use_container_width=True
            ):
                editor_actions.handle_import_from_link(link_url)

        # Info Display
        if state.audio.is_loaded:
            st.divider()
            try:
                audio_info = st.session_state.processor.get_audio_info() or {}
            except Exception as e:
                logger.warning(
                    "Failed to read audio info",
                    extra={"error": str(e), "operation": "audio_info"},
                    exc_info=True,
                )
                audio_info = {}

            c1, c2, c3, c4 = st.columns(4)
            file_name = (
                Path(state.audio.current_path).name
                if state.audio.current_path
                else "N/A"
            )
            c1.caption(f"File: **{file_name}**")
            c2.caption(f"Rate: **{audio_info.get('sample_rate', 'N/A')}Hz**")
            c3.caption(f"Bitrate: **{audio_info.get('bitrate', 'N/A')}**")
            c4.caption(f"Duration: **{state.audio.duration:.2f}s**")
