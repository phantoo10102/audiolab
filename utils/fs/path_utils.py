import logging
import time
from pathlib import Path
from typing import Optional

from utils.constants import DATA_OUTPUT_DIR, DATA_TEMP_DIR
from utils.logging_config import get_session_id


logger = logging.getLogger(__name__)

TEMP_HISTORY_DIR = DATA_TEMP_DIR / "history"
TEMP_HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def resolve_output_path(
    config_path: Optional[str | Path], default_subdir: Optional[str | Path]
) -> Path:
    """
    Resolve output directory from config path, falling back to DATA_OUTPUT_DIR.
    """
    base_dir = Path(config_path) if config_path else DATA_OUTPUT_DIR
    if default_subdir:
        base_dir = base_dir / default_subdir
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def get_unique_history_path(
    original_name: str,
    history_dir: Optional[Path] = None,
) -> Path:
    """
    Tạo đường dẫn unique cho history file, bảo toàn extension gốc.
    [FIX BUG #9] Security: Fail-fast path traversal check.
    """
    timestamp = int(time.time() * 1000)
    base_dir = history_dir or TEMP_HISTORY_DIR
    base_dir.mkdir(parents=True, exist_ok=True)

    # --- STEP 1: Extract basename only ---
    safe_basename = Path(original_name).name

    # --- STEP 2: Validate dangerous patterns ---
    # Defense in depth: Check ký tự nguy hiểm
    dangerous_patterns = [
        "\0",  # Null byte injection
        "../",  # Unix path traversal
        "..\\",  # Windows path traversal
        ":",  # Windows drive letter
        "<",
        ">",
        "|",
        "*",
        "?",  # Invalid filename chars
    ]

    # --- STEP 3: FAIL-FAST instead of silent fallback ---
    for pattern in dangerous_patterns:
        if pattern in safe_basename:
            # Log security event
            logger.warning(
                "Path traversal/injection attempt blocked",
                extra={
                    "original_name": original_name,
                    "safe_basename": safe_basename,
                    "detected_pattern": pattern,
                    "operation": "history_path",
                    "session_id": get_session_id(),
                },
            )
            # RAISE ERROR để UI bắt và hiển thị
            raise ValueError(
                f"Invalid filename: '{original_name}'. "
                f"Filename contains forbidden character: '{pattern}'"
            )

    # --- STEP 4: Continue normal processing ---
    original_path_obj = Path(safe_basename)
    stem = original_path_obj.stem
    ext = original_path_obj.suffix

    if not ext:
        ext = ".mp3"

    # Làm sạch tên file (chỉ giữ ký tự an toàn cho filesystem)
    clean_stem = "".join(
        c for c in stem if c.isalnum() or c in (" ", "-", "_")
    ).rstrip()

    filename = f"hist_{timestamp}_{clean_stem}{ext}"
    return base_dir / filename
