from pathlib import Path
from typing import Callable, Optional

import httpx

from app.core.config import settings
from app.engines.avatar.adapters.base import AdapterUnavailableError, BaseAvatarAdapter
from app.engines.avatar.schemas import (
    AvatarTimelineSegment,
    CharacterIdentityPack,
    ContinuityReport,
)


class ComfyUIEchoMimicV2Adapter(BaseAvatarAdapter):
    """
    Adapter for EchoMimicV2 (Apache-2.0, half-body + hand gestures) running via
    local or remote ComfyUI API (--lowvram sliced inference).
    """

    name = "comfyui_echomimic_v2"

    def is_available(self) -> bool:
        try:
            res = httpx.get(f"{settings.COMFYUI_URL.rstrip('/')}/system_stats", timeout=1.5)
            return res.status_code == 200
        except Exception:
            return False

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
        if not self.is_available():
            raise AdapterUnavailableError(
                f"ComfyUI server not reachable at {settings.COMFYUI_URL}."
            )
        raise AdapterUnavailableError(
            "ComfyUI EchoMimicV2 workflow weights/nodes not yet installed on ComfyUI server."
        )


class CloudAvatarAdapter(BaseAvatarAdapter):
    """
    Optional Cloud GPU adapter for heavy half-body/full-body models
    (EchoMimicV2, LongCat-Video-Avatar, InfiniteTalk).
    Never incurs paid charges unless CLOUD_GPU_PROVIDER & CLOUD_GPU_ENDPOINT are configured.
    """

    name = "cloud_avatar"

    def is_available(self) -> bool:
        return (
            settings.CLOUD_GPU_PROVIDER != "none"
            and bool(settings.CLOUD_GPU_ENDPOINT)
            and bool(settings.CLOUD_GPU_API_KEY)
        )

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
        if not self.is_available():
            raise AdapterUnavailableError(
                "Cloud GPU backend is disabled (CLOUD_GPU_PROVIDER=none)."
            )
        raise AdapterUnavailableError("Cloud GPU endpoint integration awaits user credentials.")
