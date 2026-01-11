import sys
import time
import types
import unittest

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
if "pydantic" not in sys.modules:
    pydantic_stub = types.ModuleType("pydantic")

    class _BaseModel:
        def __init__(self, *args, **kwargs):
            pass

    def _field(default=None, **kwargs):
        return default

    pydantic_stub.BaseModel = _BaseModel
    pydantic_stub.Field = _field
    pydantic_stub.ConfigDict = dict
    sys.modules.setdefault("pydantic", pydantic_stub)


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


class TestJobRunner(unittest.TestCase):
    def tearDown(self):
        for job_id in list(job_runner._FUTURES.keys()):
            job_runner.clear_job(job_id)

    def test_completed_job_expires_after_ttl(self):
        original_ttl = job_runner.COMPLETED_JOB_TTL
        job_id = None
        job_runner.COMPLETED_JOB_TTL = 0.01

        try:
            job_id = job_runner.submit(lambda: "ok")

            info = None
            for _ in range(50):
                info = job_runner.get_job(job_id)
                if info.get("status") == "COMPLETED":
                    break
                time.sleep(0.001)

            self.assertEqual(info.get("status"), "COMPLETED")

            time.sleep(0.02)
            expired = job_runner.get_job(job_id)
            self.assertEqual(expired.get("status"), "EXPIRED")
        finally:
            job_runner.COMPLETED_JOB_TTL = original_ttl
            if job_id:
                job_runner.clear_job(job_id)

    def test_timeout_sets_cancel_event(self):
        original_timeout = job_runner._DEFAULT_TIMEOUT
        job_id = None
        job_runner._DEFAULT_TIMEOUT = 0.01

        def long_task(cancel_event=None):
            while True:
                if cancel_event and cancel_event.is_set():
                    return "cancelled"
                time.sleep(0.002)

        try:
            job_id = job_runner.submit(long_task)
            time.sleep(0.02)
            info = job_runner.get_job(job_id)

            self.assertEqual(info.get("status"), "TIMEOUT")
            self.assertTrue(job_runner._JOB_CANCEL_EVENTS[job_id].is_set())
        finally:
            job_runner._DEFAULT_TIMEOUT = original_timeout
            if job_id:
                job_runner.clear_job(job_id)

    def test_failed_job_returns_error_and_cleans_up(self):
        job_id = job_runner.submit(lambda: (_ for _ in ()).throw(ValueError("boom")))

        info = None
        for _ in range(50):
            info = job_runner.get_job(job_id)
            if info.get("status") == "FAILED":
                break
            time.sleep(0.001)

        self.assertEqual(info.get("status"), "FAILED")
        self.assertIn("boom", info.get("error", ""))
        self.assertNotIn(job_id, job_runner._FUTURES)


if __name__ == "__main__":
    unittest.main()
