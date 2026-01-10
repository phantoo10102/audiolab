import logging
import os
import shutil
import time
from pathlib import Path
from typing import Set

import streamlit as st

from utils.config_loader import config
from utils.constants import (
    DATA_OUTPUT_DIR,
    DATA_TEMP_DIR,
    LEGACY_PATHS,
    PROJECT_ROOT,
    ensure_data_dirs,
)
from utils.fs.path_utils import TEMP_HISTORY_DIR, get_unique_history_path

logger = logging.getLogger(__name__)

MAX_HISTORY_STEPS = config.get("system.history.max_steps", 10)


<<<<<<< HEAD:utils/fs/io_utils.py
def cleanup_old_history(history_list) -> None:
=======
def resolve_output_path(config_path, default_subdir):
    """
    Resolve output directory from config path, falling back to DATA_OUTPUT_DIR.
    """
    base_dir = Path(config_path) if config_path else DATA_OUTPUT_DIR
    if default_subdir:
        base_dir = base_dir / default_subdir
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def get_unique_history_path(original_name: str) -> Path:
    """
    Tạo đường dẫn unique cho history file, bảo toàn extension gốc.
    [FIX BUG #9] Security: Fail-fast path traversal check.
    """
    timestamp = int(time.time() * 1000)

    # --- STEP 1: Extract basename only ---
    safe_basename = Path(original_name).name

    # --- STEP 2: Validate dangerous patterns ---
    # Defense in depth: Check ký tự nguy hiểm
    DANGEROUS_PATTERNS = [
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
    for pattern in DANGEROUS_PATTERNS:
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
    return TEMP_HISTORY_DIR / filename


def cleanup_old_history(history_list):
>>>>>>> origin/main:utils/file_manager.py
    """
    Xóa các file history không còn nằm trong danh sách undo stack.
    Được gọi định kỳ từ SessionManager (mỗi 10 lần push).
    """
    try:
        if not history_list:
            return

        # Lấy danh sách các file đang được sử dụng trong history stack
        active_paths = {
            str(Path(entry.path).absolute()) for entry in history_list if entry.path
        }

        # Kiểm tra folder tồn tại trước khi quét
        if TEMP_HISTORY_DIR.exists():
            for file_path in TEMP_HISTORY_DIR.glob("*"):
                if file_path.is_file():
                    # Nếu file không nằm trong danh sách active -> Xóa
                    if str(file_path.absolute()) not in active_paths:
                        try:
                            os.remove(file_path)
                            # [FIX BUG-017] Logging debug thay vì print
                            logger.debug(f"Deleted orphan history file: {file_path.name}")
                        except OSError:
                            pass
    except Exception as e:
        # [FIX BUG-017] Logging warning thay vì print error
        logger.warning(
            "History cleanup warning",
            extra={"error": str(e), "operation": "cleanup_history"},
        )


def copy_to_history(source_path: str | Path) -> Path | None:
    """
    Copy file hiện tại vào thư mục history.
    Sử dụng Atomic operation để tránh lỗi Race Condition.
    """
    if not source_path:
        return None

    source = Path(source_path)
    dest_path = get_unique_history_path(source.name)

    # [FIX BUG-014] Atomic Operation: Try to copy directly.
    # Bắt lỗi FileNotFoundError nếu file nguồn bị xóa ngay trước khi copy.
    try:
        shutil.copy2(source, dest_path)
        return dest_path
    except (FileNotFoundError, OSError) as e:
        # [FIX BUG-017] Log warning
        logger.warning(
            "Error copying to history (Source missing)",
            extra={"source": str(source), "error": str(e)},
        )
        return None
    except Exception as e:
        # [FIX BUG-017] Log error system
        logger.error(
            "Critical error copying to history",
            extra={"source": str(source), "error": str(e)},
            exc_info=True,
        )
        return None


def migrate_legacy_data() -> None:
    """
    Kiểm tra và di chuyển thư mục cũ (temp_audio, output) vào cấu trúc data/ mới.
    Chỉ chạy 1 lần khi khởi động app.
    """
    ensure_data_dirs()

    migrated_count = 0

    for old_name, new_path in LEGACY_PATHS.items():
        old_path = PROJECT_ROOT / old_name

        # Nếu thư mục cũ tồn tại và có dữ liệu
        if old_path.exists() and old_path.is_dir():
            # Duyệt qua các file trong thư mục cũ
            for item in old_path.iterdir():
                try:
                    dest = new_path / item.name
                    if not dest.exists():  # Chỉ move nếu đích chưa có
                        if item.is_dir():
                            shutil.copytree(item, dest)
                        else:
                            shutil.move(str(item), str(dest))
                        migrated_count += 1
                except Exception as e:
                    logger.warning(f"Error migrating {item}: {e}")

            # Sau khi move hết, thử xóa thư mục cũ (nếu rỗng)
            try:
                if not any(old_path.iterdir()):
                    old_path.rmdir()
            except OSError:
                pass

    if migrated_count > 0:
        # [FIX BUG-017] Logging info
        logger.info(
            "Legacy data migration completed",
            extra={"migrated_count": migrated_count, "operation": "migration"},
        )


def get_current_session_files() -> Set[str]:
    """
    Lấy danh sách các file đang được sử dụng trong session hiện tại.
    Bảo vệ chúng khỏi bị xóa nhầm bởi bộ dọn dẹp.
    """
    session_files: Set[str] = set()

    try:
        # 1. Audio đang load
        if "app_state" in st.session_state:
            state = st.session_state.app_state
            if state.audio.current_path:
                session_files.add(str(Path(state.audio.current_path).absolute()))
            if state.audio.original_path:
                session_files.add(str(Path(state.audio.original_path).absolute()))

        # 2. History Stack
        if "history" in st.session_state:
            for entry in st.session_state.history:
                if entry.path:
                    session_files.add(str(Path(entry.path).absolute()))

        # 3. Job Results (Separation, etc.)
        if (
            "separation_result" in st.session_state
            and st.session_state.separation_result
        ):
            for stem in st.session_state.separation_result.stems:
                if stem.path:
                    session_files.add(str(Path(stem.path).absolute()))

    except Exception as e:
        logger.warning(f"Error getting session files: {e}")

    return session_files


def cleanup_empty_dirs(root_dir: Path) -> None:
    """Xóa các thư mục con rỗng."""
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        if not dirnames and not filenames:
            try:
                os.rmdir(dirpath)
            except OSError:
                pass


def cleanup_by_size(
    target_dir: Path, max_size_mb: int, protect_files: Set[str]
) -> None:
    """
    Xóa file cũ nhất nếu thư mục vượt quá dung lượng cho phép.
    """
    try:
        total_size = 0
        file_list = []

        for file_path in target_dir.rglob("*"):
            if file_path.is_file():
                stat = file_path.stat()
                total_size += stat.st_size
                file_list.append((file_path, stat.st_mtime, stat.st_size))

        max_bytes = max_size_mb * 1024 * 1024

        if total_size <= max_bytes:
            return  # Under limit

        # Sắp xếp file theo thời gian (cũ nhất đứng đầu)
        file_list.sort(key=lambda x: x[1])

        deleted_size = 0
        target_size = max_bytes * 0.8  # Xóa về mức 80%

        for file_path, mtime, size in file_list:
            if total_size - deleted_size <= target_size:
                break

            abs_path = str(file_path.absolute())
            if abs_path in protect_files:
                continue

            try:
                os.remove(file_path)
                deleted_size += size
                logger.info(
                    "[Cleanup Size] Deleted %s (%.1f KB)",
                    file_path.name,
                    size / 1024,
                )
            except OSError:
                pass

    except Exception as e:
        logger.warning(f"Cleanup by size error: {e}")


def cleanup_old_temp_files() -> None:
    """
    Hàm dọn dẹp chính. Xóa file tạm dựa trên tuổi và dung lượng.
    Được gọi khi App khởi động (session mới).
    """
    if not config.get("system.cleanup.enabled", True):
        return

    max_age_hours = config.get("system.cleanup.max_age_hours", 24)
    max_size_mb = config.get("system.cleanup.max_size_mb", 1000)

    current_time = time.time()
    max_age_seconds = max_age_hours * 3600

    # Danh sách file cần bảo vệ của session hiện tại
    protect_files = get_current_session_files()

    cleanup_dirs = [DATA_TEMP_DIR, DATA_OUTPUT_DIR]
    deleted_count = 0
    freed_bytes = 0

    for root_dir in cleanup_dirs:
        if not root_dir.exists():
            continue

        # 1. Age-based Cleanup
        for file_path in root_dir.rglob("*"):
            if not file_path.is_file():
                continue

            # Skip hidden files or specific system files if needed
            if file_path.name.startswith("."):
                continue

            try:
                # Check protection
                if str(file_path.absolute()) in protect_files:
                    continue

                # Check age
                file_mtime = os.path.getmtime(file_path)
                age = current_time - file_mtime

                if age > max_age_seconds:
                    size = file_path.stat().st_size
                    os.remove(file_path)
                    deleted_count += 1
                    freed_bytes += size
            except (OSError, PermissionError):
                continue

        # 2. Cleanup Empty Dirs
        cleanup_empty_dirs(root_dir)

        # 3. Size-based Cleanup (Optional second pass)
        if max_size_mb > 0:
            cleanup_by_size(root_dir, max_size_mb, protect_files)

    if deleted_count > 0:
        logger.info(
            "Auto cleanup completed",
            extra={
                "deleted_files": deleted_count,
                "freed_mb": round(freed_bytes / (1024 * 1024), 2),
                "operation": "cleanup",
            },
        )
