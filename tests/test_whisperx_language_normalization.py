import unittest

from utils.whisperx_languages import (
    is_valid_whisper_language_code,
    normalize_whisper_language,
)


class TestWhisperxLanguageNormalization(unittest.TestCase):
    def test_normalize_none_and_auto(self):
        self.assertIsNone(normalize_whisper_language(None))
        self.assertIsNone(normalize_whisper_language("Auto"))

    def test_normalize_valid_code(self):
        self.assertEqual(normalize_whisper_language("vi"), "vi")
        self.assertEqual(normalize_whisper_language("en"), "en")

    def test_normalize_label(self):
        self.assertEqual(normalize_whisper_language("Nhật"), "ja")
        self.assertEqual(normalize_whisper_language("Japanese"), "ja")
        self.assertEqual(normalize_whisper_language("Trung"), "zh")

    def test_normalize_invalid(self):
        self.assertIsNone(normalize_whisper_language("Nhãt"))
        self.assertIsNone(normalize_whisper_language("invalid-lang"))

    def test_is_valid_code(self):
        self.assertTrue(is_valid_whisper_language_code("vi"))
        self.assertTrue(is_valid_whisper_language_code("ja"))
        self.assertFalse(is_valid_whisper_language_code("xx"))


if __name__ == "__main__":
    unittest.main()
