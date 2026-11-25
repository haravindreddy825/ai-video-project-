from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

EmotionType = Literal[
    "happy",
    "serious",
    "curious",
    "surprised",
    "thinking",
    "explaining",
    "confident",
    "concerned",
    "neutral",
]


class FaceBox(BaseModel):
    x: int
    y: int
    w: int
    h: int


class Point2D(BaseModel):
    x: int
    y: int


class CharacterIdentityPack(BaseModel):
    character_id: str
    canonical_image_path: str
    width: int = 1080
    height: int = 960
    face_box: FaceBox
    eye_left: Point2D
    eye_right: Point2D
    mouth_center: Point2D
    shoulder_y: int
    color_mean_bgr: list[float] = Field(default_factory=list)
    approved: bool = False


class AvatarTimelineSegment(BaseModel):
    index: int
    start_ms: int
    end_ms: int
    emotion: EmotionType = "neutral"
    facial_expression: str = "natural_attentive_expression"
    hand_gesture: str = "subtle_conversational_gesture"
    head_movement: str = "natural_micro_nod"
    is_pause: bool = False
    highlight_words: list[str] = Field(default_factory=list)


class ContinuityReport(BaseModel):
    segments_checked: int
    boundary_ssim_min: float
    boundary_ssim_avg: float
    audio_duration_sec: float
    video_duration_sec: float
    av_drift_ms: float
    passed: bool
    warnings: list[str] = Field(default_factory=list)


class AvatarGenerateRequest(BaseModel):
    character_id: str
    audio_id: str
    adapter: Literal["auto", "local_expressive", "comfyui_echomimic_v2", "cloud_avatar"] = "auto"
    fps: int = Field(default=25, ge=15, le=30)
    chunk_duration_sec: float = Field(default=12.0, ge=4.0, le=30.0)


class AvatarJobResponse(BaseModel):
    id: str
    project_id: str
    character_id: str
    audio_id: str
    adapter_used: str
    status: str
    progress_pct: int
    width: int
    height: int
    fps: int
    duration_sec: float
    video_file_path: Optional[str] = None
    continuity_report_json: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}
