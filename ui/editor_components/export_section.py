import streamlit as st

from utils.config_loader import config
from utils.constants import DATA_OUTPUT_DIR
from utils.os_utils import open_folder


def render_export_section(state):
    format_opts = config.get("audio.export.format_options", ["mp3", "wav", "flac"])
    bitrate_opts = config.get("audio.export.bitrate_options", ["128k", "320k"])

    with st.container(border=True):
        st.markdown("#### 💾 Export")
        st.selectbox(
            "Format",
            format_opts,  # Used config options
            key="export_format",
            disabled=not state.audio.is_loaded,
        )
        if st.session_state.get("export_format") == "mp3":
            st.selectbox("Bitrate", bitrate_opts, key="export_bitrate")

        st.button(
            "📂 Open Output",
            use_container_width=True,
            on_click=lambda: open_folder(str(DATA_OUTPUT_DIR.absolute())),
        )
