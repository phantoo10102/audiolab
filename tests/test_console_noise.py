import logging
import unittest
import warnings

from utils.console_noise import configure_console_noise


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
