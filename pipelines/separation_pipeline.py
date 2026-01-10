import concurrent.futures
import logging
import os
import subprocess
import sys
import time
from pathlib import Path 
from typing import List

from state.schemas import SeparationArtifacts 
from typing import Dict, Any, List
 
from utils.logging_config import get_session_id

logger = logging.getLogger(__name__)


_ALLOWED_STEM_NAMES = {"vocals", "drums", "bass", "other"}
_MIN_STEM_COUNT = 2


def _select_wav_files(stem_dir: Path) -> List[Path]:
    wav_files = list(stem_dir.glob("*.wav"))
    if not wav_files:
        return []
    preferred = [
        wav_path
        for wav_path in wav_files
        if wav_path.stem.lower() in _ALLOWED_STEM_NAMES
    ]
    return preferred or wav_files


def _find_best_stem_dir(model_dir: Path, run_start_ts: float) -> Path | None:
    if not model_dir.exists():
        return None

    candidates = [p for p in model_dir.iterdir() if p.is_dir()]
    if not candidates:
        return None

    recent_candidates = [p for p in candidates if p.stat().st_mtime >= run_start_ts]
    scan_candidates = recent_candidates or candidates

    def score_dir(path: Path) -> tuple[int, float]:
        stem_count = len(_select_wav_files(path))
        return (stem_count, path.stat().st_mtime)

    scored = [(path, score_dir(path)) for path in scan_candidates]
    filtered = [(path, score) for path, score in scored if score[0] >= _MIN_STEM_COUNT]
    best_pool = filtered or scored
    if not best_pool:
        return None
    return max(best_pool, key=lambda item: item[1])[0]


def _resolve_stem_dir(
    output_dir: Path, model_name: str, input_path: Path, run_start_ts: float
) -> Path | None:
    expected_stem_dir = output_dir / model_name / input_path.stem
    if expected_stem_dir.exists():
        return expected_stem_dir

    model_dir = output_dir / model_name
    return _find_best_stem_dir(model_dir, run_start_ts)


class DemucsPipeline:
    @staticmethod
    def separate(
        input_path: str | Path,
        output_dir: str | Path,
        model_name: str = "htdemucs",
        cancel_event=None,
    ) -> SeparationArtifacts:
        """
        Xây dựng và thực thi lệnh Demucs thông qua subprocess.

        Args:
            input_path (Path): Đường dẫn đến file audio gốc.
            output_dir (Path): Thư mục chứa kết quả đầu ra.
            model_name (str): Tên model Demucs (vd: htdemucs, htdemucs_ft).

        Returns:
            SeparationArtifacts: Output artifacts and stem paths.
        """
        session_id = get_session_id()
        input_path = Path(input_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # [FIX BUG-SEPARATION-PATH] Chuyển đổi Path object sang string.
        # Hàm 'join' và subprocess trên Windows yêu cầu tham số là string thuần túy.
        cmd = [
            sys.executable,  # Python interpreter hiện tại
            "-m",
            "demucs.separate",  # Module Demucs
            "-n",
            model_name,
            "-o",
            str(output_dir),  # [FIX] Convert WindowsPath -> str
            str(input_path),  # [FIX] Convert WindowsPath -> str
            "--filename",
            "{track}/{stem}.{ext}",  # Format tên file đầu ra
            # Tùy chọn thêm để tối ưu cho server (không dùng GPU nếu không có CUDA, v.v. - tùy chỉnh sau)
            # "--device", "cpu"
        ]

        # Log lệnh sẽ chạy (dạng string để dễ debug)
        logger.info(
            "Executing Demucs subprocess",
            extra={
                "session_id": session_id,
                "operation": "demucs_separate",
                "model": model_name,
                "command": str(cmd),  # hoặc " ".join(cmd)
            },
        )

        run_start_ts = time.time()

        try:
            # Thực thi lệnh
            # capture_output=True để bắt lấy logs từ Demucs
            # encoding='utf-8', errors='replace' để tránh lỗi charset trên Windows
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"

            process = subprocess.Popen(
                cmd,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                errors="replace",
                env=env,
            )

            while True:
                if cancel_event and cancel_event.is_set():
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    raise concurrent.futures.CancelledError(
                        "Demucs subprocess cancelled"
                    )
                if process.poll() is not None:
                    break
                time.sleep(0.1)

            stdout, stderr = process.communicate()
            if process.returncode != 0:
                raise subprocess.CalledProcessError(
                    process.returncode, cmd, output=stdout, stderr=stderr
                )

            # Log output từ Demucs (nếu cần debug kỹ hơn thì đổi sang info)
            logger.debug(
                "Demucs subprocess stdout",
                extra={
                    "session_id": session_id,
                    "operation": "demucs_separate",
                    "stdout": stdout,
                },
            )

            stem_dir = _resolve_stem_dir(output_dir, model_name, input_path, run_start_ts)
            stem_paths = _select_wav_files(stem_dir) if stem_dir else []

            return SeparationArtifacts(
                model_name=model_name,
                input_path=input_path,
                output_dir=output_dir,
                stem_paths=stem_paths,
            )

        except subprocess.CalledProcessError as e:
            # Log lỗi chi tiết nếu subprocess thất bại (exit code != 0)
            logger.error(
                "Demucs subprocess failed",
                extra={
                    "session_id": session_id,
                    "operation": "demucs_separate",
                    "exit_code": e.returncode,
                    "stderr": e.stderr,
                },
            )
            logger.error(f"Demucs stderr: {e.stderr}")

            raise RuntimeError(f"Demucs processing failed: {e.stderr}")

        except concurrent.futures.CancelledError:
            logger.info(
                "Demucs subprocess cancelled",
                extra={
                    "session_id": session_id,
                    "operation": "demucs_separate",
                },
            )
            raise

        except Exception as e:
            # Bắt các lỗi khác (ví dụ: không tìm thấy executable, lỗi permission)
            logger.error(
                "Unexpected error running Demucs",
                extra={
                    "session_id": session_id,
                    "operation": "demucs_separate",
                    "error": str(e),
                },
                exc_info=True,
            )
            raise e
