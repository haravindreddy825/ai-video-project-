from abc import ABC, abstractmethod

from app.engines.video_gen.schemas import (
    ProviderCapability,
    VideoGenRequest,
    VideoGenResult,
)


class ProviderNotConfiguredError(RuntimeError):
    """Raised when a real video-generation provider lacks an API key or local server."""


class BaseVideoGenProvider(ABC):
    id: str = "base"

    @abstractmethod
    def get_capabilities(self) -> ProviderCapability:
        """Return honest availability, limits, and cost metadata."""

    @abstractmethod
    def generate_clip(self, req: VideoGenRequest) -> VideoGenResult:
        """Generate a real AI video clip (T2V, I2V, or Extension)."""
