import sys
import types
import unittest
from unittest.mock import patch


torch_stub = types.ModuleType("torch")
torch_stub.cuda = types.SimpleNamespace(is_available=lambda: False)
sys.modules.setdefault("torch", torch_stub)

whisperx_stub = types.ModuleType("whisperx")
whisperx_stub.load_model = lambda *args, **kwargs: "model"
whisperx_stub.load_audio = lambda *args, **kwargs: b"audio"
sys.modules["whisperx"] = whisperx_stub
sys.modules.setdefault("numpy", types.ModuleType("numpy"))

pydub_stub = types.ModuleType("pydub")
pydub_stub.AudioSegment = object
sys.modules.setdefault("pydub", pydub_stub)

streamlit_stub = sys.modules.get("streamlit")
if streamlit_stub is None:
    streamlit_stub = types.ModuleType("streamlit")
    sys.modules["streamlit"] = streamlit_stub
if not hasattr(streamlit_stub, "session_state"):
    streamlit_stub.session_state = {}
if not hasattr(streamlit_stub, "toast"):
    streamlit_stub.toast = lambda *args, **kwargs: None
if not hasattr(streamlit_stub, "error"):
    streamlit_stub.error = lambda *args, **kwargs: None

runtime_stub = types.ModuleType("streamlit.runtime")
scriptrunner_stub = types.ModuleType("streamlit.runtime.scriptrunner")
scriptrunner_stub.get_script_run_ctx = lambda: None
runtime_stub.scriptrunner = scriptrunner_stub
streamlit_stub.runtime = runtime_stub
sys.modules.setdefault("streamlit.runtime", runtime_stub)
sys.modules.setdefault("streamlit.runtime.scriptrunner", scriptrunner_stub)

import importlib

whisperx_actions = importlib.import_module("actions.whisperx_actions")
whisperx_service_module = importlib.import_module("services.whisperx_service")


class _AudioState:
    def __init__(self):
        self.is_loaded = True
        self.current_path = "audio.wav"


class _State:
    def __init__(self):
        self.audio = _AudioState()


class _Manager:
    def __init__(self):
        self.state = _State()


class TestWhisperXVad(unittest.TestCase):
    def setUp(self):
        streamlit_stub.session_state.clear()
        streamlit_stub.session_state.update(
            {
                "whisperx_model": "small",
                "whisperx_language": "en",
                "whisperx_export_format": "Text",
                "whisperx_alignment": "Đoạn",
                "user_settings": {"whisperx": {}},
            }
        )

    def test_vad_on_passed_to_job(self):
        streamlit_stub.session_state["whisperx_vad"] = "ON"
        with patch.object(
            whisperx_actions, "get_manager", return_value=_Manager()
        ), patch.object(whisperx_actions, "job_runner") as job_runner, patch.object(
            whisperx_actions.os.path, "exists", return_value=True
        ):
            job_runner.submit.return_value = "job"
            whisperx_actions.run_whisperx_callback()

        _, kwargs = job_runner.submit.call_args
        self.assertTrue(kwargs["vad_enabled"])

    def test_vad_off_passed_to_job(self):
        streamlit_stub.session_state["whisperx_vad"] = "OFF"
        with patch.object(
            whisperx_actions, "get_manager", return_value=_Manager()
        ), patch.object(whisperx_actions, "job_runner") as job_runner, patch.object(
            whisperx_actions.os.path, "exists", return_value=True
        ):
            job_runner.submit.return_value = "job"
            whisperx_actions.run_whisperx_callback()

        _, kwargs = job_runner.submit.call_args
        self.assertFalse(kwargs["vad_enabled"])


class _ModelNoVad:
    def __init__(self):
        self.last_language = None

    def transcribe(self, audio, batch_size=16, language=None):
        self.last_language = language
        return {"segments": [], "language": language}


class _ModelWithVad:
    def __init__(self):
        self.last_language = None
        self.last_vad = None

    def transcribe(self, audio, batch_size=16, language=None, vad_filter=False):
        self.last_language = language
        self.last_vad = vad_filter
        return {"segments": [], "language": language}


class TestWhisperXTranscribeCompat(unittest.TestCase):
    def test_transcribe_omits_vad_when_unsupported(self):
        service = whisperx_service_module.WhisperXService()
        service.model = _ModelNoVad()
        with patch.object(
            whisperx_service_module.whisperx,
            "load_audio",
            return_value=b"audio",
            create=True,
        ):
            result = service.transcribe(
                audio_path="audio.wav",
                language="zh",
                batch_size=4,
                vad_filter=True,
            )
        self.assertTrue(result["success"])
        self.assertEqual(service.model.last_language, "zh")

    def test_transcribe_passes_vad_when_supported(self):
        service = whisperx_service_module.WhisperXService()
        service.model = _ModelWithVad()
        with patch.object(
            whisperx_service_module.whisperx,
            "load_audio",
            return_value=b"audio",
            create=True,
        ):
            result = service.transcribe(
                audio_path="audio.wav",
                language="zh",
                batch_size=4,
                vad_filter=True,
            )
        self.assertTrue(result["success"])
        self.assertEqual(service.model.last_language, "zh")
        self.assertTrue(service.model.last_vad)

    def test_transcribe_auto_language_omits_language(self):
        service = whisperx_service_module.WhisperXService()
        service.model = _ModelNoVad()
        with patch.object(
            whisperx_service_module.whisperx,
            "load_audio",
            return_value=b"audio",
            create=True,
        ):
            result = service.transcribe(
                audio_path="audio.wav",
                language=None,
                batch_size=4,
                vad_filter=False,
            )
        self.assertTrue(result["success"])
        self.assertIsNone(service.model.last_language)


if __name__ == "__main__":
    unittest.main()
