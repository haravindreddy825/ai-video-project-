from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional

from app.engines.avatar.schemas import (
    AvatarTimelineSegment,
    CharacterIdentityPack,
    ContinuityReport,
)


class AdapterUnavailableError(RuntimeError):
    """Raised when an optional local/cloud avatar adapter is not reachable."""


class BaseAvatarAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def render(
        self,
        identity_pack: CharacterIdentityPack,
        audio_wav_path: Path,
        segments: list[AvatarTimelineSegment],
        output_mp4_path: Path,
        fps: int = 25,
        chunk_duration_sec: float = 12.0,
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> ContinuityReport:
        """Render synchronized 1080x960 avatar MP4 muxed with audio_wav_path."""
