# ===== FILE: services/whisperx_service.py =====
import gc
import inspect
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional

import torch
import whisperx

# [VERIFIED IMPORTS]
from utils.constants import DATA_MODELS_DIR
from utils.logging_config import get_session_id

logger = logging.getLogger(__name__)


class WhisperXService:
    """
    Ver3-specific WhisperX Service.
    Adapts logic from reference 'transcribe.py' but removes external dependencies.
    Includes Structured Logging.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WhisperXService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.model = None
        self.model_name = None
        self.device = None
        self.compute_type = None
        self._initialized = True

    def load_model(
        self,
        model_name: str,
        device: str = "cuda",
        compute_type: str = "float16",
        models_dir: Optional[str | Path] = None,
    ) -> Dict[str, Any]:
        """
        Loads the WhisperX model with reuse logic and structured logging.
        """
        session_id = get_session_id()
        start_time = time.time()

        try:
            # Check availability
            if device == "cuda" and not torch.cuda.is_available():
                logger.warning(
                    "CUDA requested but not available. Falling back to CPU.",
                    extra={
                        "session_id": session_id,
                        "operation": "whisperx_load_model",
                        "event": "fallback_cpu",
                    },
                )
                device = "cpu"
                compute_type = "int8"

            # Reuse check
            if self.model is not None:
                if (
                    self.model_name == model_name
                    and self.device == device
                    and self.compute_type == compute_type
                ):

                    logger.info(
                        "Model reused from memory",
                        extra={
                            "session_id": session_id,
                            "operation": "whisperx_load_model",
                            "model": model_name,
                            "status": "reused",
                        },
                    )
                    return {"success": True, "message": "Model reused from memory"}

                # Unload if different config
                self.unload_model()

            resolved_models_dir = self._resolve_models_dir(models_dir, session_id)
            model_available = self._model_exists(
                resolved_models_dir, model_name
            )

            logger.info(
                f"Loading WhisperX model",
                extra={
                    "session_id": session_id,
                    "operation": "whisperx_load_model",
                    "model": model_name,
                    "device": device,
                    "compute_type": compute_type,
                    "models_dir": str(resolved_models_dir),
                },
            )

            if not model_available:
                logger.info(
                    "Model not found locally; downloading",
                    extra={
                        "session_id": session_id,
                        "operation": "whisperx_model_download",
                        "model": model_name,
                        "models_dir": str(resolved_models_dir),
                    },
                )
                self.model = self.ensure_whisperx_model(
                    resolved_models_dir,
                    model_name,
                    device=device,
                    compute_type=compute_type,
                )
            else:
                logger.info(
                    "Model found locally; reuse local files",
                    extra={
                        "session_id": session_id,
                        "operation": "whisperx_model_reuse",
                        "model": model_name,
                        "models_dir": str(resolved_models_dir),
                    },
                )

            if self.model is None:
                # Load model
                self.model = whisperx.load_model(
                    model_name,
                    device=device,
                    compute_type=compute_type,
                    download_root=str(resolved_models_dir),
                )

            self.model_name = model_name
            self.device = device
            self.compute_type = compute_type

            elapsed = time.time() - start_time
            logger.info(
                "Model loaded successfully",
                extra={
                    "session_id": session_id,
                    "operation": "whisperx_load_model",
                    "model": model_name,
                    "duration": round(elapsed, 3),
                },
            )

            return {"success": True, "message": "Model loaded successfully"}

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "Model load failed",
                extra={
                    "session_id": session_id,
                    "operation": "whisperx_load_model",
                    "model": model_name,
                    "error": str(e),
                    "duration": round(elapsed, 3),
                },
                exc_info=True,
            )
            return {"success": False, "message": str(e)}

    def _model_exists(self, models_dir: Path, model_name: str) -> bool:
        model_dir = models_dir / model_name
        return model_dir.exists() and any(model_dir.iterdir())

    def ensure_whisperx_model(
        self,
        models_dir: Path,
        model_name: str,
        device: str,
        compute_type: str,
        *,
        language: str | None = None,
    ) -> Optional[Any]:
        models_dir.mkdir(parents=True, exist_ok=True)
        if self._model_exists(models_dir, model_name):
            return None

        kwargs = {
            "device": device,
            "compute_type": compute_type,
            "download_root": str(models_dir),
        }
        if language is not None:
            kwargs["language"] = language

        try:
            return whisperx.load_model(model_name, **kwargs)
        except TypeError as e:
            # Backward-compatible: some whisperx versions may not accept `language=`
            if "language" in str(e):
                kwargs.pop("language", None)
                return whisperx.load_model(model_name, **kwargs)
            raise


    def _resolve_models_dir(
        self,
        models_dir: Optional[str | Path],
        session_id: str,
    ) -> Path:
        default_dir = DATA_MODELS_DIR / "whisperx"
        if models_dir is None:
            return default_dir
        if isinstance(models_dir, str) and not models_dir.strip():
            return default_dir
        try:
            resolved = Path(models_dir).expanduser()
            resolved.mkdir(parents=True, exist_ok=True)
            return resolved
        except Exception as e:
            logger.warning(
                "Invalid models_dir; falling back to default",
                extra={
                    "session_id": session_id,
                    "operation": "whisperx_models_dir_fallback",
                    "models_dir": str(models_dir),
                    "error": str(e),
                },
            )
            default_dir.mkdir(parents=True, exist_ok=True)
            return default_dir

    def transcribe(
        self,
        audio_path: str,
        language: str | None = "en",
        batch_size: int = 16,
        vad_filter: bool | None = None,
    ) -> Dict[str, Any]:
        """
        Runs transcription with structured logging.
        """
        session_id = get_session_id()
        start_time = time.time()

        if not self.model:
            return {"success": False, "message": "Model not loaded"}

        try:
            language_label = language or "auto"
            logger.info(
                "Transcription started",
                extra={
                    "session_id": session_id,
                    "operation": "whisperx_transcribe",
                    "input_file": Path(audio_path).name,
                    "language": language_label,
                    "batch_size": batch_size,
                },
            )

            audio = whisperx.load_audio(audio_path)
            transcribe_kwargs = self._build_transcribe_kwargs(
                language=language,
                batch_size=batch_size,
                session_id=session_id,
            )

            if vad_filter:
                sample_rate = getattr(whisperx, "SAMPLE_RATE", 16000)
                vad_token = self._resolve_vad_token()
                try:
                    vad_intervals = self._get_vad_intervals(
                        waveform=audio,
                        sample_rate=sample_rate,
                        session_id=session_id,
                        token=vad_token,
                    )
                except Exception as exc:
                    logger.warning(
                        "VAD failed; falling back to full transcription",
                        extra={
                            "session_id": session_id,
                            "operation": "whisperx_vad",
                            "error": str(exc),
                        },
                    )
                    vad_intervals = []

                if vad_intervals:
                    merged_segments = []
                    detected_language = None
                    for start_s, end_s in vad_intervals:
                        chunk = self._slice_audio(audio, sample_rate, start_s, end_s)
                        if chunk is None:
                            continue
                        chunk_result = self.model.transcribe(chunk, **transcribe_kwargs)
                        chunk_segments = chunk_result.get("segments", [])
                        self._offset_segments(chunk_segments, start_s)
                        merged_segments.extend(chunk_segments)
                        if detected_language is None:
                            detected_language = chunk_result.get("language")

                    merged_segments.sort(key=lambda seg: seg.get("start", 0.0))
                    result = {
                        "segments": merged_segments,
                        "language": detected_language or language,
                    }
                else:
                    logger.warning(
                        "No VAD speech regions found; running full transcription",
                        extra={
                            "session_id": session_id,
                            "operation": "whisperx_vad",
                        },
                    )
                    result = self.model.transcribe(audio, **transcribe_kwargs)
            else:
                result = self.model.transcribe(audio, **transcribe_kwargs)

            # Cleanup
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            elapsed = time.time() - start_time
            num_segments = len(result.get("segments", []))

            logger.info(
                "Transcription completed",
                extra={
                    "session_id": session_id,
                    "operation": "whisperx_transcribe",
                    "duration": round(elapsed, 3),
                    "num_segments": num_segments,
                },
            )

            return {
                "success": True,
                "segments": result["segments"],
                "language": result.get("language", language),
            }

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "Transcription failed",
                extra={
                    "session_id": session_id,
                    "operation": "whisperx_transcribe",
                    "input_file": Path(audio_path).name,
                    "error": str(e),
                    "duration": round(elapsed, 3),
                },
                exc_info=True,
            )
            return {"success": False, "message": str(e)}

    def unload_model(self):
        if self.model:
            del self.model
            self.model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _build_transcribe_kwargs(
        self,
        *,
        language: str | None,
        batch_size: int,
        session_id: str,
    ) -> Dict[str, Any]:
        transcribe_kwargs = {"batch_size": batch_size}
        try:
            signature = inspect.signature(self.model.transcribe)
            param_names = set(signature.parameters.keys())
        except (TypeError, ValueError):
            param_names = set()

        if language is None:
            logger.info(
                "Transcription language set to auto-detect",
                extra={
                    "session_id": session_id,
                    "operation": "whisperx_transcribe",
                },
            )
            return transcribe_kwargs

        if "language" in param_names or not param_names:
            transcribe_kwargs["language"] = language
            return transcribe_kwargs

        logger.warning(
            "Transcribe does not accept language parameter; omitting",
            extra={
                "session_id": session_id,
                "operation": "whisperx_transcribe",
                "language": language,
            },
        )
        return transcribe_kwargs

    def _get_vad_intervals(
        self,
        *,
        waveform,
        sample_rate: int,
        session_id: str,
        token: str | None,
    ) -> list[tuple[float, float]]:
        from pyannote.audio import Pipeline

        pipeline = Pipeline.from_pretrained(
            "pyannote/voice-activity-detection",
            use_auth_token=token,
        )
        audio_tensor = torch.tensor(waveform).float().unsqueeze(0)
        vad_result = pipeline({"waveform": audio_tensor, "sample_rate": sample_rate})
        segments = []
        for segment in vad_result.get_timeline().support():
            segments.append((float(segment.start), float(segment.end)))
        logger.info(
            "VAD intervals detected",
            extra={
                "session_id": session_id,
                "operation": "whisperx_vad",
                "segments": len(segments),
            },
        )
        return segments

    def _resolve_vad_token(self) -> str | None:
        try:
            from services.settings_service import settings_manager

            settings = settings_manager.load_settings()
            token = settings.get("whisperx", {}).get("vad_token")
            if token:
                return token
        except Exception:
            pass

        return os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")

    def _slice_audio(
        self,
        waveform,
        sample_rate: int,
        start_s: float,
        end_s: float,
    ):
        if start_s >= end_s:
            return None
        start_idx = max(0, int(start_s * sample_rate))
        end_idx = max(start_idx, int(end_s * sample_rate))
        try:
            return waveform[start_idx:end_idx]
        except Exception:
            return None

    def _offset_segments(self, segments: list[dict], offset_s: float) -> None:
        for seg in segments:
            if "start" in seg and seg["start"] is not None:
                seg["start"] = float(seg["start"]) + offset_s
            if "end" in seg and seg["end"] is not None:
                seg["end"] = float(seg["end"]) + offset_s
            if "words" in seg and isinstance(seg["words"], list):
                for word in seg["words"]:
                    if "start" in word and word["start"] is not None:
                        word["start"] = float(word["start"]) + offset_s
                    if "end" in word and word["end"] is not None:
                        word["end"] = float(word["end"]) + offset_s


# Singleton accessor
whisperx_service = WhisperXService()