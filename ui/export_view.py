import streamlit as st
from pathlib import Path
from utils.constants import OUTPUT_DIR
from utils.os_utils import open_folder
from ui.layout import render_header


# [ADR-011] Fragment auto-refresh for file list
@st.fragment(run_every="2s")
def render_output_files_panel():
    """
    Displays the list of exported files and refreshes automatically.
    """
    st.markdown("#### Output Files")
    out_dir = Path(OUTPUT_DIR)

    # Safe check if directory exists
    if not out_dir.exists():
        st.caption("Output directory not created yet.")
        return

    files = sorted(
        [p for p in out_dir.glob("*") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not files:
        st.caption("No exported files yet.")
        return

    for p in files[:25]:
        cols = st.columns([3, 1], vertical_alignment="center")
        cols[0].caption(f"📄 {p.name}")
        try:
            # Use mtime in key to force re-render if file changes
            cols[1].download_button(
                "Download",
                data=p.read_bytes(),
                file_name=p.name,
                mime="audio/mpeg",
                use_container_width=True,
                key=f"dl_{p.name}_{p.stat().st_mtime}",
            )
        except Exception:
            pass


def render_export_view(session):
    render_header("Export & History")
    c1, c2 = st.columns([2, 1], gap="large")

    with c1:
        with st.container(border=True):
            # [ADR-011] Call the polling fragment
            render_output_files_panel()

    with c2:
        with st.container(border=True):
            st.markdown("#### Utilities")
            st.button(
                "📂 Open Output Folder",
                key="btn_open_out_exp",
                use_container_width=True,
                on_click=lambda: open_folder(str(Path(OUTPUT_DIR).absolute())),
            )
