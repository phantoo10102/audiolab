import io
import sys
import unittest
import warnings
from unittest.mock import Mock

from utils import warnings_config


class TestWarningsConfig(unittest.TestCase):
    def setUp(self):
        self.original_showwarning = warnings.showwarning
        self.original_filters = warnings.filters[:]
        self.original_configured = warnings_config._CONFIGURED
        self.original_console_filter = warnings_config._CONSOLE_FILTER_ATTACHED
        self.original_file_logger = warnings_config._FILE_LOGGER
        self.original_console_suppress = warnings_config._CONSOLE_SUPPRESS

        warnings_config._CONFIGURED = False
        warnings_config._CONSOLE_FILTER_ATTACHED = False
        warnings_config._FILE_LOGGER = None
        warnings_config._CONSOLE_SUPPRESS = True

    def tearDown(self):
        warnings.showwarning = self.original_showwarning
        warnings.filters[:] = self.original_filters
        warnings_config._CONFIGURED = self.original_configured
        warnings_config._CONSOLE_FILTER_ATTACHED = self.original_console_filter
        warnings_config._FILE_LOGGER = self.original_file_logger
        warnings_config._CONSOLE_SUPPRESS = self.original_console_suppress

    def test_suppressed_warning_not_in_stderr(self):
        mock_logger = Mock()
        buffer = io.StringIO()
        original_stderr = sys.stderr
        sys.stderr = buffer
        try:
            warnings_config.configure_warnings(console_suppress=True, file_logger=mock_logger)
            warnings.warn("TRANSFORMERS_CACHE is deprecated", FutureWarning, stacklevel=1)
        finally:
            sys.stderr = original_stderr

        self.assertEqual(buffer.getvalue(), "")

    def test_suppressed_warning_logged_to_file_logger(self):
        mock_logger = Mock()
        warnings_config.configure_warnings(console_suppress=True, file_logger=mock_logger)
        warnings.warn("TRANSFORMERS_CACHE is deprecated", FutureWarning, stacklevel=1)

        mock_logger.warning.assert_called_once()
        args, kwargs = mock_logger.warning.call_args
        self.assertEqual(args[0], "TRANSFORMERS_CACHE is deprecated")
        extra = kwargs.get("extra")
        self.assertIsNotNone(extra)
        self.assertEqual(extra.get("warning_message"), "TRANSFORMERS_CACHE is deprecated")
