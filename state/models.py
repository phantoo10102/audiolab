from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class AudioState:
    current_path: Optional[str] = None
    original_path: Optional[str] = None
    duration: float = 0.0

    # [FIX] Khai báo biến thường, KHÔNG dùng @property
    is_loaded: bool = False

    # Version để ép Waveform vẽ lại
    version: int = 0
    source_url: Optional[str] = None


@dataclass
class SelectionState:
    start: float = 0.0
    end: float = 0.0
    source: str = "init"
    version: int = 0


@dataclass
class UIState:
    theme: str = "light"
    # [FIX BUG-009] Rename 'last_apply_id' -> 'last_waveform_id'
    # để khớp với runtime check trong SessionManager.
    last_waveform_id: int = 0
    show_spectrogram: bool = False


@dataclass
class HistoryEntry:
    path: str
    original_path: str
    duration: float
    view_start: float = 0.0
    view_end: float = 0.0


@dataclass
class AppState:
    audio: AudioState = field(default_factory=AudioState)
    selection: SelectionState = field(default_factory=SelectionState)
    ui: UIState = field(default_factory=UIState)
