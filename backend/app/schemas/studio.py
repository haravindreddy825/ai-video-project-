from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    target_duration_sec: int = Field(default=120, ge=10, le=1800)
    compute_mode: Literal["local_hybrid", "local_only", "cloud_preferred"] = "local_hybrid"


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    target_duration_sec: Optional[int] = Field(default=None, ge=10, le=1800)
    compute_mode: Optional[Literal["local_hybrid", "local_only", "cloud_preferred"]] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: Optional[str]
    target_duration_sec: int
    resolution: str
    layout_mode: str
    compute_mode: str
    status: str
    created_at: datetime
    updated_at: datetime


class ScriptCreate(BaseModel):
    raw_text: str = Field(..., min_length=10)
    beats_json: Optional[list[dict[str, Any]]] = None


class ScriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    version: int
    raw_text: str
    beats_json: Optional[list[dict[str, Any]] | dict[str, Any]]
    estimated_duration_sec: float
    created_at: datetime


class CharacterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    reference_image_path: str
    width: int
    height: int
    identity_pack_json: Optional[dict[str, Any]]
    created_at: datetime


class VoiceConfigCreate(BaseModel):
    engine: Literal["kokoro", "chatterbox"] = "kokoro"
    preset_voice_id: Optional[str] = "af_heart"
    speaking_rate: float = Field(default=1.0, ge=0.5, le=2.0)


class VoiceConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    engine: str
    preset_voice_id: Optional[str]
    sample_audio_path: Optional[str]
    speaking_rate: float
    created_at: datetime


class JobCreate(BaseModel):
    script_id: Optional[str] = None
    character_id: Optional[str] = None
    voice_config_id: Optional[str] = None
    max_retries: int = Field(default=3, ge=0, le=5)


class JobStatusUpdate(BaseModel):
    status: Literal["queued", "running", "retrying", "completed", "failed", "cancelled"]
    current_stage: Optional[str] = None
    progress_pct: Optional[int] = Field(default=None, ge=0, le=100)
    error_message: Optional[str] = None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    script_id: Optional[str]
    character_id: Optional[str]
    voice_config_id: Optional[str]
    celery_task_id: Optional[str]
    status: str
    current_stage: str
    progress_pct: int
    retry_count: int
    max_retries: int
    compute_target: str
    checkpoint_json: Optional[dict[str, Any]]
    continuity_report_json: Optional[dict[str, Any]]
    output_mp4_path: Optional[str]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class JobLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: str
    level: str
    stage: str
    message: str
    vram_used_mb: Optional[int]
    created_at: datetime
