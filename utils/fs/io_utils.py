import logging
import os
import shutil
import time
from pathlib import Path
from typing import Set

import streamlit as st

#
from utils.config_loader import config
#
from utils.constants import (
    DATA_OUTPUT_DIR,
    DATA_TEMP_DIR,
    LEGACY_PATHS,
    PROJECT_ROOT,
    ensure_data_dirs,
)
# Giả định path_utils đã được tách ra theo kế hoạch refactor
# Nếu chưa có file này, bạn cần đảm bảo utils/fs/path_utils.py tồn tại
# hoặc copy hàm get_unique_history_path vào đây tạm thời.
from utils.fs.path_utils import TEMP_HISTORY_DIR, get_unique_history_path

logger = logging.getLogger(__name__)

# Định nghĩa biến MAX_HISTORY_STEPS để session_manager import được
MAX_HISTORY_STEPS = config.get("system.history.max_steps", 10)


def resolve_output_path(config_path, default_subdir) -> Path:
    """
    Resolve output directory from config path, falling back to DATA_OUTPUT_DIR.
    """
    base_dir = Path(config_path) if config_path else DATA_OUTPUT_DIR
    if default_subdir:
        base_dir = base_dir / default_subdir
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def cleanup_old_history(history_list) -> None:
    """
    Xóa các file history không còn nằm trong danh sách undo stack.
    Được gọi định kỳ từ SessionManager.
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
                            logger.debug(f"Deleted orphan history file: {file_path.name}")
                        except OSError:
                            pass
    except Exception as e:
        logger.warning(
            "History cleanup warning",
            extra={"error": str(e), "operation": "cleanup_history"},
        )


def copy_to_history(source_path: str | Path) -> Path | None:
    """
    Copy file hiện tại vào thư mục history.
    """
    if not source_path:
        return None

    source = Path(source_path)
    # Hàm này được import từ path_utils để tránh lặp code
    dest_path = get_unique_history_path(source.name)

    try:
        shutil.copy2(source, dest_path)
        return dest_path
    except (FileNotFoundError, OSError) as e:
        logger.warning(
            "Error copying to history (Source missing)",
            extra={"source": str(source), "error": str(e)},
        )
        return None
    except Exception as e:
        logger.error(
            "Critical error copying to history",
            extra={"source": str(source), "error": str(e)},
            exc_info=True,
        )
        return None


def migrate_legacy_data() -> None:
    """
    Kiểm tra và di chuyển thư mục cũ (temp_audio, output) vào cấu trúc data/ mới.
    """
    ensure_data_dirs()

    migrated_count = 0

    for old_name, new_path in LEGACY_PATHS.items():
        old_path = PROJECT_ROOT / old_name

        if old_path.exists() and old_path.is_dir():
            for item in old_path.iterdir():
                try:
                    dest = new_path / item.name
                    if not dest.exists():
                        if item.is_dir():
                            shutil.copytree(item, dest)
                        else:
                            shutil.move(str(item), str(dest))
                        migrated_count += 1
                except Exception as e:
                    logger.warning(f"Error migrating {item}: {e}")

            try:
                if not any(old_path.iterdir()):
                    old_path.rmdir()
            except OSError:
                pass

    if migrated_count > 0:
        logger.info(
            "Legacy data migration completed",
            extra={"migrated_count": migrated_count, "operation": "migration"},
        )


def get_current_session_files() -> Set[str]:
    """
    Lấy danh sách các file đang được sử dụng trong session hiện tại.
    """
    session_files: Set[str] = set()

    try:
        if "app_state" in st.session_state:
            state = st.session_state.app_state
            if state.audio.current_path:
                session_files.add(str(Path(state.audio.current_path).absolute()))
            if state.audio.original_path:
                session_files.add(str(Path(state.audio.original_path).absolute()))

        if "history" in st.session_state:
            for entry in st.session_state.history:
                if entry.path:
                    session_files.add(str(Path(entry.path).absolute()))

        if (
            "separation_result" in st.session_state
            and st.session_state.separation_result
        ):
            # Giả định separation_result là object có attribute stems hoặc dict
            # Cần defensive coding ở đây nếu cấu trúc object khác
            stems = getattr(st.session_state.separation_result, "stems", [])
            for stem in stems:
                path_val = getattr(stem, "path", None)
                if path_val:
                    session_files.add(str(Path(path_val).absolute()))

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
            return

        file_list.sort(key=lambda x: x[1])

        deleted_size = 0
        target_size = max_bytes * 0.8

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
    """
    if not config.get("system.cleanup.enabled", True):
        return

    max_age_hours = config.get("system.cleanup.max_age_hours", 24)
    max_size_mb = config.get("system.cleanup.max_size_mb", 1000)

    current_time = time.time()
    max_age_seconds = max_age_hours * 3600

    protect_files = get_current_session_files()

    cleanup_dirs = [DATA_TEMP_DIR, DATA_OUTPUT_DIR]
    deleted_count = 0
    freed_bytes = 0

    for root_dir in cleanup_dirs:
        if not root_dir.exists():
            continue

        for file_path in root_dir.rglob("*"):
            if not file_path.is_file():
                continue

            if file_path.name.startswith("."):
                continue

            try:
                if str(file_path.absolute()) in protect_files:
                    continue

                file_mtime = os.path.getmtime(file_path)
                age = current_time - file_mtime

                if age > max_age_seconds:
                    size = file_path.stat().st_size
                    os.remove(file_path)
                    deleted_count += 1
                    freed_bytes += size
            except (OSError, PermissionError):
                continue

        cleanup_empty_dirs(root_dir)

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