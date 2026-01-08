import unittest

from utils.srt_formatter import format_srt_timestamp, segments_to_srt


class TestSrtFormatter(unittest.TestCase):
    def test_format_srt_timestamp_zero(self):
        self.assertEqual(format_srt_timestamp(0), "00:00:00,000")

    def test_format_srt_timestamp_rounding(self):
        self.assertEqual(format_srt_timestamp(1.2345), "00:00:01,235")

    def test_segments_to_srt_blocks(self):
        segments = [
            {"start": 0.0, "end": 1.23, "text": "Hello world."},
            {"start": 1.23, "end": 2.5, "text": "Next line."},
        ]
        expected = (
            "1\n00:00:00,000 --> 00:00:01,230\nHello world.\n\n"
            "2\n00:00:01,230 --> 00:00:02,500\nNext line.\n"
        )
        self.assertEqual(segments_to_srt(segments), expected)

    def test_segments_to_srt_end_before_start(self):
        segments = [{"start": 2.0, "end": 1.0, "text": "Clamp end."}]
        expected = "1\n00:00:02,000 --> 00:00:02,000\nClamp end.\n"
        self.assertEqual(segments_to_srt(segments), expected)


if __name__ == "__main__":
    unittest.main()
