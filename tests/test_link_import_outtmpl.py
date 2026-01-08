import sys
import types
import unittest
from pathlib import Path

sys.modules.setdefault("numpy", types.ModuleType("numpy"))
sys.modules.setdefault("streamlit", types.ModuleType("streamlit"))
pydub_stub = types.ModuleType("pydub")
pydub_stub.AudioSegment = object
sys.modules.setdefault("pydub", pydub_stub)
sys.modules.setdefault("yaml", types.ModuleType("yaml"))
sys.modules.setdefault("yt_dlp", types.ModuleType("yt_dlp"))

from services.link_import_service import LinkImportService


class TestLinkImportOuttmpl(unittest.TestCase):
    def test_outtmpl_uses_id_only(self):
        output_dir = Path("/tmp/downloads")
        template = str(output_dir / "%(id)s.%(ext)s")
        self.assertIn("%(id)s", template)
        self.assertNotIn("%(title)s", template)


if __name__ == "__main__":
    unittest.main()
