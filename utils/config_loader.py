import os
import logging
from pathlib import Path
from typing import Any, Dict

# [FIX IMPORT ERROR] Import đúng tên singleton 'settings_manager'
from services.settings_service import settings_manager

logger = logging.getLogger(__name__)

# Try importing yaml (PyYAML), fallback if missing
try:
    import yaml
except ImportError:
    yaml = None
    logger.warning("PyYAML not installed. Config file will be ignored, using defaults.")


class Config:
    _instance = None
    _config = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """Loads config from yaml or falls back to defaults."""
        # Config file expected at project root (same level as app.py)
        project_root = Path(__file__).parent.parent
        config_path = project_root / "config.yaml"

        # 1. Load Defaults First
        self._config = self._get_defaults()

        # 2. Override with User Config if exists (config.yaml)
        if config_path.exists() and yaml:
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    user_config = yaml.safe_load(f) or {}
                    self._merge_config(self._config, user_config)
                    logger.info(f"Loaded configuration from {config_path}")
            except Exception as e:
                logger.error(f"Error loading config.yaml: {e}. Using defaults.")
        elif not config_path.exists():
            logger.info("config.yaml not found. Using default configuration.")

    def _merge_config(self, default: Dict, user: Dict):
        """Recursive deep merge."""
        for k, v in user.items():
            if isinstance(v, dict) and k in default and isinstance(default[k], dict):
                self._merge_config(default[k], v)
            else:
                default[k] = v

    def get(self, key_path: str, default=None) -> Any:
        """Access config using dot notation: 'audio.export.default_format'"""
        keys = key_path.split(".")
        value = self._config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
        return value if value is not None else default

    def _get_defaults(self) -> Dict:
        """Hard-coded defaults matching original codebase."""
        return {
            "audio": {
                "export": {
                    "default_format": "mp3",
                    "default_bitrate": "320k",
                    "format_options": ["mp3", "wav", "flac"],
                    "bitrate_options": ["128k", "320k"],
                }
            },
            "processing": {
                "denoise": {
                    "default_strength": 0.5,
                    "reduce_noise_db": 12.0,
                    "default_method": "auto",
                },
                "trim_silence": {
                    "silence_thresh_db": -40.0,
                    "min_silence_len_ms": 400,
                    "keep_silence_ms": 150,
                },
                "separation": {
                    "default_model": "htdemucs",
                    "available_models": ["htdemucs"],
                },
            },
            "whisperx": {
                "models_dir": "data/models/whisperx",
            },
            "system": {
                "jobs": {"timeout_seconds": 300, "max_workers": 4},
                "history": {"max_steps": 10, "cleanup_interval": 10},
                "cache": {"waveform_ttl": 3600},
                "cleanup": {"enabled": True, "max_age_hours": 24, "max_size_mb": 1000},
                "credentials": {"hf_token": ""},
                "models": {
                    "default_asr_model": "small",
                    "device": "cpu",
                    "compute_precision": "float16",
                },
            },
        }


# Global instance
config = Config()
