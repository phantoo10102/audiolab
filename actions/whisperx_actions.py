import streamlit as st
import logging
import json
import os
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Imports
from jobs import job_runner
from services.whisperx_service import whisperx_service
from state.session_manager import get_manager
from utils.constants import DATA_OUTPUT_DIR
from utils.logging_config import get_session_id
from actions.job_utils import check_background_job, ensure_audio_available

logger = logging.getLogger(__name__)


# --- WORKER FUNCTION (Chạy trong Background Thread) ---
def _run_whisperx_task(
    input_path: str,
    model_name: str,
    language: str,
    batch_size: int,
    session_id: str,
    export_format: str = "Text",
    alignment_level: str = "Đoạn", 
    models_dir: str | None = None, 
    vad_enabled: bool = False,
) -> Dict[str, Any]:
    """
    Hàm thực thi logic nặng của WhisperX.
    Được gọi bởi JobRunner, KHÔNG truy cập st.session_state ở đây.
    """
    pipeline_start = time.time()

    resolved_models_dir = whisperx_service._resolve_models_dir(models_dir, session_id)
    logger.info(
        "Using WhisperX models_dir",
        extra={
            "session_id": session_id,
            "operation": "whisperx_models_dir",
            "models_dir": str(resolved_models_dir),
        },
    )

    # 1. Load Model
    load_res = whisperx_service.load_model(
        model_name=model_name,
        models_dir=resolved_models_dir,
    )
    if not load_res["success"]:
        raise RuntimeError(f"Load Model Failed: {load_res['message']}")

    # 2. Transcribe
    from utils.whisperx_languages import normalize_whisper_language

    normalized_language = normalize_whisper_language(language)
    trans_res = whisperx_service.transcribe(
        audio_path=input_path,
        language=normalized_language,
        batch_size=batch_size,
        vad_filter=vad_enabled,
    )
    if not trans_res["success"]:
        raise RuntimeError(f"Transcription Failed: {trans_res['message']}")

    segments = trans_res["segments"]
    full_text = "\n".join([seg["text"].strip() for seg in segments])

    from utils.whisperx_alignment import apply_alignment

    aligned_segments = apply_alignment(segments, alignment_level)

    # 3. Save to File
    now = datetime.now()
    date_folder = now.strftime("%d-%m-%Y")
    timestamp = now.strftime("%d%m%Y_%H%M%S")

    original_name = Path(input_path).stem.replace(" ", "_")
    safe_format = (export_format or "Text").strip().lower()
    if safe_format == "srt":
        filename = f"SRT_{original_name}_{timestamp}.srt"
    elif safe_format == "json":
        filename = f"JSON_{original_name}_{timestamp}.json"
    else:
        filename = f"TXT_{original_name}_{timestamp}.txt"

    output_dir = DATA_OUTPUT_DIR / date_folder / "whisperx"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    try:
        if safe_format == "srt":
            from utils.srt_formatter import segments_to_srt

            srt_text = segments_to_srt(aligned_segments, lang=normalized_language)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(srt_text)
        elif safe_format == "json":
            payload = {
                "segments": aligned_segments,
                "language": language,
                "input_file": original_name,
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(full_text)

        logger.info(
            "WhisperX file exported",
            extra={
                "session_id": session_id,
                "operation": "whisperx_export",
                "path": str(output_path),
            },
        )
    except Exception as e:
        logger.error("Export failed", extra={"error": str(e), "session_id": session_id})
        # Vẫn trả về kết quả text dù save file lỗi
        output_path = None

    total_elapsed = time.time() - pipeline_start

    # Kết quả trả về cho Main Thread
    return {
        "segments": aligned_segments,
        "language": language,
        "input_file": original_name,
        "output_path": str(output_path) if output_path else None,
        "full_text": full_text,
        "total_duration": total_elapsed,
        "export_format": export_format,
        "alignment_level": alignment_level, 
        "models_dir": models_dir, 
    }


# --- UI CALLBACK (Main Thread) ---
def run_whisperx_callback():
    """
    Callback nút 'Run Whisk'.
    Chỉ submit job và setup state, KHÔNG chạy xử lý nặng.
    """
    manager = get_manager()
    state = manager.state
    session_id = get_session_id()

    # 1. Validation
    if not state.audio.is_loaded or not state.audio.current_path:
        st.error("⚠️ Vui lòng import file audio trước khi chạy.")
        return

    if not ensure_audio_available(
        state,
        manager=manager,
        missing_message="❌ File audio gốc không tồn tại.",
    ):
        return

    # 2. Configuration (Lấy từ UI state nếu có, hiện tại dùng default/hardcode cho Phase 1)
    # Trong thực tế, bạn sẽ lấy từ st.session_state.whisperx_model, v.v.
    target_model = st.session_state.get("whisperx_model", "small").lower()
    if target_model == "turbo v3":
        target_model = "large-v3-turbo"  # Mapping ví dụ

    from utils.whisperx_languages import normalize_whisper_language

    target_lang = normalize_whisper_language(
        st.session_state.get("whisperx_language")
    )

    batch_size = 16
    export_format = st.session_state.get("whisperx_export_format", "Text")
    alignment_level = st.session_state.get("whisperx_alignment", "Đoạn") 
    settings = st.session_state.get("user_settings", {})
    models_dir = settings.get("whisperx", {}).get("models_dir") 
    vad_enabled = st.session_state.get("whisperx_vad", "OFF") == "ON"

    # 3. Submit Job
    job_id = job_runner.submit(
        _run_whisperx_task,
        input_path=state.audio.current_path,
        model_name=target_model,
        language=target_lang,
        batch_size=batch_size,
        session_id=session_id,
        export_format=export_format,
        alignment_level=alignment_level, 
        models_dir=models_dir, 
        vad_enabled=vad_enabled,
    )

    # 4. Update UI State
    st.session_state["whisperx_job_id"] = job_id

    # 5. Logging & Toast
    logger.info(
        "WhisperX job submitted",
        extra={
            "session_id": session_id,
            "operation": "whisperx_submit",
            "job_id": job_id,
        },
    )
    st.toast("🚀 WhisperX started in background...")


# --- POLLING FUNCTION (Called by Fragment) ---
def check_whisperx_job():
    """
    Kiểm tra trạng thái job WhisperX.
    Return: True nếu đang chạy, False nếu đã xong/lỗi/không có job.
    """
    job_id = st.session_state.get("whisperx_job_id")

    def _on_completed(info):
        result = info["result"]

        # Update Session State với kết quả
        st.session_state.whisperx_result = result

        st.toast(f"✅ WhisperX Complete ({result['total_duration']:.1f}s)!")

        # Force Rerun để hiển thị kết quả ngay lập tức
        st.rerun()

    def _on_failed(info):
        error_msg = info.get("error")
        st.error(f"❌ WhisperX Failed: {error_msg}")
        st.rerun()

    def _on_terminal(info):
        status = info.get("status")
        error_msg = info.get("error")
        if status == "CANCELLED":
            st.error("⚠️ WhisperX Cancelled.")
        elif status == "TIMEOUT":
            st.error(f"⏱️ WhisperX Timed Out: {error_msg}")
        elif status == "EXPIRED":
            st.error(f"⚠️ WhisperX Result Expired: {error_msg}")
        else:
            st.error("⚠️ WhisperX Job Not Found.")
        st.rerun()

    return check_background_job(
        job_id,
        "whisperx_job_id",
        on_completed=_on_completed,
        on_failed=_on_failed,
        on_terminal=_on_terminal,
    )
