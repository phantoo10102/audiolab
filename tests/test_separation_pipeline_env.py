import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("streamlit", types.ModuleType("streamlit"))
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

from pipelines.separation_pipeline import DemucsPipeline


class TestSeparationPipelineEnv(unittest.TestCase):
    @patch("pipelines.separation_pipeline.subprocess.Popen")
    def test_separation_env_and_unicode_path(self, popen_mock):
        input_path = Path("C:\\music\\bài_hát_đặc_biệt.wav")
        output_dir = Path("C:\\output")

        process = types.SimpleNamespace(
            poll=lambda: 0,
            communicate=lambda: ("", ""),
            returncode=0,
        )
        popen_mock.return_value = process

        DemucsPipeline.separate(input_path=input_path, output_dir=output_dir)

        args, kwargs = popen_mock.call_args
        env = kwargs.get("env", {})
        self.assertEqual(env.get("PYTHONUTF8"), "1")
        self.assertEqual(env.get("PYTHONIOENCODING"), "utf-8")
        cmd = args[0] if args else []
        self.assertIn(str(input_path), cmd)


if __name__ == "__main__": 
    unittest.main() 
