from app.engines.video_gen.providers.base import BaseVideoGenProvider
from app.engines.video_gen.providers.comfyui_wan_provider import ComfyUIWanProvider
from app.engines.video_gen.providers.veo_provider import GoogleVeoProvider
from app.engines.video_gen.schemas import ProviderCapability


class VideoProviderRegistry:
    """Modular registry for interchangeable Text-to-Video / Image-to-Video providers."""

    def __init__(self) -> None:
        self._providers: dict[str, BaseVideoGenProvider] = {
            "veo_3_1": GoogleVeoProvider(),
            "comfyui_wan2_1": ComfyUIWanProvider(),
        }

    def list_capabilities(self) -> list[ProviderCapability]:
        return [p.get_capabilities() for p in self._providers.values()]

    def get(self, provider_id: str) -> BaseVideoGenProvider:
        if provider_id not in self._providers:
            raise ValueError(
                f"Unknown video provider '{provider_id}'. Supported: {list(self._providers.keys())}"
            )
        return self._providers[provider_id]
