import asyncio
import logging
import warnings


class AsyncioCancellationFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != "asyncio":
            return True
        exc_info = record.exc_info
        if exc_info and isinstance(exc_info[1], asyncio.CancelledError):
            return False
        message = record.getMessage()
        if "CancelledError" in message:
            return False
        return True


def configure_console_noise() -> None:
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
    logging.getLogger("asyncio").addFilter(AsyncioCancellationFilter())
