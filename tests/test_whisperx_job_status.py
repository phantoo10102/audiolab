import sys
import types
import unittest
from unittest import mock

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

class SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        if name in self:
            del self[name]
        else:
            raise AttributeError(name)


streamlit_stub = sys.modules.get("streamlit")
if streamlit_stub is None:
    streamlit_stub = types.ModuleType("streamlit")
    sys.modules["streamlit"] = streamlit_stub
if not hasattr(streamlit_stub, "session_state"):
    streamlit_stub.session_state = SessionState()
if not hasattr(streamlit_stub, "toast"):
    streamlit_stub.toast = lambda *args, **kwargs: None
if not hasattr(streamlit_stub, "error"):
    streamlit_stub.error = lambda *args, **kwargs: None
if not hasattr(streamlit_stub, "rerun"):
    streamlit_stub.rerun = lambda *args, **kwargs: None

runtime_stub = types.ModuleType("streamlit.runtime")
scriptrunner_stub = types.ModuleType("streamlit.runtime.scriptrunner")
streamlit_stub.runtime = runtime_stub
sys.modules.setdefault("streamlit.runtime", runtime_stub)
sys.modules.setdefault("streamlit.runtime.scriptrunner", scriptrunner_stub)

from actions import whisperx_actions


class TestWhisperxJobStatus(unittest.TestCase):
    def setUp(self):
        streamlit_stub.session_state.clear()
        streamlit_stub.session_state["whisperx_job_id"] = "job-123"
        streamlit_stub.error = mock.Mock()
        streamlit_stub.toast = mock.Mock()
        streamlit_stub.rerun = mock.Mock()

    def test_completed_clears_job_and_sets_result(self):
        result = {"full_text": "done", "total_duration": 1.2}
        with mock.patch.object(
            whisperx_actions.job_runner,
            "get_job",
            return_value={"status": "COMPLETED", "result": result},
        ), mock.patch.object(whisperx_actions.job_runner, "clear_job") as clear_job:
            running = whisperx_actions.check_whisperx_job()

        self.assertFalse(running)
        self.assertNotIn("whisperx_job_id", streamlit_stub.session_state)
        self.assertEqual(streamlit_stub.session_state.get("whisperx_result"), result)
        clear_job.assert_called_once_with("job-123")
        streamlit_stub.rerun.assert_not_called()

    def test_failed_clears_job_and_reruns(self):
        with mock.patch.object(
            whisperx_actions.job_runner,
            "get_job",
            return_value={"status": "FAILED", "error": "boom"},
        ), mock.patch.object(whisperx_actions.job_runner, "clear_job") as clear_job:
            running = whisperx_actions.check_whisperx_job()

        self.assertFalse(running)
        self.assertNotIn("whisperx_job_id", streamlit_stub.session_state)
        clear_job.assert_called_once_with("job-123")
        streamlit_stub.rerun.assert_not_called()

    def test_terminal_states_clear_job(self):
        terminal_statuses = ["CANCELLED", "TIMEOUT", "EXPIRED", "UNKNOWN"]
        for status in terminal_statuses:
            with self.subTest(status=status):
                streamlit_stub.session_state["whisperx_job_id"] = "job-123"
                streamlit_stub.rerun.reset_mock()
                with mock.patch.object(
                    whisperx_actions.job_runner,
                    "get_job",
                    return_value={"status": status, "error": "oops"},
                ), mock.patch.object(
                    whisperx_actions.job_runner, "clear_job"
                ) as clear_job:
                    running = whisperx_actions.check_whisperx_job()

                self.assertFalse(running)
                self.assertNotIn("whisperx_job_id", streamlit_stub.session_state)
                clear_job.assert_called_once_with("job-123")
                streamlit_stub.rerun.assert_not_called()


if __name__ == "__main__":
    unittest.main()
