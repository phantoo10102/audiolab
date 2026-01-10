import sys
import types
import unittest
from unittest import mock

pydub_stub = types.ModuleType("pydub")
pydub_stub.AudioSegment = object
sys.modules.setdefault("pydub", pydub_stub)
sys.modules.setdefault("yaml", types.ModuleType("yaml"))
cryptography_stub = types.ModuleType("cryptography")
fernet_stub = types.ModuleType("cryptography.fernet")

class _Fernet:
    def __init__(self, *args, **kwargs):
        pass

    @staticmethod
    def generate_key():
        return b"key"

    def encrypt(self, value):
        return value

    def decrypt(self, value):
        return value

fernet_stub.Fernet = _Fernet
cryptography_stub.fernet = fernet_stub
sys.modules.setdefault("cryptography", cryptography_stub)
sys.modules.setdefault("cryptography.fernet", fernet_stub)
huggingface_stub = types.ModuleType("huggingface_hub")
huggingface_stub.whoami = lambda *args, **kwargs: {}
sys.modules.setdefault("huggingface_hub", huggingface_stub)

from utils import shutdown


class TestShutdownCleanup(unittest.TestCase):
    def test_cleanup_calls_services(self):
        with mock.patch.object(
            shutdown.local_audio_server, "stop_audio_server"
        ) as stop_server, mock.patch.object(
            shutdown.job_runner, "shutdown"
        ) as shutdown_jobs:
            shutdown.cleanup_on_exit()

        stop_server.assert_called_once_with()
        shutdown_jobs.assert_called_once_with(reason="CANCELLED")


if __name__ == "__main__":
    unittest.main()
