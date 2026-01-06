import streamlit as st
import os
import hashlib  # <--- [FIX] Đã thêm import hashlib để sửa lỗi NameError
from components.audio_waveform import audio_waveform
from services.waveform_service import WaveformService


def render_waveform(manager, state):
    current_path = state.audio.current_path

    # [CHECK] Cache logic giữ nguyên
    payload = WaveformService.get_cached_payload(current_path)
    if not payload.get("is_valid", False):
        st.error("⚠️ Audio file not found or invalid.")
        return

    # [FIX] Tạo Key Động: Path + Audio Version
    # Khi set_audio được gọi -> version tăng -> key đổi -> Component Remount
    unique_key = f"{current_path}_v{state.audio.version}"
    safe_key = hashlib.md5(unique_key.encode()).hexdigest()

    # Render Component
    waveform_data = audio_waveform(
        audio_file=current_path,
        height=320,
        key=f"wf_{safe_key}",  # Key thay đổi sẽ ép Streamlit vẽ lại từ đầu
        start_time=state.selection.start,
        end_time=state.selection.end,
    )

    manager.sync_from_waveform(waveform_data)
