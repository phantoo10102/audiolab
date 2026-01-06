import streamlit as st
import os
import math
from typing import Optional

# Import Models
from .models import AppState, HistoryEntry

# Import Utils
from utils.file_manager import copy_to_history, cleanup_old_history, MAX_HISTORY_STEPS
from utils.constants import TEMP_DIR

# Import Service
from services.audio_service import AudioProcessor


class SessionManager:
    def __init__(self):
        """Khởi tạo SessionManager và load state từ st.session_state."""

        # 1. Init History Stack (SSOT Location)
        # [FIX BUG-009] Chỉ khởi tạo history tại đây để tránh trùng lặp code với app.py
        if "history" not in st.session_state:
            st.session_state.history = []

        # 2. Init App State wrapper
        if "app_state" not in st.session_state:
            st.session_state.app_state = AppState()

        # 3. Init Processor (Legacy/Shared Service)
        # Khởi tạo AudioProcessor tại đây để đảm bảo nó luôn sẵn sàng cho Services khác
        if "processor" not in st.session_state:
            # Import lazy hoặc đảm bảo TEMP_DIR đã import từ utils.constants
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
            st.session_state.processor = AudioProcessor(output_dir=str(TEMP_DIR))

        # 4. Binding (Liên kết biến local với session state)
        self.state: AppState = st.session_state.app_state

        # 5. Init UI keys (Sync binding cho Widget)
        if "input_start" not in st.session_state:
            st.session_state.input_start = 0.0
        if "input_end" not in st.session_state:
            st.session_state.input_end = 0.0

    # --- CORE LOGIC ---

    def set_selection(self, start: float, end: float, source: str):
        """
        Hàm DUY NHẤT để set selection.
        Đã hợp nhất logic validate và sync UI.
        """
        duration = self.state.audio.duration

        # 1. Validate & Clamp
        start = max(0.0, min(start, duration))
        end = max(0.0, min(end, duration))
        if end < start:
            end = start

        # 2. Update Model (Data)
        self.state.selection.start = start
        self.state.selection.end = end
        self.state.selection.source = source
        self.state.selection.version += 1

        # 3. Sync UI Widgets (Quan trọng: Round để tránh lỗi precision)
        # Làm tròn 4 chữ số thập phân để an toàn cho so sánh float
        if "input_start" in st.session_state:
            st.session_state.input_start = round(start, 4)
        if "input_end" in st.session_state:
            st.session_state.input_end = round(end, 4)

    def set_audio(
        self, path: str, original_path: str, duration: float, source_url: str = None
    ):
        """Cập nhật audio mới và reset state."""
        # 1. Cập nhật thông tin cơ bản
        self.state.audio.current_path = path
        self.state.audio.original_path = original_path
        self.state.audio.duration = duration
        self.state.audio.source_url = source_url

        self.state.audio.is_loaded = True
        self.state.audio.version += 1

        # 2. Tính toán Selection mặc định (15%)
        if duration and duration > 0:
            default_end = min(duration, max(duration * 0.15, 0.5))
        else:
            default_end = 0.0

        # 3. Reset State & UI
        # Gọi set_selection để tận dụng logic clamp/round ở trên
        self.set_selection(0.0, default_end, source="init")

        # [FIX BUG-005] Conditional History Clearing
        # Logic: Nếu 'path' hiện tại trùng với 'original_path', nghĩa là ta đang load file gốc
        # (Import mới hoặc Reset), lúc này nên xóa History để bắt đầu session mới.
        # Ngược lại, nếu 'path' khác 'original_path' (vd: file crop, denoise, stem),
        # nghĩa là đây là bản phái sinh, ta CẦN GIỮ lại History để user có thể Undo.
        if path == original_path:
            st.session_state.history = []

    # --- HISTORY LOGIC ---

    def push_history(self, current_path: str, original_path: str, duration: float):
        if not current_path:
            return

        history_path = copy_to_history(current_path)
        if not history_path:
            return

        entry = HistoryEntry(
            path=history_path,
            original_path=original_path,
            duration=duration,
            view_start=self.state.selection.start,
            view_end=self.state.selection.end,
        )

        st.session_state.history.append(entry)
        if len(st.session_state.history) > MAX_HISTORY_STEPS:
            st.session_state.history.pop(0)

        # [FIX BUG-013] Optimized I/O Cleanup Strategy
        # Sử dụng Counter để chỉ chạy cleanup mỗi 10 lần push.
        # Chiến lược này tốt hơn check len() vì tránh việc scan ổ cứng liên tục
        # khi history đã đầy (len == MAX).
        if "history_push_count" not in st.session_state:
            st.session_state.history_push_count = 0

        st.session_state.history_push_count += 1

        # Chỉ dọn dẹp orphan files mỗi 10 thao tác sửa đổi
        if st.session_state.history_push_count % 10 == 0:
            cleanup_old_history(st.session_state.history)

    def pop_history(self) -> Optional[HistoryEntry]:
        if not st.session_state.history:
            return None
        return st.session_state.history.pop()

    # --- CALLBACKS & SYNC ---

    def on_input_change(self):
        new_start = st.session_state.get("input_start", 0.0)
        new_end = st.session_state.get("input_end", 0.0)
        self.set_selection(new_start, new_end, source="input")

    def sync_from_waveform(self, component_value: dict):
        if not component_value:
            return

        apply_id = component_value.get("apply_id", 0)
        start = component_value.get("start", 0.0)
        end = component_value.get("end", 0.0)

        last_id = getattr(self.state, "last_waveform_id", 0)

        if apply_id != last_id:
            self.state.last_waveform_id = apply_id

            # Gọi set_selection để đồng bộ chuẩn
            self.set_selection(start, end, source="waveform")

            st.rerun()


def get_manager() -> SessionManager:
    if "session_manager_instance" not in st.session_state:
        st.session_state.session_manager_instance = SessionManager()
    return st.session_state.session_manager_instance
