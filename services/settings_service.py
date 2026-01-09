import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from cryptography.fernet import Fernet
from huggingface_hub import whoami
from utils.logging_config import get_session_id
from utils.constants import DATA_MODELS_DIR

logger = logging.getLogger(__name__)
# Constants
ROOT_DIR = Path(__file__).parent.parent
ROOT_DIR = Path(__file__).parent.parent
CONFIG_FILE = ROOT_DIR / "config.yaml"
USER_SETTINGS_FILE = ROOT_DIR / "data" / "config" / "user_settings.yaml"
KEY_FILE = (
    ROOT_DIR / "data" / "config" / ".secret_key"
)  # Giữ nguyên key ở chỗ cũ để bảo mật

# Default configuration structure
DEFAULT_SETTINGS = {
    "credentials": {"hf_token": ""},
    "models": {
        "default_asr_model": "small",
        "device": "cuda" if os.environ.get("CUDA_VISIBLE_DEVICES") else "cpu",
        "compute_precision": "float16",
    },
    "processing": {
        "vad_threshold": 0.5,
        "enable_diarization": False,
        "min_speakers": 1,
        "max_speakers": 5,
    },
    "whisperx": {
        "models_dir": str(DATA_MODELS_DIR / "whisperx"),
        "vad_enabled": False,
    },
    "experimental": {"enable_beta_features": False},
}

logger = logging.getLogger(__name__)


class SettingsManager:
    _key: bytes = None
    _cipher: Fernet = None

    def __init__(self):
        self._ensure_config_dir()
        self._load_or_create_key()

    def _ensure_config_dir(self):
        """Ensure encryption key directory exists."""
        # [FIX] Thay thế SETTINGS_DIR bằng thư mục cha của KEY_FILE
        key_dir = KEY_FILE.parent
        if not key_dir.exists():
            key_dir.mkdir(parents=True, exist_ok=True)

    def _load_or_create_key(self):
        """Load encryption key or generate a new one if missing."""
        if KEY_FILE.exists():
            try:
                self._key = KEY_FILE.read_bytes()
            except Exception as e:
                logger.error(
                    "Failed to read key file",
                    extra={"error": str(e), "operation": "load_key_file"},
                )
                self._key = Fernet.generate_key()  # Fallback
        else:
            self._key = Fernet.generate_key()
            try:
                KEY_FILE.write_bytes(self._key)
                # On Unix, restrict permissions to owner only
                if os.name == "posix":
                    KEY_FILE.chmod(0o600)
            except Exception as e:
                logger.error(
                    "Failed to save key file",
                    extra={"error": str(e), "operation": "create_key_file"},
                )

        try:
            self._cipher = Fernet(self._key)
        except Exception as e:
            logger.critical(
                "Failed to initialize encryption",
                extra={"error": str(e), "operation": "init_cipher"},
            )
            self._cipher = None

    def encrypt_token(self, token: str) -> str:
        """Encrypt a string token."""
        if not token or not self._cipher:
            return ""
        try:
            return self._cipher.encrypt(token.encode()).decode()
        except Exception as e:
            logger.error(
                "Encryption failed",
                extra={"error": str(e), "operation": "encrypt_token"},
            )
            return ""

    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt a string token."""
        if not encrypted_token or not self._cipher:
            return ""
        try:
            return self._cipher.decrypt(encrypted_token.encode()).decode()
        except Exception as e:
            # Silent fail for UI (returns empty if invalid/corrupt)
            logger.warning(
                "Decryption failed or invalid token",
                extra={"error": str(e), "operation": "decrypt_token"},
            )
            return ""

    def load_settings(self) -> Dict[str, Any]:
        """Load settings directly from config.yaml"""
        # Start with Code Defaults
        merged = DEFAULT_SETTINGS.copy()

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    file_config = yaml.safe_load(f) or {}

                # Merge File Config over Defaults
                self._deep_update(merged, file_config)
            except Exception as e:
                logger.error(f"Failed to load config.yaml: {e}")

        if USER_SETTINGS_FILE.exists():
            try:
                with open(USER_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    user_config = yaml.safe_load(f) or {}

                self._deep_update(merged, user_config)
            except Exception as e:
                logger.error(f"Failed to load user_settings.yaml: {e}")

        return merged

    def _deep_update(self, base, update):
        for k, v in update.items():
            if isinstance(v, dict) and k in base:
                self._deep_update(base[k], v)
            else:
                base[k] = v

    def save_settings(self, new_settings: Dict[str, Any]) -> bool:
        """Save settings back to config.yaml and user_settings.yaml"""
        try:
            # 1. Load current file content to preserve other fields
            current_config = {}
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    current_config = yaml.safe_load(f) or {}

            # 2. Merge new settings
            self._deep_update(current_config, new_settings)

            # 3. Write back
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                yaml.dump(
                    current_config,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )

            user_config_dir = USER_SETTINGS_FILE.parent
            user_config_dir.mkdir(parents=True, exist_ok=True)
            with open(USER_SETTINGS_FILE, "w", encoding="utf-8") as f:
                yaml.dump(
                    new_settings,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )

            logger.info("Settings saved to config.yaml and user_settings.yaml")
            return True
        except Exception as e:
            logger.error(f"Failed to save config.yaml: {e}")
            return False

    def validate_hf_token(self, token: str) -> Tuple[bool, str]:
        """Validate format and Ping HuggingFace API."""
        if not token:
            return False, "Token is empty."

        if not token.startswith("hf_"):
            return False, "Invalid format. Token must start with 'hf_'."

        try:
            # Check with HF API
            user_info = whoami(token=token)
            return True, f"Valid token for user: {user_info.get('name', 'Unknown')}"
        except Exception as e:
            return False, f"API Validation failed: {str(e)}"

    def get_hf_token(self) -> str:
        """Convenience method to get the raw decrypted token."""
        settings = self.load_settings()
        encrypted = settings.get("credentials", {}).get("hf_token", "")
        return self.decrypt_token(encrypted)

    def reset_to_defaults(self):
        """Reset settings file to factory defaults."""
        self.save_settings(DEFAULT_SETTINGS)

    def validate_device(self, device: str) -> tuple[bool, str]:
        """
        Kiểm tra xem thiết bị tính toán (CPU/CUDA) có khả dụng không.
        """
        if device == "cpu":
            return True, "✅ CPU is always available."

        if device == "cuda":
            try:
                import torch

                if torch.cuda.is_available():
                    # Lấy tên GPU để hiển thị cho user thấy "uy tín"
                    device_name = torch.cuda.get_device_name(0)
                    return True, f"✅ CUDA Available: {device_name}"
                else:
                    return (
                        False,
                        "❌ CUDA not detected. Please install NVIDIA drivers or use CPU.",
                    )
            except ImportError:
                return False, "❌ PyTorch not installed or missing CUDA support."
            except Exception as e:
                return False, f"❌ CUDA check failed: {str(e)}"

        return False, f"❌ Unknown device type: {device}"


# [CRITICAL FIX] Create Singleton Instance matching the new class name
settings_manager = SettingsManager()
