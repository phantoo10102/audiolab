import math
import re
from typing import Iterable


_CJK_PUNCT = set("。！？；，、")
_ASCII_PUNCT = set(".!?;,:")
_SENTENCE_PUNCT = set("。！？?!")
_MID_PUNCT = set(";；")
_COMMA_PUNCT = set(",，、")
_ALL_PUNCT = _CJK_PUNCT | _ASCII_PUNCT


def is_cjk_lang(lang_code: str | None) -> bool:
    if not lang_code:
        return False
    code = str(lang_code).strip().lower()
    return code.startswith(("zh", "ja", "ko"))


def _clean_text(text: str, *, lang: str | None) -> str:
    if not text:
        return ""
    if is_cjk_lang(lang):
        return "".join(text.split())
    return " ".join(text.split())


def wrap_lines(
    text: str,
    *,
    lang: str | None,
    max_chars_per_line_non_cjk: int = 42,
    max_chars_per_line_cjk: int = 20,
    max_lines: int = 2,
) -> str:
    cleaned = _clean_text(text, lang=lang)
    if not cleaned:
        return ""

    if is_cjk_lang(lang):
        max_chars = max_chars_per_line_cjk
        lines = []
        line = ""
        last_punct = -1

        def _find_last_punct(s: str) -> int:
            for idx in range(len(s) - 1, -1, -1):
                if s[idx] in _ALL_PUNCT:
                    return idx
            return -1

        for ch in cleaned:
            line += ch
            if ch in _ALL_PUNCT:
                last_punct = len(line) - 1
            if len(line) >= max_chars:
                if last_punct >= int(max_chars * 0.6):
                    split_at = last_punct + 1
                else:
                    split_at = max_chars
                lines.append(line[:split_at])
                line = line[split_at:]
                last_punct = _find_last_punct(line)

        if line:
            lines.append(line)
    else:
        max_chars = max_chars_per_line_non_cjk
        words = cleaned.split(" ")
        lines = []
        line = ""
        for word in words:
            if not line:
                candidate = word
            else:
                candidate = f"{line} {word}"
            if len(candidate) <= max_chars:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)

    if len(lines) > max_lines:
        head = lines[: max_lines - 1]
        tail = " ".join(lines[max_lines - 1 :]).strip()
        lines = head + ([tail] if tail else [])

    return "\n".join([ln.strip() for ln in lines if ln.strip()])


def _text_length(text: str, *, lang: str | None) -> int:
    if is_cjk_lang(lang):
        return len("".join(text.split()))
    return len(text.strip())


