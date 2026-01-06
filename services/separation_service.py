import os
import logging
import time
from pathlib import Path
from typing import Dict, Any, List

from pydub import AudioSegment  # Cần để lấy duration/sample_rate của stem

# [FIX] Import đầy đủ các module tiện ích mới
from utils.constants import DATA_OUTPUT_DIR
from utils.config_loader import config
from utils.logging_config import get_session_id

logger = logging.getLogger(__name__)


class SeparationService:
    @staticmethod
    def run_separation(
        input_path: str,
        model_name: str = None,
        progress_callback=None,
        job_id: str = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Chạy tác vụ tách nhạc (Demucs).
        Hỗ trợ: Config loader, Logging context, Progress reporting.
        [FIXED] Đảm bảo trả về đầy đủ 'stems' và 'input_path' để tránh KeyError.
        """
        # 1. Load Config Defaults
        if model_name is None:
            model_name = config.get("processing.separation.default_model", "htdemucs")

        # 2. Setup Logging Context
        session_id = get_session_id()
        extra_log = {
            "session_id": session_id,
            "operation": "run_separation",
            "input_file": input_path,
            "model": model_name,
        }
        if job_id:
            extra_log["job_id"] = job_id

        logger.info("Separation started", extra=extra_log)

        # Helper báo cáo tiến độ
        def report(p):
            if progress_callback:
                try:
                    progress_callback(p)
                except:
                    pass

        report(0)  # START

        try:
            # Lazy Import Pipeline
            from pipelines.separation_pipeline import DemucsPipeline

            if not os.path.exists(input_path):
                raise FileNotFoundError(f"Input file not found: {input_path}")

            # --- STAGE 1: INIT ---
            report(10)
            report(20)

            # --- STAGE 2: PROCESS ---
            # Demucs output sẽ nằm trong data/output/separation
            sep_base_dir = DATA_OUTPUT_DIR / "separation"
            sep_base_dir.mkdir(parents=True, exist_ok=True)

            # Gọi Pipeline (đã fix lỗi WindowsPath trước đó)
            # DemucsPipeline.separate chỉ trả về info cơ bản, ta cần scan file thủ công
            pipeline_result = DemucsPipeline.separate(
                input_path=input_path, output_dir=sep_base_dir, model_name=model_name
            )

            report(80)  # Separation Done

            # --- STAGE 3: SCAN STEMS & BUILD RESULT ---
            # Demucs tạo thư mục theo cấu trúc: output_dir / model_name / track_name / stems.wav
            # Ta cần tìm đúng thư mục chứa kết quả của file input này.

            input_filename = Path(input_path).stem
            # Thư mục dự kiến chứa stems
            expected_stem_dir = sep_base_dir / model_name / input_filename

            # [FIX BUG-SEPARATION-MISSING-STEMS] Logic quét file stem
            stems_list = []

            if expected_stem_dir.exists():
                # Tìm tất cả file wav trong thư mục này
                wav_files = list(expected_stem_dir.glob("*.wav"))

                if wav_files:
                    # Lấy metadata từ file đầu tiên (giả sử các stem có cùng length/rate)
                    try:
                        ref_audio = AudioSegment.from_wav(str(wav_files[0]))
                        duration = len(ref_audio) / 1000.0
                        sample_rate = ref_audio.frame_rate
                    except Exception:
                        duration = 0.0
                        sample_rate = 44100

                    # Xây dựng danh sách dictionary cho từng stem
                    for wav_path in wav_files:
                        stems_list.append(
                            {
                                "name": wav_path.stem,  # vocals, drums, bass, other
                                "path": str(wav_path),  # convert Path -> str
                                "duration": duration,
                                "sample_rate": sample_rate,
                            }
                        )

            # Nếu không tìm thấy file theo đường dẫn dự kiến, thử fallback scan (tùy chọn)
            if not stems_list:
                error_msg = (
                    f"Separation completed but no output stems found. "
                    f"Expected location: {expected_stem_dir}. "
                    f"Demucs may have failed silently or output path mismatch."
                )
                logger.error(
                    "Separation failed - no stems generated",
                    extra={
                        "session_id": session_id,
                        "job_id": job_id,
                        "expected_path": str(expected_stem_dir),
                        "input_file": Path(input_path).name,
                        "operation": "scan_stems",
                    },
                )
                # Raise lỗi để Action layer bắt được và hiển thị Toast error thay vì crash
                raise RuntimeError(error_msg)
            # --- END FIX BUG #1 ---

            report(100)  # DONE

            logger.info(
                "Separation completed",
                extra={
                    "session_id": session_id,
                    "stems_count": len(stems_list),
                    "job_id": job_id,
                },
            )

            return {
                "model_name": model_name,
                "input_path": str(input_path),
                "output_dir": str(expected_stem_dir),
                "stems": stems_list,
            }

        except Exception as e:
            logger.error(
                "Separation failed",
                extra={
                    "session_id": session_id,
                    "operation": "run_separation",
                    "error": str(e),
                    "job_id": job_id,
                },
                exc_info=True,
            )
            raise e
