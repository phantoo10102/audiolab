import os
import logging
import time
import random
import socket
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.error import URLError

import yt_dlp

# Import Constants & Config
from utils.constants import DATA_DOWNLOAD_DIR
from utils.logging_config import get_session_id

logger = logging.getLogger(__name__)


class LinkImportService:

    @staticmethod
    def _is_retryable_error(e: Exception) -> bool:
        """
        Helper: Kiểm tra xem lỗi có phải là tạm thời (mạng, timeout) hay không.
        """
        # 1. Lỗi mạng cơ bản
        if isinstance(e, (socket.timeout, URLError, ConnectionError, TimeoutError)):
            return True

        # 2. Phân tích chuỗi lỗi
        msg = str(e).lower()

        # HTTP Status tạm thời
        if "429" in msg or "too many requests" in msg:
            return True
        if "500" in msg or "502" in msg or "503" in msg or "504" in msg:
            return True

        # Từ khóa lỗi mạng yt-dlp
        retry_keywords = [
            "timeout",
            "connection reset",
            "timed out",
            "network is unreachable",
            "temporary failure",
            "content too short",
            "did not get any data",
        ]
        return any(kw in msg for kw in retry_keywords)

    @staticmethod
    def download_audio_from_url(
        url: str,
        output_dir: Path = DATA_DOWNLOAD_DIR,  # [FIX BUG-010] Default to Download dir
    ) -> Path:
        """
        Tải audio từ URL (YouTube, TikTok...).
        Tích hợp: Security Check, Retry Logic, Logging.
        """
        session_id = get_session_id()

        # --- [FIX BUG-10] SECURITY CHECKS ---
        ALLOWED_DOMAINS = [
            "youtube.com",
            "youtu.be",
            "m.youtube.com",
            "tiktok.com",
            "vt.tiktok.com",
            "vm.tiktok.com",
            "soundcloud.com",
        ]
        BLOCKED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

        try:
            parsed = urlparse(url)
            # 1. Validate Scheme
            if parsed.scheme not in ["http", "https"]:
                raise ValueError(f"Only HTTP/HTTPS allowed, got: {parsed.scheme}://")

            # 2. Validate Domain Whitelist
            domain = parsed.netloc.lower()
            if not any(allowed in domain for allowed in ALLOWED_DOMAINS):
                raise ValueError(
                    f"Domain '{domain}' not supported. Allowed: {', '.join(ALLOWED_DOMAINS)}"
                )

            # 3. Block Localhost (SSRF Protection)
            if any(blocked in domain for blocked in BLOCKED_HOSTS):
                logger.warning(
                    "Blocked localhost access attempt",
                    extra={"url": url, "session_id": session_id},
                )
                raise ValueError("Local URLs not permitted")

        except ValueError as e:
            logger.error(
                f"URL Validation failed: {e}",
                extra={"url": url, "session_id": session_id},
            )
            raise e

        # --- SETUP DIRECTORY ---
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)

        # --- YT-DLP CONFIG ---
        temp_filename_tpl = str(output_dir / "%(id)s.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": temp_filename_tpl,
            "socket_timeout": 30,  # [FIX BUG-020] Timeout mạng 30s
            "retries": 0,  # Tắt retry ngầm để tự quản lý
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }

        # --- RETRY LOGIC (Exponential Backoff) ---
        max_retries = 3
        base_delay = 2.0
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt}/{max_retries} for {url}")

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # 1. Extract Info & Download
                    info = ydl.extract_info(url, download=True)

                    # 2. Determine Final Path
                    # yt-dlp prepare_filename trả về tên gốc (ví dụ .webm),
                    # nhưng postprocessor đã đổi thành .mp3
                    original_path = ydl.prepare_filename(info)
                    final_path = Path(original_path).with_suffix(".mp3")

                    # Save title metadata for display/debug (sidecar)
                    try:
                        title_path = final_path.with_suffix(".json")
                        title_payload = {
                            "id": info.get("id", ""),
                            "title": info.get("title", ""),
                            "source_url": url,
                        }
                        title_path.write_text(
                            json.dumps(title_payload, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                    except Exception:
                        pass

                    # Fallback scan nếu tên file có ký tự lạ
                    if not final_path.exists():
                        video_id = info.get("id", "")
                        candidates = list(output_dir.glob(f"*{video_id}*.mp3"))
                        if candidates:
                            final_path = candidates[0]

                    if not final_path.exists():
                        raise FileNotFoundError(
                            "Download reported success but file missing."
                        )

                    # Success Log
                    logger.info(
                        "Download success",
                        extra={
                            "session_id": session_id,
                            "url": url,
                            "file": final_path.name,
                        },
                    )
                    return final_path

            except Exception as e:
                last_exception = e

                # Check Retry Eligibility
                if attempt < max_retries and LinkImportService._is_retryable_error(e):
                    wait_time = base_delay * (2**attempt)
                    # Jitter (0-50%)
                    jitter = wait_time * (0.5 + random.random() * 0.5)

                    logger.warning(
                        f"Download transient error. Retrying in {jitter:.1f}s...",
                        extra={"error": str(e), "attempt": attempt + 1},
                    )
                    time.sleep(jitter)
                else:
                    # Fatal error or max retries reached
                    logger.error(
                        f"Download failed permanently: {str(e)}",
                        extra={"url": url, "session_id": session_id},
                    )
                    raise e

        # Should not be reached
        raise last_exception
