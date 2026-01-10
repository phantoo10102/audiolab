# -*- coding: utf-8 -*-
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from pydub import AudioSegment, silence

from utils.config_loader import config
from utils.file_manager import resolve_output_path
from utils.logging_config import get_session_id

# Setup logger chuẩn thay cho print
logger = logging.getLogger(__name__)

class TrimSilenceService:
    """Service cắt khoảng lặng (Windows-friendly, logging chuẩn)."""

    @staticmethod
    def trim_silence(
        input_path: str,
        output_path: Optional[str] = None,
        *,
        silence_thresh_db: float = -40.0,
        min_silence_len_ms: int = 400,
        keep_silence_ms: int = 150,
        mode: str = "both",
    ) -> Dict[str, Any]:

        session_id = get_session_id()

        logger.info(
            "Trim silence started",
            extra={
                "session_id": session_id,
                "operation": "trim_silence",
                "input_file": input_path,
                "params": {
                    "mode": mode,
                    "thresh_db": silence_thresh_db,
                    "min_len_ms": min_silence_len_ms,
                },
            },
        )

        # 1. Validation
        if not input_path or not os.path.exists(input_path):
            raise ValueError(f"Input path not found: {input_path}")

        file_name = Path(input_path).name
        if output_path is None:
            clean_name = f"trim_{Path(file_name).stem}.wav"
            output_dir = resolve_output_path(
                config.get("processing.trim.output_dir", None),
                "",
            )
            output_path = str(output_dir / clean_name)

        parent_dir = os.path.dirname(output_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        # 2. Load Audio
        try:
            audio = AudioSegment.from_file(input_path)
        except Exception as e:
            raise RuntimeError(f"Failed to load audio: {e}")

        original_len = len(audio)

        # 3. Detect Nonsilent
        logger.info(
            "Detecting silence",
            extra={
                "session_id": session_id,
                "operation": "trim_silence",
                "thresh_db": silence_thresh_db,
            },
        )

        nonsilent_ranges = silence.detect_nonsilent(
            audio, min_silence_len=min_silence_len_ms, silence_thresh=silence_thresh_db
        )

        # 4. Process Trimming Logic
        trim_start = 0
        trim_end = original_len
        is_trimmed = False

        if nonsilent_ranges:
            # Lấy vùng có âm thanh đầu tiên và cuối cùng
            first_sound_start = nonsilent_ranges[0][0]
            last_sound_end = nonsilent_ranges[-1][1]

            # Tính toán điểm cắt dựa trên mode
            if mode in ["start", "both"]:
                # Cắt đầu: Start = điểm có tiếng - padding
                trim_start = max(0, first_sound_start - keep_silence_ms)

            if mode in ["end", "both"]:
                # Cắt đuôi: End = điểm hết tiếng + padding
                trim_end = min(original_len, last_sound_end + keep_silence_ms)

            # Check logic nếu cắt xong mà start >= end (file rỗng hoặc lỗi)
            if trim_start >= trim_end:
                logger.warning(
                    "Trim calc resulted in empty file. Resetting to original.",
                    extra={"session_id": session_id, "operation": "trim_silence"},
                )
                trim_start = 0
                trim_end = original_len
            else:
                is_trimmed = (trim_start > 0) or (trim_end < original_len)
        else:
            logger.warning(
                "No sound detected (Full silence). Keeping original.",
                extra={"session_id": session_id, "operation": "trim_silence"},
            )

        # 5. Apply Slice
        trimmed_audio = audio[trim_start:trim_end]

        logger.info("Cutting from %dms to %dms", trim_start, trim_end)

        # 6. Export
        trimmed_audio.export(output_path, format="wav")
        logger.info(
            "Trim silence completed",
            extra={
                "session_id": session_id,
                "operation": "trim_silence",
                "output_file": output_path,
                "cut_range_ms": [trim_start, trim_end],
                "is_trimmed": is_trimmed,
            },
        )

        return {
            "output_path": output_path,
            "duration": len(trimmed_audio) / 1000.0,
            "sample_rate": audio.frame_rate,
            "channels": audio.channels,
            "trimmed_ms_start": trim_start,
            "trimmed_ms_end": trim_end,
            "is_trimmed": is_trimmed,
            "metadata": {"original_duration": original_len / 1000.0, "mode": mode},
        }
