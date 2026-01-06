import os
import streamlit as st
import numpy as np  # [FIX] Import numpy để xử lý array
import logging
from typing import Dict, Any, Tuple, List, Optional
from pydub import AudioSegment
from utils.logging_config import get_session_id

logger = logging.getLogger(__name__)


class WaveformService:
    """
    Service quản lý việc truy xuất metadata và waveform data.
    Sử dụng st.cache_data để tránh IO/CPU bound operations khi rerender.
    """

    @staticmethod
    def get_file_signature(path: str) -> Tuple[str, int]:
        """
        Lấy 'chữ ký' của file để làm cache key.
        Return: (absolute_path, mtime_ns)
        """
        try:
            abs_path = os.path.abspath(path)
            stat = os.stat(abs_path)
            return abs_path, stat.st_mtime_ns
        except OSError:
            return "", 0

    @staticmethod
    @st.cache_data(show_spinner=False, max_entries=50)
    def compute_waveform_metadata(abs_path: str, mtime_ns: int) -> Dict[str, Any]:
        """
        Tính toán metadata nặng. Hàm này chỉ chạy lại khi file path hoặc mtime thay đổi.
        """
        session_id = get_session_id()
        logger.info(
            "Computing waveform metadata",
            extra={
                "session_id": session_id,
                "file_name": os.path.basename(abs_path),
                "operation": "waveform_metadata",
            },
        )
        try:
            audio = AudioSegment.from_file(abs_path)
            metadata = {
                "duration": len(audio) / 1000.0,
                "channels": audio.channels,
                "frame_rate": audio.frame_rate,
                "sample_width": audio.sample_width,
                "is_valid": True,
            }
            return metadata
        except Exception as e:
            # [THÊM] Log Error
            logger.error(
                "Metadata computation failed",
                extra={
                    "session_id": session_id,
                    "file_name": os.path.basename(abs_path),
                    "error": str(e),
                    "operation": "waveform_metadata",
                },
            )
            return {"is_valid": False, "error": str(e), "duration": 0.0}

    # [FIX BUG-012] Thêm hàm sinh dữ liệu Waveform có Caching
    @staticmethod
    @st.cache_data(show_spinner=False, ttl=3600, max_entries=20)
    def generate_waveform_data(
        abs_path: str, mtime_ns: int, n_samples: int = 1000
    ) -> Optional[np.ndarray]:
        """
        Sinh mảng dữ liệu biên độ (peaks) từ file audio để vẽ biểu đồ.
        Được cache dựa trên đường dẫn và mtime của file.

        Args:
            abs_path: Đường dẫn tuyệt đối tới file audio.
            mtime_ns: Thời gian sửa đổi file (dùng để invalidate cache).
            n_samples: Số lượng điểm mẫu muốn lấy (downsampling).

        Returns:
            np.ndarray: Mảng các giá trị biên độ (đã chuẩn hóa hoặc raw).
        """
        session_id = get_session_id()
        logger.info(
            "Generating waveform data",
            extra={
                "session_id": session_id,
                "file_name": os.path.basename(abs_path),
                "samples": n_samples,
                "operation": "waveform_generation",
            },
        )
        try:
            if not os.path.exists(abs_path):
                return None

            audio = AudioSegment.from_file(abs_path)

            # Convert sang mảng samples
            # Lưu ý: get_array_of_samples trả về array.array, cần convert sang numpy
            samples = np.array(audio.get_array_of_samples())

            # Xử lý Stereo -> Mono (nếu cần)
            if audio.channels == 2:
                samples = samples.reshape((-1, 2))
                # Lấy trung bình cộng hoặc chỉ lấy kênh trái để tăng tốc
                samples = samples.mean(axis=1)

            # Downsampling (Decimation)
            # Lấy mẫu cách đều để giảm kích thước dữ liệu xuống n_samples
            if len(samples) > n_samples:
                step = len(samples) // n_samples
                samples = samples[::step]

            # Chuẩn hóa về khoảng [-1, 1] nếu cần (tùy thuộc UI component)
            # Ở đây ta trả về raw values hoặc normalized tùy nhu cầu.
            # Ví dụ chuẩn hóa theo max int type:
            max_val = float(1 << (8 * audio.sample_width - 1))
            normalized_data = samples / max_val

            return normalized_data

        except Exception as e:
            # Fallback hoặc log lỗi
            return None

    @staticmethod
    def get_cached_payload(path: str) -> Dict[str, Any]:
        """Wrapper để UI gọi gọn gàng"""
        if not path or not os.path.exists(path):
            return {"is_valid": False}

        abs_path, mtime = WaveformService.get_file_signature(path)
        return WaveformService.compute_waveform_metadata(abs_path, mtime)
