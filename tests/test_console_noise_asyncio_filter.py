import asyncio
import logging
import unittest

from utils import console_noise


class TestAsyncioCancelledErrorFilter(unittest.TestCase):
    def setUp(self):
        console_noise._mark_shutdown()

    def test_filters_tornado_cancelled_during_shutdown(self):
        filt = console_noise.AsyncioCancelledErrorFilter()
        record = logging.LogRecord(
            name="asyncio",
            level=logging.ERROR,
            pathname=__file__,
            lineno=10,
            msg="Exception in callback tornado.web.RequestHandler._execute",
            args=(),
            exc_info=(
                asyncio.CancelledError,
                asyncio.CancelledError(),
                None,
            ),
        )
        self.assertFalse(filt.filter(record))

    def test_allows_non_cancelled_errors(self):
        filt = console_noise.AsyncioCancelledErrorFilter()
        record = logging.LogRecord(
            name="asyncio",
            level=logging.ERROR,
            pathname=__file__,
            lineno=20,
            msg="Unexpected error",
            args=(),
            exc_info=(RuntimeError, RuntimeError("boom"), None),
        )
        self.assertTrue(filt.filter(record))


if __name__ == "__main__":
    unittest.main()
