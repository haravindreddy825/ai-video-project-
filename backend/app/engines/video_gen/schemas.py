from pathlib import Path
from typing import Literal, Optional
from pydantic import BaseModel, Field

AspectRatio = Literal["16:9", "9:16", "1:1"]
FlowDuration = Literal[30, 60, 90, 120]


class ProviderCapability(BaseModel):
    id: str
    name: str
    kind: Literal["cloud_api", "local_gpu"]
    available: bool
    reason: str
    max_clip_duration_sec: int
    resolutions: list[str]
    supports_i2v: bool
    supports_first_last_frame: bool
    supports_extension: bool
    supports_reference_images: bool
    cost_per_sec_usd: float
    estimated_120s_cost_usd: float
    requirements: str


class VideoGenRequest(BaseModel):
    prompt: str
    duration_sec: int = 8
    aspect_ratio: AspectRatio = "16:9"
    quality: str = "lite"
    first_frame_path: Optional[Path] = None
    last_frame_path: Optional[Path] = None
    reference_image_paths: list[Path] = Field(default_factory=list)
    source_video_path: Optional[Path] = None
    output_mp4_path: Path


class VideoGenResult(BaseModel):
    provider_id: str
    output_mp4_path: Path
    duration_sec: float
    width: int
    height: int
    last_frame_path: Optional[Path] = None
