import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


torch_stub = types.ModuleType("torch")
torch_stub.cuda = types.SimpleNamespace(is_available=lambda: False)
sys.modules["torch"] = torch_stub

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

import actions.whisperx_actions as whisperx_actions


class TestWhisperxLanguageWiring(unittest.TestCase):
    def test_trung_label_passes_zh_to_service(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            segments = [{"start": 0.0, "end": 1.0, "text": "hi"}]

            def _fake_transcribe(*, language, **_kwargs):
                self.assertEqual(language, "zh")
                return {"success": True, "segments": segments}

            with patch.object(
                whisperx_actions,
                "DATA_OUTPUT_DIR",
                output_dir,
            ), patch.object(
                whisperx_actions.whisperx_service,
                "_resolve_models_dir",
                return_value=Path(tmpdir),
            ), patch.object(
                whisperx_actions.whisperx_service,
                "load_model",
                return_value={"success": True},
            ), patch.object(
                whisperx_actions.whisperx_service,
                "transcribe",
                side_effect=_fake_transcribe,
            ), patch(
                "utils.whisperx_alignment.apply_alignment",
                return_value=segments,
            ):
                result = whisperx_actions._run_whisperx_task(
                    input_path="audio.wav",
                    model_name="small",
                    language="Trung",
                    batch_size=4,
                    session_id="session",
                )

            self.assertEqual(result["language"], "Trung")

    def test_auto_language_passes_none_to_service(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            segments = [{"start": 0.0, "end": 1.0, "text": "hi"}]

            def _fake_transcribe(*, language, **_kwargs):
                self.assertIsNone(language)
                return {"success": True, "segments": segments}

            with patch.object(
                whisperx_actions,
                "DATA_OUTPUT_DIR",
                output_dir,
            ), patch.object(
                whisperx_actions.whisperx_service,
                "_resolve_models_dir",
                return_value=Path(tmpdir),
            ), patch.object(
                whisperx_actions.whisperx_service,
                "load_model",
                return_value={"success": True},
            ), patch.object(
                whisperx_actions.whisperx_service,
                "transcribe",
                side_effect=_fake_transcribe,
            ), patch(
                "utils.whisperx_alignment.apply_alignment",
                return_value=segments,
            ):
                result = whisperx_actions._run_whisperx_task(
                    input_path="audio.wav",
                    model_name="small",
                    language="auto",
                    batch_size=4,
                    session_id="session",
                )

            self.assertEqual(result["language"], "auto")


if __name__ == "__main__":
    unittest.main()