def _ends_with_punct(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and stripped[-1] in _ALL_PUNCT


def _split_by_punctuation(text: str, punct_set: Iterable[str]) -> list[str]:
    chunks = []
    current = ""
    for ch in text:
        current += ch
        if ch in punct_set:
            if current.strip():
                chunks.append(current.strip())
            current = ""
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _split_by_length(text: str, *, lang: str | None, max_len: int) -> list[str]:
    if max_len <= 0:
        return [text]
    if is_cjk_lang(lang):
        chars = "".join(text.split())
        return [chars[i : i + max_len] for i in range(0, len(chars), max_len)]

    words = text.split()
    chunks = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if not line or len(candidate) <= max_len:
            line = candidate
        else:
            chunks.append(line)
            line = word
    if line:
        chunks.append(line)
    return chunks


def _join_words(words: list[dict]) -> str:
    parts = []
    for word in words:
        token = str(word.get("word", ""))
        parts.append(token)
    return "".join(parts).strip()


def _allocate_times(
    chunks: list[str],
    *,
    start: float,
    end: float,
    lang: str | None,
) -> list[dict]:
    total_duration = max(0.0, end - start)
    lengths = [_text_length(chunk, lang=lang) or 1 for chunk in chunks]
    total_length = sum(lengths) or 1
    current = start
    results = []
    for idx, (chunk, length) in enumerate(zip(chunks, lengths)):
        if idx == len(chunks) - 1:
            chunk_end = end
        else:
            chunk_duration = total_duration * (length / total_length)
            chunk_end = current + chunk_duration
        results.append({"start": current, "end": chunk_end, "text": chunk})
        current = chunk_end
    return results


def split_segment(
    segment: dict,
    *,
    lang: str | None,
    max_duration_s: float = 6.0,
    min_duration_s: float = 1.0,
    target_max_cps: int = 18,
    prefer_punctuation: bool = True,
    max_chars_per_line_non_cjk: int = 42,
    max_chars_per_line_cjk: int = 20,
) -> list[dict]:
    start = float(segment.get("start", 0.0) or 0.0)
    end = float(segment.get("end", start) or start)
    text = str(segment.get("text", "")).strip()
    if not text:
        return [{"start": start, "end": end, "text": ""}]

    duration = max(0.0, end - start)
    length = _text_length(text, lang=lang) or 1
    cps = length / duration if duration > 0 else length

    if duration <= max_duration_s and cps <= target_max_cps:
        return [{"start": start, "end": end, "text": text}]

    words = segment.get("words")
    if isinstance(words, list) and words:
        segments = []
        current_words = []
        current_start = start
        for word in words:
            if word is None:
                continue
            word_start = word.get("start", current_start)
            word_end = word.get("end", word_start)
            if not current_words:
                current_start = max(start, float(word_start or start))
            current_words.append(word)
            current_end = float(word_end or current_start)
            chunk_duration = current_end - current_start
            if chunk_duration <= 0:
                continue
            if (
                chunk_duration >= max_duration_s
                or (
                    prefer_punctuation
                    and _ends_with_punct(str(word.get("word", "")))
                    and chunk_duration >= min_duration_s
                )
            ):
                segments.append(
                    {
                        "start": current_start,
                        "end": min(current_end, end),
                        "text": _join_words(current_words),
                    }
                )
                current_words = []
                current_start = min(current_end, end)
        if current_words:
            segments.append(
                {
                    "start": current_start,
                    "end": end,
                    "text": _join_words(current_words),
                }
            )

        return segments

    cleaned = _clean_text(text, lang=lang)
    chunks = [cleaned]
    if prefer_punctuation:
        chunks = _split_by_punctuation(cleaned, _SENTENCE_PUNCT)
        if len(chunks) == 1:
            chunks = _split_by_punctuation(cleaned, _MID_PUNCT) or chunks
        if len(chunks) == 1:
            chunks = _split_by_punctuation(cleaned, _COMMA_PUNCT) or chunks

    total_length = sum(_text_length(chunk, lang=lang) for chunk in chunks) or 1
    required_segments = max(1, int(math.ceil(duration / max_duration_s)))
    max_chunk_len = max(1, int(math.ceil(total_length / required_segments)))
    if is_cjk_lang(lang):
        max_chunk_len = min(max_chunk_len, max_chars_per_line_cjk)
    else:
        max_chunk_len = min(max_chunk_len, max_chars_per_line_non_cjk)

    refined = []
    for chunk in chunks:
        chunk_len = _text_length(chunk, lang=lang)
        if chunk_len > max_chunk_len:
            refined.extend(_split_by_length(chunk, lang=lang, max_len=max_chunk_len))
        else:
            refined.append(chunk)

    while len(refined) < required_segments:
        idx = max(range(len(refined)), key=lambda i: _text_length(refined[i], lang=lang))
        longest = refined.pop(idx)
        split_parts = _split_by_length(longest, lang=lang, max_len=max_chunk_len)
        refined[idx:idx] = split_parts

    return _allocate_times(refined, start=start, end=end, lang=lang)


def postprocess_subtitle_segments(
    segments: list,
    *,
    lang: str | None,
    max_duration_s: float = 6.0,
    min_duration_s: float = 1.0,
    target_max_cps: int = 18,
    max_chars_per_line_non_cjk: int = 42,
    max_chars_per_line_cjk: int = 20,
    max_lines: int = 2,
) -> list[dict]:
    processed: list[dict] = []
    for seg in segments or []:
        for split in split_segment(
            seg,
            lang=lang,
            max_duration_s=max_duration_s,
            min_duration_s=min_duration_s,
            target_max_cps=target_max_cps,
            max_chars_per_line_non_cjk=max_chars_per_line_non_cjk,
            max_chars_per_line_cjk=max_chars_per_line_cjk,
        ):
            wrapped = wrap_lines(
                split.get("text", ""),
                lang=lang,
                max_chars_per_line_non_cjk=max_chars_per_line_non_cjk,
                max_chars_per_line_cjk=max_chars_per_line_cjk,
                max_lines=max_lines,
            )
            processed.append(
                {
                    "start": split.get("start", 0.0),
                    "end": split.get("end", 0.0),
                    "text": wrapped,
                }
            )
    return processed
