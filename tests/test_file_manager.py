import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from utils.fs.path_utils import get_unique_history_path, resolve_output_path


class TestFileManagerUtilities(unittest.TestCase):
    def test_resolve_output_path_creates_dir(self):
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir) / "outputs"
            resolved = resolve_output_path(base_dir, "denoise")
            self.assertTrue(resolved.exists())
            self.assertEqual(resolved, base_dir / "denoise")

    def test_get_unique_history_path_uses_custom_dir(self):
        with TemporaryDirectory() as tmpdir:
            history_dir = Path(tmpdir) / "history"
            path = get_unique_history_path("audio.wav", history_dir=history_dir)
            self.assertTrue(path.parent.exists())
            self.assertEqual(path.parent, history_dir)
            self.assertTrue(path.name.startswith("hist_"))
            self.assertTrue(path.name.endswith(".wav"))


if __name__ == "__main__":
    unittest.main()
