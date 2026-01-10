import concurrent.futures
import logging
from pathlib import Path
from typing import Any, Dict, List

from pydub import AudioSegment  # Cần để lấy duration/sample_rate của stem

from utils.config_loader import config
from utils.constants import DATA_OUTPUT_DIR
from utils.logging_config import get_session_id

logger = logging.getLogger(__name__)


class SeparationService:
    @staticmethod
    def _build_stems_from_paths(stem_paths: List[Path]) -> List[Dict[str, Any]]:
        stems_list: List[Dict[str, Any]] = []
        if not stem_paths:
            return stems_list

        try:
            ref_audio = AudioSegment.from_wav(str(stem_paths[0]))
            duration = len(ref_audio) / 1000.0
            sample_rate = ref_audio.frame_rate
        except Exception:
            duration = 0.0
            sample_rate = 44100

        for wav_path in stem_paths:
            stems_list.append(
                {
                    "name": wav_path.stem,
                    "path": str(wav_path),
                    "duration": duration,
                    "sample_rate": sample_rate,
                }
            )
        return stems_list

    @staticmethod
    def run_separation(
        input_path: str,
        model_name: str = None,
        progress_callback=None,
        job_id: str = None,
        cancel_event=None,
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

        def check_cancel():
            if cancel_event and cancel_event.is_set():
                raise concurrent.futures.CancelledError("Separation cancelled")

        # Helper báo cáo tiến độ
        def report(p):
            if progress_callback:
                try:
                    progress_callback(p)
                except Exception:
                    pass

        report(0)  # START
        check_cancel()

        try:
            # Lazy Import Pipeline
            from pipelines.separation_pipeline import DemucsPipeline

            input_file = Path(input_path)
            if not input_file.exists():
                raise FileNotFoundError(f"Input file not found: {input_path}")

            # --- STAGE 1: INIT ---
            report(10)
            report(20)
            check_cancel()

            # --- STAGE 2: PROCESS ---
            # Demucs output sẽ nằm trong data/output/separation
            sep_base_dir = DATA_OUTPUT_DIR / "separation"
            sep_base_dir.mkdir(parents=True, exist_ok=True)

            # Gọi Pipeline (đã fix lỗi WindowsPath trước đó)
            pipeline_result = DemucsPipeline.separate(
                input_path=input_file,
                output_dir=sep_base_dir,
                model_name=model_name,
                cancel_event=cancel_event,
            )

            report(80)  # Separation Done
            check_cancel()

            # --- STAGE 3: BUILD RESULT ---
            stems_list = SeparationService._build_stems_from_paths(
                pipeline_result.stem_paths
            )

            if not stems_list:
                error_msg = (
                    "Separation completed but no output stems found. "
                    "Demucs may have failed silently or output path mismatch."
                )
                logger.error(
                    "Separation failed - no stems generated",
                    extra={
                        "session_id": session_id,
                        "job_id": job_id,
                        "input_file": input_file.name,
                        "operation": "scan_stems",
                    },
                )
                # Raise lỗi để Action layer bắt được và hiển thị Toast error thay vì crash
                raise RuntimeError(error_msg)

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
                "model_name": pipeline_result.model_name,
                "input_path": str(pipeline_result.input_path),
                "output_dir": str(pipeline_result.output_dir),
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
