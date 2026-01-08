import unittest

from utils.whisperx_alignment import apply_alignment


class TestWhisperXAlignment(unittest.TestCase):
    def test_alignment_doan_passthrough(self):
        segments = [{"start": 0.0, "end": 2.0, "text": "Hello world."}]
        self.assertEqual(apply_alignment(segments, "Đoạn"), segments)

    def test_alignment_cau_splits_sentences(self):
        segments = [
            {"start": 0.0, "end": 3.0, "text": "Hello world. How are you? Fine."}
        ]
        result = apply_alignment(segments, "Câu")
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["text"], "Hello world.")
        self.assertEqual(result[1]["text"], "How are you?")
        self.assertEqual(result[2]["text"], "Fine.")
        self.assertGreaterEqual(result[0]["end"], result[0]["start"])

    def test_alignment_tu_uses_words(self):
        segments = [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "Hello world",
                "words": [
                    {"word": "Hello", "start": 0.0, "end": 0.5},
                    {"word": "world", "start": 0.5, "end": 1.0},
                ],
            }
        ]
        result = apply_alignment(segments, "Từ")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "Hello world")
        self.assertEqual(result[0]["start"], 0.0)
        self.assertEqual(result[0]["end"], 1.0)

    def test_alignment_tu_fallback_without_words(self):
        segments = [{"start": 0.0, "end": 2.0, "text": "Hello. World."}]
        result = apply_alignment(segments, "Từ")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["text"], "Hello.")
        self.assertEqual(result[1]["text"], "World.")


if __name__ == "__main__":
    unittest.main()
