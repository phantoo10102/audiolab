import inspect
import logging
import os
import re
import warnings
from dataclasses import dataclass
from typing import Pattern

from utils.logging_config import JSONL_LOGGER_NAME


@dataclass(frozen=True)
class WarningRule:
    message: Pattern[str]
    category: type[Warning] | None = None
    module: Pattern[str] | None = None


SUPPRESSED_WARNING_RULES = (
    WarningRule(re.compile(r"^Module 'speechbrain\.pretrained' was deprecated"), UserWarning),
    WarningRule(re.compile(r"multiple ModelCheckpoint callback states"), UserWarning),
    WarningRule(re.compile(r"Lightning automatically upgraded your loaded checkpoint"), UserWarning),
    WarningRule(re.compile(r"TF32 has been disabled"), UserWarning),
    WarningRule(re.compile(r"torch\.load with weights_only=False"), FutureWarning),
    WarningRule(
        re.compile(r"backend.*dispatcher", re.IGNORECASE),
        UserWarning,
        re.compile(r"(torchaudio|streamlit[./]watcher)")
    ),
    WarningRule(re.compile(r"pkg_resources is deprecated as an API"), DeprecationWarning),
    WarningRule(re.compile(r"TRANSFORMERS_CACHE is deprecated"), FutureWarning),
)


_CONFIGURED = False
_ORIGINAL_SHOWWARNING = warnings.showwarning
_CONSOLE_FILTER_ATTACHED = False
_FILE_LOGGER: logging.Logger | None = None
_CONSOLE_SUPPRESS = True


class _StreamlitScriptRunContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != "streamlit.runtime.scriptrunner":
            return True
        message = record.getMessage()
        return "missing ScriptRunContext!" not in message


def _matches_rule(
    message: str,
    category: type[Warning],
    module: str,
    rules: tuple[WarningRule, ...] = SUPPRESSED_WARNING_RULES,
) -> bool:
    for rule in rules:
        if rule.category is not None and not issubclass(category, rule.category):
            continue
        if rule.module is not None and not rule.module.search(module):
            continue
        if rule.message.search(message):
            return True
    return False


def _build_warning_extra(
    category: type[Warning],
    filename: str,
    lineno: int,
    module: str,
    message: str,
) -> dict[str, str | int]:
    return {
        "warning_category": category.__name__,
        "warning_filename": filename,
        "warning_lineno": lineno,
        "warning_module": module,
        "warning_message": message,
    }


def _custom_showwarning(message, category, filename, lineno, file=None, line=None):
    msg_text = str(message)
    module_name = inspect.getmodulename(filename) or ""
    module_match_target = filename
    module_field = module_name or filename
    if _FILE_LOGGER is not None:
        _FILE_LOGGER.warning(
            msg_text,
            extra=_build_warning_extra(category, filename, lineno, module_field, msg_text),
        )

    if not _CONSOLE_SUPPRESS:
        _ORIGINAL_SHOWWARNING(message, category, filename, lineno, file=file, line=line)
        return

    if _matches_rule(msg_text, category, module_match_target):
        return

    _ORIGINAL_SHOWWARNING(message, category, filename, lineno, file=file, line=line)


def _attach_streamlit_console_filter() -> None:
    global _CONSOLE_FILTER_ATTACHED
    if _CONSOLE_FILTER_ATTACHED:
        return
    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.addFilter(_StreamlitScriptRunContextFilter())
    _CONSOLE_FILTER_ATTACHED = True


def configure_warnings(
    console_suppress: bool = True,
    file_logger: logging.Logger | None = None,
) -> None:
    global _CONFIGURED, _FILE_LOGGER, _CONSOLE_SUPPRESS
    if os.environ.get("SHOW_WARNINGS") == "1":
        console_suppress = False

    if _CONFIGURED and _CONSOLE_SUPPRESS == console_suppress and file_logger is _FILE_LOGGER:
        return

    if file_logger is None:
        file_logger = logging.getLogger(JSONL_LOGGER_NAME)

    _FILE_LOGGER = file_logger
    _CONSOLE_SUPPRESS = console_suppress
    warnings.showwarning = _custom_showwarning

    if not _CONFIGURED:
        warnings.filterwarnings("default")
        for rule in SUPPRESSED_WARNING_RULES:
            warnings.filterwarnings(
                "always",
                message=rule.message.pattern,
                category=rule.category or Warning,
                module=rule.module.pattern if rule.module is not None else "",
            )

        _attach_streamlit_console_filter()
        _CONFIGURED = True
