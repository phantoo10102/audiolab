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
sys.modules.setdefault("whisperx", whisperx_stub)
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


if __name__ == "__main__":
    unittest.main()
