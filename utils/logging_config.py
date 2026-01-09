import logging
import json
import sys
from datetime import datetime


class StructuredFormatter(logging.Formatter):
    """
    Formatter xuất log dưới dạng JSON để dễ dàng parse và monitor.
    Tự động thêm timestamp, log level, và context (session_id, operation).
    """

    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Thêm context fields nếu được truyền qua parameter 'extra'
        if hasattr(record, "session_id"):
            log_data["session_id"] = record.session_id
        if hasattr(record, "operation"):
            log_data["operation"] = record.operation
        if hasattr(record, "duration"):
            log_data["duration_s"] = round(record.duration, 3)
        if hasattr(record, "file_path"):
            log_data["file_path"] = str(record.file_path)

        # Xử lý Exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def get_session_id():
    """Lấy Session ID hiện tại của Streamlit context."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        ctx = get_script_run_ctx()
        return ctx.session_id if ctx else "unknown_session"
    except Exception:
        return "no_context"


def setup_logging(level=logging.INFO):
    """Cấu hình logging cho toàn bộ ứng dụng."""
    # Xóa handlers cũ để tránh duplicate
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)

    # Setup StreamHandler (console)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())

    # Config root logger
    root.setLevel(level)
    root.addHandler(handler)

    # Giảm bớt log ồn ào từ thư viện bên thứ 3
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("streamlit").setLevel(logging.WARNING)
    logging.getLogger("pydub").setLevel(logging.WARNING)
