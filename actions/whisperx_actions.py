import streamlit as st
import logging
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

logger = logging.getLogger(__name__)


# --- WORKER FUNCTION (Chạy trong Background Thread) ---
def _run_whisperx_task(
    input_path: str, model_name: str, language: str, batch_size: int, session_id: str
) -> Dict[str, Any]:
    """
    Hàm thực thi logic nặng của WhisperX.
    Được gọi bởi JobRunner, KHÔNG truy cập st.session_state ở đây.
    """
    pipeline_start = time.time()

    # 1. Load Model
    load_res = whisperx_service.load_model(model_name=model_name)
    if not load_res["success"]:
        raise RuntimeError(f"Load Model Failed: {load_res['message']}")

    # 2. Transcribe
    trans_res = whisperx_service.transcribe(
        audio_path=input_path, language=language, batch_size=batch_size
    )
    if not trans_res["success"]:
        raise RuntimeError(f"Transcription Failed: {trans_res['message']}")

    segments = trans_res["segments"]
    full_text = "\n".join([seg["text"].strip() for seg in segments])

    # 3. Save to File
    now = datetime.now()
    date_folder = now.strftime("%d-%m-%Y")
    timestamp = now.strftime("%d%m%Y_%H%M%S")

    original_name = Path(input_path).stem.replace(" ", "_")
    filename = f"TXT_{original_name}_{timestamp}.txt"

    output_dir = DATA_OUTPUT_DIR / date_folder / "whisperx"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    try:
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
        "segments": segments,
        "language": language,
        "input_file": original_name,
        "output_path": str(output_path) if output_path else None,
        "full_text": full_text,
        "total_duration": total_elapsed,
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

    if not os.path.exists(state.audio.current_path):
        st.error("❌ File audio gốc không tồn tại.")
        return

    # 2. Configuration (Lấy từ UI state nếu có, hiện tại dùng default/hardcode cho Phase 1)
    # Trong thực tế, bạn sẽ lấy từ st.session_state.whisperx_model, v.v.
    target_model = st.session_state.get("whisperx_model", "small").lower()
    if target_model == "turbo v3":
        target_model = "large-v3-turbo"  # Mapping ví dụ

    target_lang = st.session_state.get("whisperx_language", "en")
    if target_lang == "Auto":
        target_lang = None
    elif target_lang == "Anh":
        target_lang = "en"
    elif target_lang == "Việt":
        target_lang = "vi"

    batch_size = 16

    # 3. Submit Job
    job_id = job_runner.submit(
        _run_whisperx_task,
        input_path=state.audio.current_path,
        model_name=target_model,
        language=target_lang,
        batch_size=batch_size,
        session_id=session_id,
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
    if not job_id:
        return False

    info = job_runner.get_job(job_id)
    status = info.get("status")

    if status == "RUNNING":
        return True

    elif status == "COMPLETED":
        result = info["result"]

        # Update Session State với kết quả
        st.session_state.whisperx_result = result

        # Cleanup Job
        job_runner.clear_job(job_id)
        if "whisperx_job_id" in st.session_state:
            del st.session_state["whisperx_job_id"]

        st.toast(f"✅ WhisperX Complete ({result['total_duration']:.1f}s)!")

        # Force Rerun để hiển thị kết quả ngay lập tức
        st.rerun()
        return False

    elif status == "FAILED":
        error_msg = info.get("error")
        st.error(f"❌ WhisperX Failed: {error_msg}")

        # Cleanup
        job_runner.clear_job(job_id)
        if "whisperx_job_id" in st.session_state:
            del st.session_state["whisperx_job_id"]

        return False

    return False
