import asyncio
import logging
import unittest
import warnings

from utils.console_noise import configure_console_noise, AsyncioCancellationFilter


class ConsoleNoiseConfigTests(unittest.TestCase):
    def test_configure_console_noise_runs(self):
        configure_console_noise()

    def test_speechbrain_checkpoint_logger_level(self):
        configure_console_noise()
        logger = logging.getLogger("speechbrain.utils.checkpoints")
        self.assertGreaterEqual(logger.getEffectiveLevel(), logging.WARNING)

    def test_warning_filters_suppress_expected_messages(self):
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            configure_console_noise()
            warnings.warn("pkg_resources is deprecated as an API", UserWarning)
            warnings.warn(
                "You are using `torch.load` with `weights_only=False`",
                UserWarning,
            )

            self.assertEqual(captured, [])

    def test_asyncio_cancelled_error_filtered(self):
        filt = AsyncioCancellationFilter()
        record = logging.LogRecord(
            name="asyncio",
            level=logging.ERROR,
            pathname=__file__,
            lineno=10,
            msg="Exception in callback",
            args=(),
            exc_info=(asyncio.CancelledError, asyncio.CancelledError(), None),
        )
        self.assertFalse(filt.filter(record))

    def test_asyncio_non_cancelled_error_allowed(self):
        filt = AsyncioCancellationFilter()
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

    def test_asyncio_message_cancelled_error_filtered(self):
        filt = AsyncioCancellationFilter()
        record = logging.LogRecord(
            name="asyncio",
            level=logging.ERROR,
            pathname=__file__,
            lineno=30,
            msg="asyncio.exceptions.CancelledError",
            args=(),
            exc_info=None,
        )
        self.assertFalse(filt.filter(record))
