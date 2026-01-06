# ===== FILE: services/whisperx_service.py =====
import os
import gc
import logging
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
        self, model_name: str, device: str = "cuda", compute_type: str = "float16"
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

            logger.info(
                f"Loading WhisperX model",
                extra={
                    "session_id": session_id,
                    "operation": "whisperx_load_model",
                    "model": model_name,
                    "device": device,
                    "compute_type": compute_type,
                },
            )

            # Load model
            self.model = whisperx.load_model(
                model_name,
                device=device,
                compute_type=compute_type,
                download_root=str(DATA_MODELS_DIR),
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

    def transcribe(
        self, audio_path: str, language: str = "en", batch_size: int = 16
    ) -> Dict[str, Any]:
        """
        Runs transcription with structured logging.
        """
        session_id = get_session_id()
        start_time = time.time()

        if not self.model:
            return {"success": False, "message": "Model not loaded"}

        try:
            logger.info(
                "Transcription started",
                extra={
                    "session_id": session_id,
                    "operation": "whisperx_transcribe",
                    "input_file": Path(audio_path).name,
                    "language": language,
                    "batch_size": batch_size,
                },
            )

            # Load audio
            audio = whisperx.load_audio(audio_path)

            # Transcribe
            result = self.model.transcribe(
                audio, batch_size=batch_size, language=language
            )

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


# Singleton accessor
whisperx_service = WhisperXService()
