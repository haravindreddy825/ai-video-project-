from pathlib import Path
from typing import Callable, Optional

from app.core.logging import logger
from app.engines.avatar.adapters.base import AdapterUnavailableError, BaseAvatarAdapter
from app.engines.avatar.adapters.cloud_and_comfy import (
    CloudAvatarAdapter,
    ComfyUIEchoMimicV2Adapter,
)
from app.engines.avatar.adapters.local_expressive import LocalExpressiveAvatarAdapter
from app.engines.avatar.schemas import (
    AvatarTimelineSegment,
    CharacterIdentityPack,
    ContinuityReport,
)


class AvatarEngineOrchestrator:
    """
    Selects and executes an interchangeable avatar animation adapter with
    automatic local/cloud fallback for RTX 3050 6GB hardware.
    """

    def __init__(self) -> None:
        self.adapters: dict[str, BaseAvatarAdapter] = {
            "local_expressive": LocalExpressiveAvatarAdapter(),
            "comfyui_echomimic_v2": ComfyUIEchoMimicV2Adapter(),
            "cloud_avatar": CloudAvatarAdapter(),
        }

    def render_with_fallback(
        self,
        requested_adapter: str,
        identity_pack: CharacterIdentityPack,
        audio_wav_path: Path,
        segments: list[AvatarTimelineSegment],
        output_mp4_path: Path,
        fps: int = 25,
        chunk_duration_sec: float = 12.0,
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> tuple[str, ContinuityReport]:
        order = (
            ["comfyui_echomimic_v2", "cloud_avatar", "local_expressive"]
            if requested_adapter == "auto"
            else [requested_adapter, "local_expressive"]
        )

        last_err: Exception | None = None
        for name in order:
            adapter = self.adapters.get(name)
            if not adapter:
                continue
            try:
                report = adapter.render(
                    identity_pack=identity_pack,
                    audio_wav_path=audio_wav_path,
                    segments=segments,
                    output_mp4_path=output_mp4_path,
                    fps=fps,
                    chunk_duration_sec=chunk_duration_sec,
                    progress_cb=progress_cb,
                )
                return name, report
            except AdapterUnavailableError as exc:
                logger.info("Avatar adapter '%s' unavailable (%s); trying fallback.", name, exc)
                last_err = exc

        raise RuntimeError(f"All avatar adapters failed: {last_err}")
