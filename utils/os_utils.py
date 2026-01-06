import sys
import subprocess
import os
import streamlit as st


def fmt_time(seconds):
    if seconds is None:
        return "00:00.00"
    m, s = divmod(seconds, 60)
    return f"{int(m):02d}:{s:05.2f}"


def open_folder(path):
    try:
        if sys.platform == "win32":
            subprocess.Popen(f'explorer /select,"{path}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])
        st.toast("📂 Đã mở thư mục!")
    except Exception as e:
        st.error(f"Error opening folder: {e}")
