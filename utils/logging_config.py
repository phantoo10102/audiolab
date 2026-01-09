import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from utils.constants import PROJECT_ROOT


LOG_ROOT_DIR = PROJECT_ROOT / "data" / "log"
APP_LOGGER_PREFIXES = ("services", "utils", "components", "app")


@dataclass(frozen=True)
class ColorRule:
    color: str
    keywords: tuple[str, ...]


COLOR_RESET = "\x1b[0m"
COLOR_RED = "\x1b[31m"
COLOR_YELLOW = "\x1b[33m"
COLOR_GREEN = "\x1b[32m"
COLOR_LIGHT_BLUE = "\x1b[94m"

COMPLETION_RULE = ColorRule(
    color=COLOR_GREEN,
    keywords=("completed", "success", "exported", "done", "finished"),
)
RUNNING_RULE = ColorRule(
    color=COLOR_LIGHT_BLUE,
    keywords=("started", "loading", "downloading", "running", "submitted", "computing", "processing"),
)


def _colors_enabled() -> bool:
    return not bool(os.environ.get("NO_COLOR"))


def _safe_str(value) -> str:
    if value is None:
        return ""
    return str(value)


def _redact_sensitive(value: str) -> str:
    if not value:
        return value
    lowered = value.lower()
    if any(token in lowered for token in ("token", "hf_token", "huggingface")):
        return "[REDACTED]"
    return value


class JsonLinesFormatter(logging.Formatter):
    """
    JSONL formatter with structured fields for file logging.
    """

    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": _redact_sensitive(record.getMessage()),
        }

        if hasattr(record, "session_id"):
            log_data["session_id"] = record.session_id
        if hasattr(record, "operation"):
            log_data["operation"] = record.operation
        if hasattr(record, "duration"):
            log_data["duration_s"] = round(record.duration, 3)
        if hasattr(record, "file_path"):
            log_data["file_path"] = _safe_str(record.file_path)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """
    Compact console output with optional ANSI colors.
    """

    def format(self, record):
        message = _redact_sensitive(record.getMessage())
        level = record.levelname
        prefix = f"{level}: "
        line = f"{prefix}{message}"

        if record.name and record.name != "root":
            line = f"{prefix}{record.name} - {message}"

        if not _colors_enabled():
            return line

        color = ""
        if record.levelno >= logging.ERROR:
            color = COLOR_RED
        elif record.levelno == logging.WARNING:
            color = COLOR_YELLOW
        elif record.levelno == logging.INFO:
            lowered = message.lower()
            if any(word in lowered for word in COMPLETION_RULE.keywords):
                color = COMPLETION_RULE.color
            elif any(word in lowered for word in RUNNING_RULE.keywords):
                color = RUNNING_RULE.color

        if color:
            return f"{color}{line}{COLOR_RESET}"
        return line


class JsonLinesFileHandler(logging.Handler):
    def __init__(self, log_root: Path, filename: str = "app.jsonl"):
        super().__init__()
        self.log_root = log_root
        self.filename = filename

    def emit(self, record):
        try:
            log_dir = self._ensure_log_dir()
            log_path = log_dir / self.filename
            message = self.format(record)
            with open(log_path, "a", encoding="utf-8") as log_file:
                log_file.write(message + "\n")
        except Exception:
            self.handleError(record)

    def _ensure_log_dir(self) -> Path:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        log_dir = self.log_root / date_str
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir


class SuppressWarningsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno != logging.WARNING


class WarningFilter(logging.Filter):
    def __init__(self, *, external: bool):
        super().__init__()
        self.external = external

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno != logging.WARNING:
            return False
        logger_name = record.name or ""
        is_internal = logger_name.startswith(APP_LOGGER_PREFIXES) or logger_name == "root"
        return (not is_internal) if self.external else is_internal


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
        for handler in list(root.handlers):
            root.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ConsoleFormatter())
    console_handler.addFilter(SuppressWarningsFilter())

    file_handler = JsonLinesFileHandler(LOG_ROOT_DIR)
    file_handler.setFormatter(JsonLinesFormatter())

    warning_handler = JsonLinesFileHandler(LOG_ROOT_DIR, filename="warnings.jsonl")
    warning_handler.setFormatter(JsonLinesFormatter())
    warning_handler.addFilter(WarningFilter(external=False))

    external_warning_handler = JsonLinesFileHandler(
        LOG_ROOT_DIR,
        filename="external_warnings.jsonl",
    )
    external_warning_handler.setFormatter(JsonLinesFormatter())
    external_warning_handler.addFilter(WarningFilter(external=True))

    # Config root logger
    root.setLevel(level)
    root.addHandler(console_handler)
    root.addHandler(file_handler)
    root.addHandler(warning_handler)
    root.addHandler(external_warning_handler)

    # Giảm bớt log ồn ào từ thư viện bên thứ 3
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("streamlit").setLevel(logging.WARNING)
    logging.getLogger("pydub").setLevel(logging.WARNING)
    logging.captureWarnings(True)
