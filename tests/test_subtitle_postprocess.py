import unittest

from utils.subtitle_postprocess import postprocess_subtitle_segments


class TestSubtitlePostprocess(unittest.TestCase):
    def test_cjk_long_segment_splits_and_wraps(self):
        text = (
            "好的，我们今天要讨论一下这个问题，因为这个问题真的很重要，"
            "如果你现在不理解，之后可能会很麻烦。你准备好了吗？"
            "请认真听，我会尽量讲清楚，并且给出一些例子。"
        )
        segment = {"start": 0.368, "end": 29.630, "text": text}

        processed = postprocess_subtitle_segments([segment], lang="zh")
        self.assertGreater(len(processed), 3)

        self.assertAlmostEqual(processed[0]["start"], segment["start"], places=3)
        self.assertAlmostEqual(processed[-1]["end"], segment["end"], places=3)

        for idx, seg in enumerate(processed):
            if idx > 0:
                self.assertGreaterEqual(seg["start"], processed[idx - 1]["end"])
            duration = seg["end"] - seg["start"]
            self.assertLessEqual(duration, 6.0 + 2.0)
            lines = seg["text"].splitlines() if seg["text"] else [""]
            self.assertLessEqual(len(lines), 2)
            for line in lines:
                self.assertLessEqual(len(line), 20)

    def test_non_cjk_long_segment_splits_or_wraps(self):
        text = (
            "this is a long run on example without much punctuation and it keeps "
            "going to simulate a subtitle cue that is far too long for any viewer "
            "to read comfortably in a single block of text"
        )
        segment = {"start": 21.783, "end": 41.780, "text": text}

        processed = postprocess_subtitle_segments([segment], lang="en")
        self.assertGreaterEqual(len(processed), 1)

        for seg in processed:
            duration = seg["end"] - seg["start"]
            self.assertLessEqual(duration, 8.0)
            for line in seg["text"].splitlines():
                self.assertEqual(line, line.strip())
            for idx, char in enumerate(seg["text"]):
                if char == "\n":
                    before = seg["text"][idx - 1] if idx > 0 else ""
                    after = seg["text"][idx + 1] if idx + 1 < len(seg["text"]) else ""
                    self.assertFalse(before.isalpha() and after.isalpha())

    def test_word_timestamp_path_split(self):
        words = []
        for idx in range(24):
            words.append(
                {
                    "start": idx * 0.5,
                    "end": (idx + 1) * 0.5,
                    "word": f"word{idx} ",
                }
            )
        segment = {
            "start": 0.0,
            "end": 12.0,
            "text": " ".join(f"word{idx}" for idx in range(24)),
            "words": words,
        }

        processed = postprocess_subtitle_segments([segment], lang="en")
        boundaries = {w["start"] for w in words} | {w["end"] for w in words}

        for seg in processed:
            duration = seg["end"] - seg["start"]
            self.assertLessEqual(duration, 6.0)
            self.assertTrue(
                any(abs(seg["start"] - b) < 1e-3 for b in boundaries)
            )
            self.assertTrue(
                any(abs(seg["end"] - b) < 1e-3 for b in boundaries)
            )

    def test_cjk_trailing_single_char_repair(self):
        text = (
            "我身体不太好,天气太热了,不爱吃饭你多吃些水果,多喝水谢谢你,医生昨天北京的天气怎么样?"
        )
        segment = {"start": 0.0, "end": 18.0, "text": text}

        processed = postprocess_subtitle_segments([segment], lang="zh")

        for idx in range(len(processed) - 1):
            prev_text = processed[idx]["text"]
            next_text = processed[idx + 1]["text"]
            self.assertFalse(prev_text.endswith("你") and next_text.startswith("多"))
            self.assertFalse(prev_text.endswith("北") and next_text.startswith("京"))

        combined = "".join(seg["text"] for seg in processed)
        self.assertIn("你多吃些水果", combined)
        self.assertIn("北京的天气", combined)

        for idx, seg in enumerate(processed):
            self.assertTrue(seg["text"])
            if idx > 0:
                self.assertGreaterEqual(seg["start"], processed[idx - 1]["end"])

    def test_monotonic_timecodes_across_segments(self):
        segments = [
            {
                "start": 0.0,
                "end": 8.0,
                "text": "This should split into multiple lines because it is long.",
            },
            {
                "start": 8.0,
                "end": 14.0,
                "text": "Second segment stays after the first segment.",
            },
        ]

        processed = postprocess_subtitle_segments(segments, lang="en")

        for idx, seg in enumerate(processed):
            self.assertLessEqual(seg["start"], seg["end"])
            if idx > 0:
                self.assertGreaterEqual(seg["start"], processed[idx - 1]["end"])


if __name__ == "__main__":
    unittest.main()
