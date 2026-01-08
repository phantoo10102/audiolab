import json
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


class _FernetStub:
    @staticmethod
    def generate_key():
        return b"stub-key"

    def __init__(self, *args, **kwargs):
        pass

    def encrypt(self, data):
        return data

    def decrypt(self, data):
        return data


class _YamlStub:
    @staticmethod
    def safe_load(stream):
        content = stream.read()
        if not content.strip():
            return {}
        return json.loads(content)

    @staticmethod
    def dump(data, stream, **kwargs):
        stream.write(json.dumps(data, ensure_ascii=False))


torch_stub = types.ModuleType("torch")
torch_stub.cuda = types.SimpleNamespace(is_available=lambda: False)
sys.modules.setdefault("torch", torch_stub)

whisperx_stub = types.ModuleType("whisperx")
whisperx_stub.load_model = lambda *args, **kwargs: "model"
sys.modules.setdefault("whisperx", whisperx_stub)
sys.modules.setdefault("numpy", types.ModuleType("numpy"))
pydub_stub = types.ModuleType("pydub")
pydub_stub.AudioSegment = object
sys.modules.setdefault("pydub", pydub_stub)
streamlit_stub = types.ModuleType("streamlit")
runtime_stub = types.ModuleType("streamlit.runtime")
scriptrunner_stub = types.ModuleType("streamlit.runtime.scriptrunner")
scriptrunner_stub.get_script_run_ctx = lambda: None
runtime_stub.scriptrunner = scriptrunner_stub
streamlit_stub.runtime = runtime_stub
sys.modules.setdefault("streamlit", streamlit_stub)
sys.modules.setdefault("streamlit.runtime", runtime_stub)
sys.modules.setdefault("streamlit.runtime.scriptrunner", scriptrunner_stub)

cryptography_stub = types.ModuleType("cryptography")
cryptography_stub.fernet = types.SimpleNamespace(Fernet=_FernetStub)
sys.modules.setdefault("cryptography", cryptography_stub)
sys.modules.setdefault("cryptography.fernet", cryptography_stub.fernet)

huggingface_stub = types.ModuleType("huggingface_hub")
huggingface_stub.whoami = lambda token=None: {"name": "stub"}
sys.modules.setdefault("huggingface_hub", huggingface_stub)

sys.modules.setdefault("yaml", _YamlStub)

import importlib
import yaml

settings_service = importlib.import_module("services.settings_service")
from services.whisperx_service import WhisperXService


class TestWhisperXModelsDir(unittest.TestCase):
    def test_save_settings_persists_models_dir(self):
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            config_path = tmp_path / "config.yaml"
            user_path = tmp_path / "user_settings.yaml"
            key_path = tmp_path / ".secret_key"

            with patch.object(settings_service, "CONFIG_FILE", config_path), patch.object(
                settings_service, "USER_SETTINGS_FILE", user_path
            ), patch.object(settings_service, "KEY_FILE", key_path):
                manager = settings_service.SettingsManager()
                settings = manager.load_settings()
                settings.setdefault("whisperx", {})
                settings["whisperx"]["models_dir"] = "D:/models/whisperx"
                self.assertTrue(manager.save_settings(settings))

                refreshed = settings_service.SettingsManager().load_settings()
                self.assertEqual(
                    refreshed["whisperx"]["models_dir"], "D:/models/whisperx"
                )

    def test_ensure_model_available(self):
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            service = WhisperXService()
            model_dir = tmp_path / "whisperx"
            model_dir.mkdir(parents=True, exist_ok=True)
            (model_dir / "small").mkdir()
            (model_dir / "small" / "model.bin").write_text("stub")

            with patch.object(whisperx_stub, "load_model") as load_model:
                result = service.ensure_whisperx_model(
                    model_dir, "small", device="cpu", compute_type="int8"
                )
                self.assertIsNone(result)
                load_model.assert_not_called()

            with patch.object(whisperx_stub, "load_model", return_value="model") as load_model:
                result = service.ensure_whisperx_model(
                    model_dir, "medium", device="cpu", compute_type="int8"
                )
                self.assertEqual(result, "model")
                load_model.assert_called_once()


if __name__ == "__main__":
    unittest.main()
