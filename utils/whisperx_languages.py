import logging

logger = logging.getLogger(__name__)

LANGUAGE_LABELS = {
    "auto": "Auto",
    "vi": "Việt",
    "en": "Anh",
    "zh": "Trung",
    "yue": "Quảng Đông",
    "ja": "Nhật",
    "ko": "Hàn",
}

LANGUAGE_ALIASES = {
    "auto": None,
    "": None,
    None: None,
    "auto-detect": None,
    "detect": None,
    "vi": "vi",
    "vietnamese": "vi",
    "việt": "vi",
    "việt nam": "vi",
    "en": "en",
    "english": "en",
    "anh": "en",
    "ja": "ja",
    "jp": "ja",
    "japanese": "ja",
    "nhật": "ja",
    "nhat": "ja",
    "ko": "ko",
    "korean": "ko",
    "hàn": "ko",
    "han": "ko",
    "zh": "zh",
    "zh-cn": "zh",
    "zh-tw": "zh",
    "trung": "zh",
    "chinese": "zh",
    "yue": "yue",
    "cantonese": "yue",
    "quảng đông": "yue",
    "quang dong": "yue",
}

VALID_LANGUAGE_CODES = {
    "af",
    "am",
    "ar",
    "as",
    "az",
    "ba",
    "be",
    "bg",
    "bn",
    "bo",
    "br",
    "bs",
    "ca",
    "cs",
    "cy",
    "da",
    "de",
    "el",
    "en",
    "es",
    "et",
    "eu",
    "fa",
    "fi",
    "fo",
    "fr",
    "gl",
    "gu",
    "ha",
    "haw",
    "he",
    "hi",
    "hr",
    "ht",
    "hu",
    "hy",
    "id",
    "is",
    "it",
    "ja",
    "jw",
    "ka",
    "kk",
    "km",
    "kn",
    "ko",
    "la",
    "lb",
    "ln",
    "lo",
    "lt",
    "lv",
    "mg",
    "mi",
    "mk",
    "ml",
    "mn",
    "mr",
    "ms",
    "mt",
    "my",
    "ne",
    "nl",
    "nn",
    "no",
    "oc",
    "pa",
    "pl",
    "ps",
    "pt",
    "ro",
    "ru",
    "sa",
    "sd",
    "si",
    "sk",
    "sl",
    "sn",
    "so",
    "sq",
    "sr",
    "su",
    "sv",
    "sw",
    "ta",
    "te",
    "tg",
    "th",
    "tk",
    "tl",
    "tr",
    "tt",
    "uk",
    "ur",
    "uz",
    "vi",
    "yi",
    "yo",
    "zh",
    "yue",
}

LANGUAGE_OPTION_CODES = [
    "auto",
    "vi",
    "en",
    "zh",
    "yue",
    "ja",
    "ko",
]


def is_valid_whisper_language_code(code: str) -> bool:
    return code in VALID_LANGUAGE_CODES


def normalize_whisper_language(lang_value: str | None) -> str | None:
    if lang_value is None:
        return None
    normalized = str(lang_value).strip().lower()
    alias = LANGUAGE_ALIASES.get(normalized)
    if alias is None:
        if normalized in ("auto", ""):
            return None
        if is_valid_whisper_language_code(normalized):
            return normalized
        logger.warning(
            "Invalid WhisperX language value '%s', fallback to auto",
            lang_value,
        )
        return None
    if alias is None:
        return None
    if is_valid_whisper_language_code(alias):
        return alias
    logger.warning(
        "Mapped WhisperX language '%s' to invalid code '%s', fallback to auto",
        lang_value,
        alias,
    )
    return None
