# pipelines/asr_whisperx.py

import logging

from typing import Optional
from __future__ import annotations
from state.schemas import Transcript, AlignmentResult
from utils.logging_config import get_session_id

logger = logging.getLogger(__name__)


class WhisperXPipeline:
    def __init__(
        self,
        model_size: str = "base",
        device: str = "cuda",
        compute_type: str = "float16",
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._align_model = None
        # NOTE: DO NOT load heavy model in __init__ (lazy loading)

    def load_model(self) -> None:
        """Load model into memory if not loaded."""
        if self._model is not None:
            return
        logger.info(
            "Loading WhisperX model",
            extra={
                "session_id": get_session_id(),
                "operation": "asr_load_model",
                "model_size": self.model_size,
                "device": self.device,
                "compute_type": self.compute_type,
            },
        )

        # TODO: whisperx.load_model(...)
        # self._model = ...
        # self._align_model = ...
        return

    def transcribe(
        self,
        audio_path: str,
        batch_size: int = 16,
        language: Optional[str] = None,
    ) -> Transcript:
        self.load_model()
        logger.info(
            "Starting transcription",
            extra={
                "session_id": get_session_id(),
                "operation": "asr_transcribe",
                "audio_path": audio_path,
                "batch_size": batch_size,
                "language": language,
            },
        )
        # TODO: run whisperx transcription and map -> Transcript schema
        return Transcript(
            full_text="",
            segments=[],
            language=language or "en",
            duration=0.0,
            model_name=f"whisperx-{self.model_size}",
        )

    def align(self, audio_path: str, transcript: Transcript) -> AlignmentResult:
        self.load_model()
        logger.info(
            "Starting alignment",
            extra={
                "session_id": get_session_id(),
                "operation": "asr_align",
                "audio_path": audio_path,
            },
        )
        # TODO: whisperx alignment map -> words in segments
        return AlignmentResult(transcript=transcript, aligned=False, metadata={})
