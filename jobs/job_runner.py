import concurrent.futures
import uuid
import os
import logging
import time
import threading
import inspect

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
_JOB_CANCEL_EVENTS = {}  # {job_id: threading.Event}
_JOB_STATUS = {}  # {job_id: str}
_JOB_LOCK = threading.Lock()
COMPLETED_JOB_TTL = 120


def update_progress(job_id: str, percentage: int):
    """
    Cập nhật tiến độ của job. Hàm này được gọi từ bên trong Service thông qua callback.
    """
    safe_percent = max(0, min(100, int(percentage)))
    with _JOB_LOCK:
        _JOB_PROGRESS[job_id] = safe_percent


def _supports_cancel_event(fn) -> bool:
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    for param in sig.parameters.values():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True
    return "cancel_event" in sig.parameters


def _run_with_cancel(fn, args, kwargs, cancel_event):
    call_kwargs = dict(kwargs)
    if _supports_cancel_event(fn):
        call_kwargs.setdefault("cancel_event", cancel_event)
    return fn(*args, **call_kwargs)


def request_cancel(job_id: str, reason: str = "CANCELLED"):
    with _JOB_LOCK:
        cancel_event = _JOB_CANCEL_EVENTS.get(job_id)
        future = _FUTURES.get(job_id)
        _JOB_STATUS[job_id] = reason
    if cancel_event:
        cancel_event.set()
    if future:
        future.cancel()


def submit(fn, *args, **kwargs) -> str:
    """Gửi hàm vào chạy nền, trả về job_id"""
    session_id = get_session_id()
    job_id = str(uuid.uuid4())
    cancel_event = threading.Event()

    with _JOB_LOCK:
        _JOB_START_TIMES[job_id] = time.time()
        _JOB_PROGRESS[job_id] = 0
        _JOB_CANCEL_EVENTS[job_id] = cancel_event
        _JOB_STATUS[job_id] = "RUNNING"

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

    future = _EXECUTOR.submit(_run_with_cancel, fn, args, kwargs, cancel_event)
    with _JOB_LOCK:
        _FUTURES[job_id] = future

    return job_id


def get_job(job_id: str):
    """
    Lấy trạng thái job với cơ chế auto-cleanup tuyến tính.
    Flow: UNKNOWN -> RUNNING -> (TIMEOUT | COMPLETED | FAILED) -> EXPIRED
    """
    # --- CHECK 1: Job exists? ---
    with _JOB_LOCK:
        if job_id not in _FUTURES:
            return {"status": "UNKNOWN"}
        future = _FUTURES[job_id]
        start_time = _JOB_START_TIMES.get(job_id, time.time())
        current_status = _JOB_STATUS.get(job_id)
    current_age = time.time() - start_time

    # --- CHECK 2: Still Running? ---
    if not future.done():
        if current_status == "CANCELLED":
            return {"status": "CANCELLED", "error": "Job cancelled"}
        if current_status == "TIMEOUT":
            return {"status": "TIMEOUT", "error": "Job exceeded time limit"}
        # Sub-check: Did it timeout?
        if current_age > _DEFAULT_TIMEOUT:
            request_cancel(job_id, reason="TIMEOUT")
            logger.warning(
                f"Job {job_id} timed out after {_DEFAULT_TIMEOUT}s",
                extra={"job_id": job_id, "operation": "job_timeout"},
            )
            return {"status": "TIMEOUT", "error": "Job exceeded time limit"}

        # Still running normally
        with _JOB_LOCK:
            progress = _JOB_PROGRESS.get(job_id, 0)
        return {"status": "RUNNING", "progress": progress}

    # --- From here: future.done() == True ---
    if current_status in ("CANCELLED", "TIMEOUT"):
        clear_job(job_id)
        error = "Job was cancelled"
        if current_status == "TIMEOUT":
            error = "Job exceeded time limit"
        return {"status": current_status, "error": error}

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
        status = "CANCELLED"
        if current_status == "TIMEOUT":
            status = "TIMEOUT"
        return {"status": status, "error": "Job was cancelled"}

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
    with _JOB_LOCK:
        if job_id in _FUTURES:
            del _FUTURES[job_id]
        if job_id in _JOB_START_TIMES:
            del _JOB_START_TIMES[job_id]
        if job_id in _JOB_PROGRESS:
            del _JOB_PROGRESS[job_id]
        if job_id in _JOB_CANCEL_EVENTS:
            del _JOB_CANCEL_EVENTS[job_id]
        if job_id in _JOB_STATUS:
            del _JOB_STATUS[job_id]
