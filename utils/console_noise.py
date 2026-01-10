import atexit
import asyncio
import logging
import warnings


_SHUTTING_DOWN = False


class AsyncioCancelledErrorFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not _SHUTTING_DOWN:
            return True
        if record.name != "asyncio":
            return True
        if not record.exc_info:
            return True
        exc = record.exc_info[1]
        if not isinstance(exc, asyncio.CancelledError):
            return True
        message = record.getMessage()
        if "tornado.web" in message or "tornado.web.py" in message:
            return False
        return True


def _mark_shutdown() -> None:
    global _SHUTTING_DOWN
    _SHUTTING_DOWN = True


def configure_console_noise() -> None:
    atexit.register(_mark_shutdown)
    warnings.filterwarnings(
        "ignore",
        message=r"Thread 'ThreadPoolExecutor-.*missing ScriptRunContext!.*",
    )
    warnings.filterwarnings(
        "ignore",
        message=r"pkg_resources is deprecated as an API",
    )
    warnings.filterwarnings(
        "ignore",
        message=r"You are using `torch.load` with `weights_only=False`.*",
    )
    warnings.filterwarnings(
        "ignore",
        message=r"Torchaudio's I/O functions now support.*",
    )
    warnings.filterwarnings(
        "ignore",
        message=r"Module 'speechbrain\.pretrained' was deprecated, redirecting to 'speechbrain\.inference'.*",
    )

    warnings.filterwarnings(
    "ignore",
    message=r".*ReproducibilityWarning: TensorFloat-32 \(TF32\) has been disabled.*",
)

    logging.getLogger("speechbrain.utils.checkpoints").setLevel(logging.WARNING)
    logging.getLogger("speechbrain").setLevel(logging.INFO)
    logging.getLogger("streamlit").setLevel(logging.WARNING)
    logging.getLogger("streamlit.watcher").setLevel(logging.ERROR)
    logging.getLogger("lightning_fabric").setLevel(logging.WARNING)
    logging.getLogger("asyncio").addFilter(AsyncioCancelledErrorFilter())
