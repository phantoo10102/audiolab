# state/schemas.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal, Union
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


# ----------------------------
# SEPARATION SCHEMAS
# ----------------------------
class SeparationStem(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str  # e.g., "vocals", "drums", "bass", "other"
    path: str  # Absolute path to the wav file
    duration: float  # Duration in seconds
    sample_rate: int


class SeparationResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    model_name: str
    input_path: str
    output_dir: str
    stems: List[SeparationStem] = Field(default_factory=list)
    error: Optional[str] = None


# ----------------------------
# JOB ENUMS
# ----------------------------
class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


JobKind = Literal["asr", "align", "tts", "other"]


# ----------------------------
# ASR / ALIGNMENT SCHEMAS
# ----------------------------
class WordUnit(BaseModel):
    word: str
    start: float
    end: float
    score: float = 0.0
    speaker: Optional[str] = None


class Segment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    words: List[WordUnit] = Field(default_factory=list)
    speaker: Optional[str] = None
    avg_logprob: float = 0.0
    no_speech_prob: float = 0.0


class Transcript(BaseModel):
    full_text: str
    segments: List[Segment] = Field(default_factory=list)
    language: str = "unknown"
    duration: float = 0.0
    model_name: str = "unknown"


class AlignmentResult(BaseModel):
    """Nếu bạn muốn tách alignment khỏi transcript raw."""

    transcript: Transcript
    aligned: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ----------------------------
# TTS SCHEMAS
# ----------------------------
class TTSResult(BaseModel):
    audio_path: str  # Path to generated wav/mp3
    duration: float
    text: str
    ref_audio_path: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ----------------------------
# JOB RESULT (generic payload)
# ----------------------------
JobPayload = Union[Transcript, AlignmentResult, TTSResult, Any]


class JobResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    kind: JobKind
    status: JobStatus
    data: Optional[JobPayload] = None
    error_message: Optional[str] = None
    progress: float = 0.0  # 0.0 -> 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
