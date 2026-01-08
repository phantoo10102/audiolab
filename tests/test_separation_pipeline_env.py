import os
import sys
import types
import unittest
from unittest.mock import patch

sys.modules.setdefault("streamlit", types.ModuleType("streamlit"))

from pipelines.separation_pipeline import DemucsPipeline


class TestSeparationPipelineEnv(unittest.TestCase):
    @patch("pipelines.separation_pipeline.subprocess.run")
    def test_separation_env_and_unicode_path(self, run_mock):
        input_path = "C:\\music\\bài_hát_đặc_biệt.wav"
        output_dir = "C:\\output"

        run_mock.return_value.stdout = ""
        run_mock.return_value.stderr = ""

        DemucsPipeline.separate(input_path=input_path, output_dir=output_dir)

        args, kwargs = run_mock.call_args
        env = kwargs.get("env", {})
        self.assertEqual(env.get("PYTHONUTF8"), "1")
        self.assertEqual(env.get("PYTHONIOENCODING"), "utf-8")
        cmd = args[0] if args else []
        self.assertIn(input_path, cmd)


if __name__ == "__main__":
    unittest.main()
