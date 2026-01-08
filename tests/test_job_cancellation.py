import sys
import time
import types
import unittest
from unittest.mock import patch
import concurrent.futures
import threading
import subprocess

streamlit_stub = types.ModuleType("streamlit")
runtime_stub = types.ModuleType("streamlit.runtime")
scriptrunner_stub = types.ModuleType("streamlit.runtime.scriptrunner")
scriptrunner_stub.get_script_run_ctx = lambda: None
runtime_stub.scriptrunner = scriptrunner_stub
streamlit_stub.runtime = runtime_stub
sys.modules.setdefault("streamlit", streamlit_stub)
sys.modules.setdefault("streamlit.runtime", runtime_stub)
sys.modules.setdefault("streamlit.runtime.scriptrunner", scriptrunner_stub)

yaml_stub = types.ModuleType("yaml")
yaml_stub.safe_load = lambda *args, **kwargs: {}
yaml_stub.dump = lambda *args, **kwargs: None
sys.modules.setdefault("yaml", yaml_stub)
sys.modules.setdefault("numpy", types.ModuleType("numpy"))
pydub_stub = types.ModuleType("pydub")
pydub_stub.AudioSegment = object
sys.modules.setdefault("pydub", pydub_stub)


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


cryptography_stub = types.ModuleType("cryptography")
cryptography_stub.fernet = types.SimpleNamespace(Fernet=_FernetStub)
sys.modules.setdefault("cryptography", cryptography_stub)
sys.modules.setdefault("cryptography.fernet", cryptography_stub.fernet)

huggingface_stub = types.ModuleType("huggingface_hub")
huggingface_stub.whoami = lambda token=None: {"name": "stub"}
sys.modules.setdefault("huggingface_hub", huggingface_stub)

from jobs import job_runner
from pipelines.separation_pipeline import DemucsPipeline


class TestJobCancellation(unittest.TestCase):
    def tearDown(self):
        for job_id in list(job_runner._FUTURES.keys()):
            job_runner.clear_job(job_id)

    def test_cooperative_cancel(self):
        def long_task(cancel_event=None):
            while True:
                if cancel_event and cancel_event.is_set():
                    raise concurrent.futures.CancelledError("Cancelled")
                time.sleep(0.01)

        job_id = job_runner.submit(long_task)
        time.sleep(0.02)
        job_runner.request_cancel(job_id)

        status = None
        for _ in range(20):
            info = job_runner.get_job(job_id)
            status = info.get("status")
            if status in ("CANCELLED", "TIMEOUT"):
                break
            time.sleep(0.01)

        self.assertEqual(status, "CANCELLED")

    def test_timeout_triggers_cancel(self):
        original_timeout = job_runner._DEFAULT_TIMEOUT
        job_runner._DEFAULT_TIMEOUT = 0.01

        def long_task(cancel_event=None):
            while True:
                if cancel_event and cancel_event.is_set():
                    raise concurrent.futures.CancelledError("Cancelled")
                time.sleep(0.01)

        try:
            job_id = job_runner.submit(long_task)
            time.sleep(0.03)
            info = job_runner.get_job(job_id)
            self.assertEqual(info.get("status"), "TIMEOUT")
        finally:
            job_runner._DEFAULT_TIMEOUT = original_timeout

    @patch("pipelines.separation_pipeline.subprocess.Popen")
    def test_demucs_cancel_terminates_process(self, popen_mock):
        class FakeProcess:
            def __init__(self):
                self.terminate_called = False
                self.kill_called = False
                self.wait_calls = 0

            def poll(self):
                return None

            def terminate(self):
                self.terminate_called = True

            def kill(self):
                self.kill_called = True

            def wait(self, timeout=None):
                self.wait_calls += 1
                if self.wait_calls == 1:
                    raise subprocess.TimeoutExpired(cmd="demucs", timeout=timeout)
                return 0

        fake_process = FakeProcess()
        popen_mock.return_value = fake_process

        cancel_event = threading.Event()
        cancel_event.set()

        with self.assertRaises(concurrent.futures.CancelledError):
            DemucsPipeline.separate(
                input_path="input.wav",
                output_dir="output",
                model_name="htdemucs",
                cancel_event=cancel_event,
            )

        self.assertTrue(fake_process.terminate_called)
        self.assertTrue(fake_process.kill_called)


if __name__ == "__main__":
    unittest.main()
