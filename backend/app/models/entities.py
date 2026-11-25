from datetime import datetime, timezone
import uuid
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_duration_sec: Mapped[int] = mapped_column(Integer, default=120)
    resolution: Mapped[str] = mapped_column(String(20), default="1080x1920")
    layout_mode: Mapped[str] = mapped_column(String(40), default="top_bottom_50_50")
    compute_mode: Mapped[str] = mapped_column(String(30), default="local_hybrid")
    status: Mapped[str] = mapped_column(String(30), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    scripts: Mapped[list["Script"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    characters: Mapped[list["CharacterReference"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    voice_configs: Mapped[list["VoiceConfig"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["GenerationJob"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    beats_json: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    estimated_duration_sec: Mapped[float] = mapped_column(Float, default=120.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project: Mapped["Project"] = relationship(back_populates="scripts")


class CharacterReference(Base):
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    reference_image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    identity_pack_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project: Mapped["Project"] = relationship(back_populates="characters")


class VoiceConfig(Base):
    __tablename__ = "voice_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    engine: Mapped[str] = mapped_column(String(40), default="kokoro")
    preset_voice_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sample_audio_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    speaking_rate: Mapped[float] = mapped_column(Float, default=1.0)
    volume: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project: Mapped["Project"] = relationship(back_populates="voice_configs")


class AudioTrack(Base):
    __tablename__ = "audio_tracks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    script_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    voice_config_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    engine: Mapped[str] = mapped_column(String(40), default="kokoro")
    voice_id: Mapped[str] = mapped_column(String(80), default="af_heart")
    speed: Mapped[float] = mapped_column(Float, default=1.0)
    volume: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    audio_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sample_rate: Mapped[int] = mapped_column(Integer, default=24000)
    duration_sec: Mapped[float] = mapped_column(Float, default=0.0)
    original_script_text: Mapped[str] = mapped_column(Text, nullable=False)
    alignment_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    script_intelligence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class GenerationJob(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    script_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    character_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    voice_config_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    current_stage: Mapped[str] = mapped_column(String(60), default="queued")
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    compute_target: Mapped[str] = mapped_column(String(30), default="local_gpu")
    checkpoint_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    continuity_report_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_mp4_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    project: Mapped["Project"] = relationship(back_populates="jobs")
    logs: Mapped[list["JobLog"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class AvatarJob(Base):
    __tablename__ = "avatar_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    character_id: Mapped[str] = mapped_column(String(36), nullable=False)
    audio_id: Mapped[str] = mapped_column(String(36), nullable=False)
    adapter_used: Mapped[str] = mapped_column(String(60), default="local_expressive")
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[int] = mapped_column(Integer, default=1080)
    height: Mapped[int] = mapped_column(Integer, default=960)
    fps: Mapped[int] = mapped_column(Integer, default=25)
    duration_sec: Mapped[float] = mapped_column(Float, default=0.0)
    video_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    continuity_report_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class VisualScene(Base):
    __tablename__ = "visual_scenes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    audio_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=3000)
    sentence_text: Mapped[str] = mapped_column(Text, nullable=False)
    main_concept: Mapped[str] = mapped_column(String(200), default="Core Concept")
    keywords_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    visual_format: Mapped[str] = mapped_column(String(40), default="text_animation")
    visual_description: Mapped[str] = mapped_column(Text, default="")
    title_text: Mapped[str] = mapped_column(String(200), default="")
    body_bullets_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    diagram_spec_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    animation_style: Mapped[str] = mapped_column(String(40), default="slide_up")
    transition_style: Mapped[str] = mapped_column(String(40), default="crossfade")
    generator_used: Mapped[str] = mapped_column(String(40), default="programmatic")
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    video_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class VisualAsset(Base):
    __tablename__ = "visual_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("visual_scenes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    asset_type: Mapped[str] = mapped_column(String(40), default="rendered_png")
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=1080)
    height: Mapped[int] = mapped_column(Integer, default=960)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class VideoExport(Base):
    __tablename__ = "video_exports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    audio_id: Mapped[str] = mapped_column(String(36), nullable=False)
    avatar_job_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    encoder_used: Mapped[str] = mapped_column(String(40), default="libx264")
    include_subtitles: Mapped[bool] = mapped_column(default=True)
    width: Mapped[int] = mapped_column(Integer, default=1080)
    height: Mapped[int] = mapped_column(Integer, default=1920)
    fps: Mapped[int] = mapped_column(Integer, default=30)
    duration_sec: Mapped[float] = mapped_column(Float, default=0.0)
    output_mp4_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    subtitle_ass_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    validation_report_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    logs_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class FlowCharacter(Base):
    __tablename__ = "flow_characters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    appearance_prompt: Mapped[str] = mapped_column(Text, default="")
    reference_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class FlowProject(Base):
    __tablename__ = "flow_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    aspect_ratio: Mapped[str] = mapped_column(String(10), default="16:9")
    target_duration_sec: Mapped[int] = mapped_column(Integer, default=120)
    visual_style: Mapped[str] = mapped_column(String(80), default="cinematic")
    quality: Mapped[str] = mapped_column(String(30), default="lite")
    provider: Mapped[str] = mapped_column(String(40), default="veo_3_1")
    voice_id: Mapped[str] = mapped_column(String(80), default="af_heart")
    bgm_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sfx_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    final_mp4_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_sec: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class FlowScene(Base):
    __tablename__ = "flow_scenes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    flow_project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("flow_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    duration_sec: Mapped[int] = mapped_column(Integer, default=8)
    scene_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    narration_text: Mapped[str] = mapped_column(Text, default="")
    camera_motion: Mapped[str] = mapped_column(String(80), default="smooth_tracking")
    character_ids_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    first_frame_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_frame_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    video_clip_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    audio_clip_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    variation_index: Mapped[int] = mapped_column(Integer, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1)
    history_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    provider_used: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="planned")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class JobLog(Base):
    __tablename__ = "job_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    level: Mapped[str] = mapped_column(String(20), default="INFO")
    stage: Mapped[str] = mapped_column(String(60), default="system")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    vram_used_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    job: Mapped["GenerationJob"] = relationship(back_populates="logs")
