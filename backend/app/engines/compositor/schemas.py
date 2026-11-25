from typing import Any, Optional
from pydantic import BaseModel, Field


class ExportCreateRequest(BaseModel):
    audio_id: str
    avatar_job_id: str
    include_subtitles: bool = True
    prefer_nvenc: bool = False
    fps: int = Field(default=30, ge=24, le=30)


class ExportValidationReport(BaseModel):
    width: int
    height: int
    aspect_ratio: str
    fps: float
    video_codec: str
    audio_codec: str
    pixel_format: str
    duration_sec: float
    audio_duration_sec: float
    av_drift_ms: float
    black_frame_count: int
    samples_checked: int
    passed: bool
    warnings: list[str] = Field(default_factory=list)


class VideoExportResponse(BaseModel):
    id: str
    project_id: str
    audio_id: str
    avatar_job_id: str
    status: str
    progress_pct: int
    encoder_used: str
    include_subtitles: bool
    width: int
    height: int
    fps: int
    duration_sec: float
    output_mp4_path: Optional[str] = None
    subtitle_ass_path: Optional[str] = None
    validation_report_json: Optional[dict[str, Any]] = None
    logs_json: Optional[list[dict[str, Any]]] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}
