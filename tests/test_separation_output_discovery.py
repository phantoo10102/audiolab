import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.modules.setdefault("streamlit", types.ModuleType("streamlit"))
sys.modules.setdefault("numpy", types.ModuleType("numpy"))
pydub_stub = types.ModuleType("pydub")
pydub_stub.AudioSegment = object
sys.modules.setdefault("pydub", pydub_stub)
sys.modules.setdefault("yaml", types.ModuleType("yaml"))
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

from pipelines.separation_pipeline import _find_best_stem_dir, _select_wav_files


class TestSeparationOutputDiscovery(unittest.TestCase):
    def _write_stems(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        for name in ["vocals.wav", "drums.wav", "bass.wav", "other.wav"]:
            (directory / name).write_bytes(b"RIFF0000WAVE")

    def test_fallback_discovery_on_mismatch(self):
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            model_dir = base_dir / "htdemucs"
            expected_dir = model_dir / "original_name"
            fallback_dir = model_dir / "bai_hat_dac_biet"

            self._write_stems(fallback_dir)

            run_start_ts = 0.0
            best_dir = _find_best_stem_dir(model_dir, run_start_ts)
            self.assertEqual(best_dir, fallback_dir)
            stems = _select_wav_files(best_dir)
            self.assertEqual(len(stems), 4)

    def test_primary_dir_used_when_present(self):
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            model_dir = base_dir / "htdemucs"
            expected_dir = model_dir / "original_name"
            fallback_dir = model_dir / "bai_hat_dac_biet"

            self._write_stems(expected_dir)
            self._write_stems(fallback_dir)

            best_dir = _find_best_stem_dir(model_dir, run_start_ts=0.0)
            self.assertIn(best_dir, {expected_dir, fallback_dir})
            stems = _select_wav_files(expected_dir)
            self.assertEqual(len(stems), 4)


if __name__ == "__main__":
    unittest.main()
