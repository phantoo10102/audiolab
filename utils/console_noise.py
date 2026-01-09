import importlib
import importlib.util
import logging
import warnings


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

    if importlib.util.find_spec("pyannote") is not None:
        spec = importlib.util.find_spec("pyannote.audio.utils.reproducibility")
        if spec is not None:
            module = importlib.import_module("pyannote.audio.utils.reproducibility")
            warnings.filterwarnings("ignore", category=module.ReproducibilityWarning)

    logging.getLogger("speechbrain.utils.checkpoints").setLevel(logging.WARNING)
    logging.getLogger("speechbrain").setLevel(logging.INFO)
    logging.getLogger("streamlit").setLevel(logging.WARNING)
    logging.getLogger("streamlit.watcher").setLevel(logging.ERROR)
    logging.getLogger("lightning_fabric").setLevel(logging.WARNING)
