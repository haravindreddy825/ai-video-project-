import httpx

from app.core.config import settings
from app.engines.video_gen.providers.base import (
    BaseVideoGenProvider,
    ProviderNotConfiguredError,
)
from app.engines.video_gen.schemas import (
    ProviderCapability,
    VideoGenRequest,
    VideoGenResult,
)


class ComfyUIWanProvider(BaseVideoGenProvider):
    """
    Local 6GB VRAM Open-Source Video Provider via ComfyUI + Wan 2.1 1.3B GGUF (Apache-2.0).
    Requires ComfyUI running locally with --lowvram and Wan 2.1 1.3B GGUF weights.
    """

    id = "comfyui_wan2_1"

    def _comfy_online(self) -> bool:
        try:
            r = httpx.get(f"{settings.COMFYUI_URL.rstrip('/')}/system_stats", timeout=1.5)
            return r.status_code == 200
        except Exception:
            return False

    def get_capabilities(self) -> ProviderCapability:
        online = self._comfy_online()
        return ProviderCapability(
            id=self.id,
            name="Wan 2.1 1.3B GGUF (Local ComfyUI)",
            kind="local_gpu",
            available=online,
            reason=(
                f"ComfyUI online at {settings.COMFYUI_URL}"
                if online
                else f"ComfyUI not running at {settings.COMFYUI_URL}. Start ComfyUI with --lowvram and Wan 2.1 1.3B GGUF weights."
            ),
            max_clip_duration_sec=5,
            resolutions=["480p (832x480)"],
            supports_i2v=True,
            supports_first_last_frame=False,
            supports_extension=True,
            supports_reference_images=False,
            cost_per_sec_usd=0.0,
            estimated_120s_cost_usd=0.0,
            requirements="Local ComfyUI (--lowvram) + ComfyUI-GGUF + Wan2.1-1.3B-Q4_K_M (~6-8 GB disk, RTX 3050 6GB).",
        )

    def generate_clip(self, req: VideoGenRequest) -> VideoGenResult:
        if not self._comfy_online():
            raise ProviderNotConfiguredError(
                f"Local ComfyUI server is not running at {settings.COMFYUI_URL}. "
                "Start ComfyUI with Wan 2.1 1.3B GGUF weights, or switch provider to Google Veo 3.1 with GEMINI_API_KEY."
            )
        raise ProviderNotConfiguredError(
            "ComfyUI is reachable, but Wan 2.1 1.3B GGUF workflow weights must be placed in ComfyUI/models/unet/."
        )
