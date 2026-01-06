import concurrent.futures
import uuid
import os
import logging
import time

# [FIX BUG-018] Config & Logging Imports
# Đảm bảo import config để lấy tham số hệ thống
from utils.config_loader import config
from utils.logging_config import get_session_id

# Setup Logger
logger = logging.getLogger(__name__)

# [FIX BUG-018] Load config values
# Lấy timeout từ config (mặc định 300s)
_DEFAULT_TIMEOUT = config.get("system.jobs.timeout_seconds", 300)

# [FIX BUG-007] Dynamic worker allocation calculation
# Lấy max_workers từ config (mặc định 4)
_config_max_workers = config.get("system.jobs.max_workers", 4)

# Tính toán số worker thực tế dựa trên CPU core, nhưng không vượt quá config
# Đây là dòng bị thiếu gây ra lỗi NameError của bạn
_max_workers = min(_config_max_workers, (os.cpu_count() or 1) + 1)

# Singleton Executor
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=_max_workers)

_FUTURES = {}  # {job_id: future}
_JOB_START_TIMES = {}  # {job_id: timestamp}
_JOB_PROGRESS = {}  # {job_id: int (0-100)}
COMPLETED_JOB_TTL = 120


def update_progress(job_id: str, percentage: int):
    """
    Cập nhật tiến độ của job. Hàm này được gọi từ bên trong Service thông qua callback.
    """
    safe_percent = max(0, min(100, int(percentage)))
    _JOB_PROGRESS[job_id] = safe_percent


def submit(fn, *args, **kwargs) -> str:
    """Gửi hàm vào chạy nền, trả về job_id"""
    session_id = get_session_id()
    job_id = str(uuid.uuid4())

    _JOB_START_TIMES[job_id] = time.time()
    _JOB_PROGRESS[job_id] = 0

    # [LOGGING] Job Submission
    logger.info(
        f"Job submitted: {fn.__name__}",
        extra={
            "session_id": session_id,
            "operation": "job_submit",
            "job_id": job_id,
            "target_function": fn.__name__,
        },
    )

    future = _EXECUTOR.submit(fn, *args, **kwargs)
    _FUTURES[job_id] = future

    return job_id


def get_job(job_id: str):
    """
    Lấy trạng thái job với cơ chế auto-cleanup tuyến tính.
    Flow: UNKNOWN -> RUNNING -> (TIMEOUT | COMPLETED | FAILED) -> EXPIRED
    """
    # --- CHECK 1: Job exists? ---
    if job_id not in _FUTURES:
        return {"status": "UNKNOWN"}

    future = _FUTURES[job_id]
    start_time = _JOB_START_TIMES.get(job_id, time.time())
    current_age = time.time() - start_time

    # --- CHECK 2: Still Running? ---
    if not future.done():
        # Sub-check: Did it timeout?
        if current_age > _DEFAULT_TIMEOUT:
            future.cancel()
            logger.warning(
                f"Job {job_id} timed out after {_DEFAULT_TIMEOUT}s",
                extra={"job_id": job_id, "operation": "job_timeout"},
            )
            # [FIX] Cleanup timeout jobs immediately
            clear_job(job_id)
            return {"status": "TIMEOUT", "error": "Job exceeded time limit"}

        # Still running normally
        progress = _JOB_PROGRESS.get(job_id, 0)
        return {"status": "RUNNING", "progress": progress}

    # --- From here: future.done() == True ---

    # --- CHECK 3: Result Expired? ---
    # TTL check chỉ áp dụng cho completed jobs (để UI kịp lấy kết quả)
    if current_age > COMPLETED_JOB_TTL:
        logger.debug(
            f"Auto-cleanup expired job result: {job_id}",
            extra={"job_id": job_id, "age_seconds": int(current_age)},
        )
        clear_job(job_id)
        return {
            "status": "EXPIRED",
            "error": f"Job result expired after {COMPLETED_JOB_TTL}s",
        }

    # --- CHECK 4: Get Result (Success or Failure) ---
    try:
        result = future.result()
        # Success - return result WITHOUT cleanup (UI needs to read it first)
        return {"status": "COMPLETED", "result": result, "progress": 100}

    except concurrent.futures.CancelledError:
        # Job bị cancel
        clear_job(job_id)
        return {"status": "FAILED", "error": "Job was cancelled"}

    except Exception as e:
        # Job execution failed
        logger.error(
            f"Job execution failed: {job_id}",
            extra={"job_id": job_id, "error": str(e)},
            exc_info=True,
        )
        # [FIX BUG #8] Cleanup failed jobs immediately to prevent leak
        clear_job(job_id)
        return {"status": "FAILED", "error": str(e)}


def clear_job(job_id: str):
    """Xóa job khỏi bộ nhớ sau khi xong"""
    if job_id in _FUTURES:
        del _FUTURES[job_id]
    if job_id in _JOB_START_TIMES:
        del _JOB_START_TIMES[job_id]
    if job_id in _JOB_PROGRESS:
        del _JOB_PROGRESS[job_id]
