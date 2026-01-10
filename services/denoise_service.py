import os
import logging
import time
import numpy as np
from pathlib import Path
from pydub import AudioSegment
<<<<<<< HEAD
from utils.fs.path_utils import resolve_output_path
=======
from utils.file_manager import resolve_output_path
>>>>>>> origin/main
from utils.logging_config import get_session_id
from utils.config_loader import config

logger = logging.getLogger(__name__)


class DenoiseService:
    """
    Service xử lý giảm nhiễu audio (Robust + Lazy Import).
    Độc lập hoàn toàn với Streamlit.
    """

    @staticmethod
    def denoise_audio(
        input_path: str,
        method=None,
        strength=None,
        progress_callback=None,
        job_id=None,
        **kwargs,
    ):
        """
        [FIX ERROR 2] Thêm job_id=None và **kwargs để tránh lỗi "unexpected keyword argument"
        nếu job_runner truyền thêm tham số context.
        """
        # Load defaults from config
        if method is None:
            method = config.get("processing.denoise.default_method", "auto")
        if strength is None:
            strength = config.get("processing.denoise.default_strength", 0.5)

        session_id = get_session_id()
        start_time = time.time()

        # Logging Context
        extra_log = {
            "session_id": session_id,
            "operation": "denoise_audio",
            "input_file": input_path,
            "method": method,
            "strength": strength,
        }
        if job_id:
            extra_log["job_id"] = job_id

        logger.info("Denoise started", extra=extra_log)

        def report(p):
            if progress_callback:
                try:
                    progress_callback(p)
                except:
                    pass

        report(0)

        try:
            if not os.path.exists(input_path):
                raise FileNotFoundError(f"Input file not found: {input_path}")

            # --- PROCESS ---
            import noisereduce as nr

            # Load
            audio = AudioSegment.from_file(input_path)
            data = np.array(audio.get_array_of_samples())
            if audio.channels == 2:
                data = data.reshape((-1, 2))

            # Reduce Noise
            reduced_data = nr.reduce_noise(
                y=data.T if audio.channels == 2 else data,
                sr=audio.frame_rate,
                prop_decrease=strength,
                stationary=True,
            )

            if audio.channels == 2:
                reduced_data = reduced_data.T

            # Save
            output_filename = f"denoised_{Path(input_path).name}"
            if not output_filename.lower().endswith(".wav"):
                output_filename = Path(output_filename).stem + ".wav"

            # [FIX ERROR 1] Đảm bảo DATA_OUTPUT_DIR đã import
            output_dir = resolve_output_path(
                config.get("processing.denoise.output_dir", None),
                "",
            )
            output_path = output_dir / output_filename

            # Export
            if reduced_data.dtype == np.float32 or reduced_data.dtype == np.float64:
                reduced_data = (reduced_data * 32767).astype(np.int16)
            processed_audio = audio._spawn(reduced_data.tobytes())
            processed_audio.export(output_path, format="wav")

            report(100)

            # Log Success
            elapsed = time.time() - start_time
            logger.info(
                "Denoise completed",
                extra={
                    "session_id": session_id,
                    "operation": "denoise_audio",
                    "duration": elapsed,
                    "output_file": str(output_path),
                    "job_id": job_id,
                },
            )

            return {
                "output_path": str(output_path),
                "method_used": f"noisereduce (strength={strength})",
                "is_denoised": True,
            }

        except Exception as e:
            logger.error(
                "Denoise failed",
                extra={
                    "session_id": session_id,
                    "operation": "denoise_audio",
                    "error": str(e),
                    "job_id": job_id,
                },
                exc_info=True,
            )
            raise e

    @staticmethod
    def _spectral_gate_fallback(y, sr, strength, reduce_noise_db):
        """
        Fallback implementation using Scipy STFT (Lazy Import).
        """
        try:
            from scipy import signal
        except ImportError:
            return y

        # Recursive handle for stereo
        if y.ndim > 1:
            out = []
            for channel in y:
                out.append(
                    DenoiseService._spectral_gate_fallback(
                        channel, sr, strength, reduce_noise_db
                    )
                )
            return np.array(out)

        # STFT
        f, t, Zxx = signal.stft(y, fs=sr, nperseg=1024)
        mag = np.abs(Zxx)

        # Noise Profile
        noise_sample_len = int(0.5 * sr / 512) or 1
        noise_mean = np.mean(mag[:, :noise_sample_len], axis=1, keepdims=True)

        # Thresholding
        threshold = noise_mean * (1.0 + strength * 1.5)

        # Mask Generation
        mask = mag > threshold
        mask = mask.astype(float)

        # Smoothing mask
        mask = signal.convolve2d(mask, np.ones((3, 3)) / 9.0, mode="same")

        # Attenuation
        attenuation_factor = 10 ** (-reduce_noise_db / 20.0)
        final_mask = mask * (1.0 - attenuation_factor) + attenuation_factor

        Zxx_denoised = Zxx * final_mask

        # ISTFT
        _, y_rec = signal.istft(Zxx_denoised, fs=sr)

        # Fix padding length
        if len(y_rec) > len(y):
            y_rec = y_rec[: len(y)]
        elif len(y_rec) < len(y):
            y_rec = np.pad(y_rec, (0, len(y) - len(y_rec)))

        return y_rec


if __name__ == "__main__":
    pass
