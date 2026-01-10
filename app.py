import sys
import os

from utils.console_noise import configure_console_noise

configure_console_noise()

import streamlit as st

# Setup Logging & Path
from utils.logging_config import setup_logging

setup_logging(level="INFO")

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from services.settings_service import SettingsManager
from ui.settings_view import render_settings_view
from services.audio_service import AudioProcessor
from state.session_manager import SessionManager, get_manager  # Updated imports
from ui.layout import init_styles, render_header
from ui.editor_view import render_editor_view
from ui.export_view import render_export_view
from utils.constants import TEMP_DIR, OUTPUT_DIR
from utils.file_manager import (
    migrate_legacy_data,
    cleanup_old_temp_files,
)  # [FIX BUG-019] Added cleanup import
from utils.shutdown import register_shutdown_handlers

# --- APP STARTUP ---
st.set_page_config(page_title="Audio Lab Ver3", layout="wide")
register_shutdown_handlers()

if "settings_manager" not in st.session_state:
    st.session_state.settings_manager = SettingsManager()
    # Load settings into session state for global access
    st.session_state.user_settings = st.session_state.settings_manager.load_settings()

# 1. Setup Data Structure & Migrate
if "migration_done" not in st.session_state:
    migrate_legacy_data()
    st.session_state["migration_done"] = True

# [FIX BUG-019] Auto Cleanup on Session Start
# Chỉ chạy 1 lần mỗi khi user F5 lại trang (Start new session)
if "cleanup_done" not in st.session_state:
    # Chạy cleanup trong background (thực tế function này chạy nhanh nên có thể để sync)
    cleanup_old_temp_files()
    st.session_state["cleanup_done"] = True

# 2. Init Styles & State
init_styles()
session = SessionManager()  # Singleton initialization (Đã bao gồm init history & state)

# --- INIT STATE & SERVICES ---
manager = get_manager()

# Init legacy session state keys (Processor, Settings)
# [FIX BUG-009] Removed duplicate history initialization.
# History initialization is now handled solely by SessionManager.__init__

# Processor có thể đã được init trong SessionManager, nhưng giữ lại check này
# để đảm bảo an toàn tuyệt đối nếu logic thay đổi sau này (Idempotent check).
if "processor" not in st.session_state:
    st.session_state.processor = AudioProcessor(output_dir=str(TEMP_DIR))

# Init UI toggles defaults
defaults = {
    "quick_transcribe": False,
    "sep_source_type": "Vocals",
    "after_crop": "Stay on source",
    "export_bitrate": "320k",
    "auto_fade": False,
    "normalize": False,
    "export_format": "mp3",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# --- MAIN RENDER ---
render_header("Audio Lab")
tabs = st.tabs(["🎵 Editor", "📊 Export History", "⚙️ Settings"])

with tabs[0]:
    # Pass session manager to editor view
    render_editor_view(session)

with tabs[1]:
    # [FIX] Truyền biến 'session' vào hàm render_export_view
    render_export_view(session)

with tabs[2]:
    render_settings_view()
