import json
import logging
import unittest
from datetime import datetime

from utils.logging_config import JsonLinesFileHandler, LOG_ROOT_DIR, setup_logging


class TestLoggingConfig(unittest.TestCase):
    def test_jsonl_log_created(self):
        setup_logging()
        logger = logging.getLogger("tests.logging")
        logger.info("test log entry")

        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        log_path = LOG_ROOT_DIR / date_str / "app.jsonl"
        self.assertTrue(log_path.exists())

        with open(log_path, "r", encoding="utf-8") as log_file:
            lines = [line.strip() for line in log_file if line.strip()]

        self.assertTrue(lines)
        last_entry = json.loads(lines[-1])
        self.assertIn("timestamp", last_entry)
        self.assertIn("level", last_entry)
        self.assertIn("logger", last_entry)
        self.assertIn("message", last_entry)

    def test_setup_logging_idempotent(self):
        setup_logging()
        setup_logging()
        root_logger = logging.getLogger()

        jsonl_handlers = [
            handler for handler in root_logger.handlers if isinstance(handler, JsonLinesFileHandler)
        ]
        stream_handlers = [
            handler for handler in root_logger.handlers if isinstance(handler, logging.StreamHandler)
        ]
        self.assertEqual(len(jsonl_handlers), 1)
        self.assertEqual(len(stream_handlers), 1)

