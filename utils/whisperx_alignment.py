import re
from typing import Iterable


_SENTENCE_END_RE = re.compile(r"[.!?…。]+$")


def _get_time_value(segment: dict, *keys: str) -> float | None:
    for key in keys:
        value = segment.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None


def _get_segment_times(segment: dict) -> tuple[float, float]:
    start = _get_time_value(segment, "start", "start_time", "startTime") or 0.0
    end = _get_time_value(segment, "end", "end_time", "endTime")
    if end is None or end < start:
        end = start
    return start, end


def _get_word_times(word: dict) -> tuple[float, float]:
    start = _get_time_value(word, "start", "start_time", "startTime") or 0.0
    end = _get_time_value(word, "end", "end_time", "endTime")
    if end is None or end < start:
        end = start
    return start, end


def _word_text(word: dict) -> str:
    return str(word.get("word") or word.get("text") or "").strip()


def _words_from_segments(segments: Iterable[dict]) -> list[dict]:
    words = []
    for seg in segments:
        for word in seg.get("words") or []:
            text = _word_text(word)
            if not text:
                continue
            start, end = _get_word_times(word)
            words.append({"start": start, "end": end, "text": text})
    return words


def _segment_sentences_from_words(words: list[dict]) -> list[dict]:
    output = []
    buffer = []

    def flush():
        if not buffer:
            return
        start = buffer[0]["start"]
        end = buffer[-1]["end"]
        text = " ".join(w["text"] for w in buffer).strip()
        if text:
            output.append({"start": start, "end": end, "text": text})
        buffer.clear()

    for word in words:
        buffer.append(word)
        if _SENTENCE_END_RE.search(word["text"]) or "\n" in word["text"]:
            flush()

    flush()
    return output


def _segment_words_grouped(words: list[dict], group_size: int = 4) -> list[dict]:
    output = []
    for idx in range(0, len(words), group_size):
        chunk = words[idx : idx + group_size]
        start = chunk[0]["start"]
        end = chunk[-1]["end"]
        text = " ".join(w["text"] for w in chunk).strip()
        output.append({"start": start, "end": end, "text": text})
    return output


def _segment_sentences_from_text(segment: dict) -> list[dict]:
    start, end = _get_segment_times(segment)
    text = str(segment.get("text", "")).strip()
    if not text:
        return []
    parts = [p.strip() for p in re.split(r"(?<=[.!?…。])\s+", text) if p.strip()]
    if len(parts) == 1:
        return [{"start": start, "end": end, "text": parts[0]}]

    total_chars = sum(len(p) for p in parts)
    if total_chars <= 0:
        return [{"start": start, "end": end, "text": text}]

    duration = max(0.0, end - start)
    cursor = start
    output = []
    for part in parts:
        ratio = len(part) / total_chars
        part_duration = duration * ratio
        part_end = cursor + part_duration
        output.append({"start": cursor, "end": part_end, "text": part})
        cursor = part_end
    if output:
        output[-1]["end"] = end
    return output


def apply_alignment(segments: list[dict], alignment_level: str) -> list[dict]:
    level = (alignment_level or "Đoạn").strip().lower()
    if level == "đoạn":
        return segments

    words = _words_from_segments(segments)
    if level == "từ":
        if words:
            return _segment_words_grouped(words, group_size=4)
        level = "câu"

    if level == "câu":
        if words:
            return _segment_sentences_from_words(words)
        output = []
        for segment in segments:
            output.extend(_segment_sentences_from_text(segment))
        return output

    return segments
