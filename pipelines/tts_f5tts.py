# pipelines/tts_f5tts.py


import logging

from typing import Optional
from __future__ import annotations
from state.schemas import TTSResult
from utils.logging_config import get_session_id

logger = logging.getLogger(__name__)


class F5TTSPipeline:
    def __init__(self, model_name: str = "F5-TTS", device: str = "cuda"):
        self.model_name = model_name
        self.device = device
        self._model = None

    def load_model(self) -> None:
        if self._model is not None:
            return
        logger.info(
            "Loading F5TTS model",
            extra={
                "session_id": get_session_id(),
                "operation": "tts_load_model",
                "model_name": self.model_name,
                "device": self.device,
            },
        )
        # TODO: load model
        return

    def synthesize(
        self,
        text: str,
        ref_audio_path: Optional[str] = None,
        ref_text: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> TTSResult:
        self.load_model()
        logger.info(
            "Synthesizing text",
            extra={
                "session_id": get_session_id(),
                "operation": "tts_synthesize",
                "text_preview": text[:50],  # Lấy 50 ký tự đầu
                "ref_audio": ref_audio_path,
            },
        )
        # TODO: inference + save to output_path
        return TTSResult(
            audio_path=output_path or "temp_tts.wav",
            duration=0.0,
            text=text,
            ref_audio_path=ref_audio_path,
            metadata={"ref_text": ref_text},
        )
