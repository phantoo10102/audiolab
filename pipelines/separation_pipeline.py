import sys
import logging
import subprocess
import os
from pathlib import Path
from typing import Dict, Any, List
from utils.logging_config import get_session_id

logger = logging.getLogger(__name__)


class DemucsPipeline:
    @staticmethod
    def separate(
        input_path: str, output_dir: Path, model_name: str = "htdemucs"
    ) -> Dict[str, Any]:
        """
        Xây dựng và thực thi lệnh Demucs thông qua subprocess.

        Args:
            input_path (str): Đường dẫn đến file audio gốc.
            output_dir (Path): Thư mục chứa kết quả đầu ra.
            model_name (str): Tên model Demucs (vd: htdemucs, htdemucs_ft).

        Returns:
            Dict: Chứa thông tin kết quả, stdout, stderr.
        """
        session_id = get_session_id()

        # Đảm bảo output directory là object Path và đã tồn tại
        if isinstance(output_dir, str):
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

        try:
            # Thực thi lệnh
            # capture_output=True để bắt lấy logs từ Demucs
            # encoding='utf-8', errors='replace' để tránh lỗi charset trên Windows
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"

            result = subprocess.run(
                cmd,
                check=True,
                text=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )

            # Log output từ Demucs (nếu cần debug kỹ hơn thì đổi sang info)
            logger.debug(
                "Demucs subprocess stdout",
                extra={
                    "session_id": session_id,
                    "operation": "demucs_separate",
                    "stdout": result.stdout,
                },
            )

            # Trả về kết quả thành công
            # Lưu ý: Demucs sẽ tạo cấu trúc thư mục: output_dir / model_name / track_name / stem.wav
            # Service layer sẽ chịu trách nhiệm quét (scan) các file này.
            return {
                "success": True,
                "model_name": model_name,
                "raw_stdout": result.stdout,
                "raw_stderr": result.stderr,
            }

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
