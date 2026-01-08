def format_srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(seconds * 1000 + 0.5))
    hours = total_ms // 3_600_000
    minutes = (total_ms % 3_600_000) // 60_000
    secs = (total_ms % 60_000) // 1_000
    millis = total_ms % 1_000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def segments_to_srt(segments: list[dict]) -> str:
    blocks = []
    for index, seg in enumerate(segments, start=1):
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        if end < start:
            end = start
        start_ts = format_srt_timestamp(start)
        end_ts = format_srt_timestamp(end)
        text = str(seg.get("text", "")).strip()
        blocks.append(f"{index}\n{start_ts} --> {end_ts}\n{text}")
    return "\n\n".join(blocks) + "\n"
