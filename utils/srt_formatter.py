def format_srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(seconds * 1000 + 0.5))
    hours = total_ms // 3_600_000
    minutes = (total_ms % 3_600_000) // 60_000
    secs = (total_ms % 60_000) // 1_000
    millis = total_ms % 1_000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _get_time_value(segment: dict, *keys: str) -> float | None:
    for key in keys:
        value = segment.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None


def _normalize_segments(segments: list[dict]) -> list[dict]:
    normalized = []
    for seg in segments:
        start = _get_time_value(seg, "start", "start_time", "startTime")
        end = _get_time_value(seg, "end", "end_time", "endTime")
        normalized.append(
            {
                "start": start if start is not None else 0.0,
                "end": end,
                "text": seg.get("text", ""),
            }
        )

    for idx, seg in enumerate(normalized):
        if seg["end"] is None:
            next_start = None
            if idx + 1 < len(normalized):
                next_start = normalized[idx + 1]["start"]
            seg["end"] = next_start if next_start is not None else seg["start"]
        if seg["end"] < seg["start"]:
            seg["end"] = seg["start"]

    return normalized


def segments_to_srt(segments: list[dict]) -> str:
    blocks = []
    normalized = _normalize_segments(segments)
    for index, seg in enumerate(normalized, start=1):
        start_ts = format_srt_timestamp(seg["start"])
        end_ts = format_srt_timestamp(seg["end"])
        text = str(seg.get("text", "")).strip()
        blocks.append(f"{index}\n{start_ts} --> {end_ts}\n{text}")
    return "\n\n".join(blocks) + "\n"
