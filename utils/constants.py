import os
from pathlib import Path

# --- PATH CONFIGURATION (SINGLE SOURCE OF TRUTH) ---

# Xác định thư mục gốc của dự án (thư mục ver3)
# File này nằm ở ver3/utils/constants.py -> .parent = utils -> .parent.parent = ver3
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Thư mục DATA trung tâm
DATA_DIR = PROJECT_ROOT / "data"

# Các thư mục con
DATA_INPUT_DIR = DATA_DIR / "input"  # Chứa file user upload/import gốc
DATA_OUTPUT_DIR = DATA_DIR / "output"  # Chứa file kết quả (export, stem, crop saved)
DATA_TEMP_DIR = DATA_DIR / "temp"  # Chứa file tạm (waveform, process intermediate)
DATA_DOWNLOAD_DIR = DATA_DIR / "download"  # Chứa file tải từ link (yt-dlp)

# Mapping để migration (Tên thư mục cũ -> Path mới)
LEGACY_PATHS = {"temp_audio": DATA_TEMP_DIR, "output": DATA_OUTPUT_DIR}

# --- PUBLIC HELPERS ---


def ensure_data_dirs():
    """Đảm bảo toàn bộ cấu trúc thư mục data tồn tại."""
    for path in [
        DATA_DIR,
        DATA_INPUT_DIR,
        DATA_OUTPUT_DIR,
        DATA_TEMP_DIR,
        DATA_DOWNLOAD_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


# Alias cho backward compatibility (để code cũ không bị lỗi khi import)
TEMP_DIR = DATA_TEMP_DIR
OUTPUT_DIR = DATA_OUTPUT_DIR

DATA_MODELS_DIR = DATA_DIR / "models"
if not DATA_MODELS_DIR.exists():
    DATA_MODELS_DIR.mkdir(parents=True, exist_ok=True)
