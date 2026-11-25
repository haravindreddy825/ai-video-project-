import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
import redis.asyncio as aioredis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.storage import InsufficientDiskSpaceError, StorageManager
from app.core.vram import VRAMMonitor
from app.db.session import AsyncSessionLocal, get_db
from app.models.entities import (
    CharacterReference,
    GenerationJob,
    JobLog,
    Project,
    Script,
    VoiceConfig,
)
from app.schemas.studio import (
    CharacterResponse,
    JobCreate,
    JobLogResponse,
    JobResponse,
    JobStatusUpdate,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    ScriptCreate,
    ScriptResponse,
    VoiceConfigCreate,
    VoiceConfigResponse,
)
from app.workers.tasks import run_video_generation_job

router = APIRouter()
storage = StorageManager()


def _estimate_duration_sec(raw_text: str) -> float:
    words = len(raw_text.split())
    return round((words / 150.0) * 60.0, 2)


@router.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@router.get("/health/detailed", tags=["Health"])
async def detailed_health_check(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    redis_ok = False
    try:
        r = aioredis.from_url(
            settings.REDIS_URL, socket_timeout=1.0, socket_connect_timeout=1.0
        )
        await asyncio.wait_for(r.ping(), timeout=1.5)
        await r.aclose()
        redis_ok = True
    except Exception:
        redis_ok = False

    vram = VRAMMonitor.get_status()
    disk = storage.get_disk_stats()

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "redis": "connected" if redis_ok else "unreachable",
        "gpu": {
            "available": vram.available,
            "name": vram.gpu_name,
            "total_mb": vram.total_mb,
            "used_mb": vram.used_mb,
            "free_mb": vram.free_mb,
            "source": vram.source,
        },
        "storage": disk,
        "ram": VRAMMonitor.get_ram_stats(),
        "video_spec": {
            "resolution": f"{settings.OUTPUT_WIDTH}x{settings.OUTPUT_HEIGHT}",
            "layout": "top_bottom_50_50",
            "top_visuals": f"{settings.OUTPUT_WIDTH}x{settings.TOP_VISUAL_HEIGHT}",
            "bottom_avatar": f"{settings.OUTPUT_WIDTH}x{settings.BOTTOM_AVATAR_HEIGHT}",
        },
    }


@router.get("/api/v1/storage/stats", tags=["Storage"])
async def get_storage_stats() -> dict[str, float]:
    return storage.get_disk_stats()


# --- Projects ---
@router.post(
    "/api/v1/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Projects"],
)
async def create_project(
    payload: ProjectCreate, db: AsyncSession = Depends(get_db)
) -> Project:
    project = Project(
        title=payload.title,
        description=payload.description,
        target_duration_sec=payload.target_duration_sec,
        compute_mode=payload.compute_mode,
        resolution=f"{settings.OUTPUT_WIDTH}x{settings.OUTPUT_HEIGHT}",
        layout_mode="top_bottom_50_50",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/api/v1/projects", response_model=list[ProjectResponse], tags=["Projects"])
async def list_projects(db: AsyncSession = Depends(get_db)) -> list[Project]:
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    return list(result.scalars().all())


@router.get("/api/v1/projects/{project_id}", response_model=ProjectResponse, tags=["Projects"])
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)) -> Project:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/api/v1/projects/{project_id}", response_model=ProjectResponse, tags=["Projects"])
async def update_project(
    project_id: str, payload: ProjectUpdate, db: AsyncSession = Depends(get_db)
) -> Project:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project


@router.delete(
    "/api/v1/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Projects"],
)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)) -> None:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.commit()


@router.post(
    "/api/v1/projects/{project_id}/duplicate",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Projects"],
)
async def duplicate_project(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> Project:
    orig = await db.get(Project, project_id)
    if not orig:
        raise HTTPException(status_code=404, detail="Project not found")

    copy_proj = Project(
        title=f"{orig.title} (Copy)",
        description=orig.description,
        target_duration_sec=orig.target_duration_sec,
        resolution=orig.resolution,
        layout_mode=orig.layout_mode,
        compute_mode=orig.compute_mode,
        status="draft",
    )
    db.add(copy_proj)
    await db.flush()

    latest_script = (
        await db.execute(
            select(Script).where(Script.project_id == project_id).order_by(Script.version.desc())
        )
    ).scalars().first()
    if latest_script:
        db.add(
            Script(
                project_id=copy_proj.id,
                version=1,
                raw_text=latest_script.raw_text,
                beats_json=latest_script.beats_json,
                estimated_duration_sec=latest_script.estimated_duration_sec,
            )
        )

    chars = (
        await db.execute(
            select(CharacterReference).where(CharacterReference.project_id == project_id)
        )
    ).scalars().all()
    for ch in chars:
        db.add(
            CharacterReference(
                project_id=copy_proj.id,
                name=ch.name,
                reference_image_path=ch.reference_image_path,
                width=ch.width,
                height=ch.height,
                identity_pack_json=ch.identity_pack_json,
            )
        )

    voices = (
        await db.execute(
            select(VoiceConfig).where(VoiceConfig.project_id == project_id)
        )
    ).scalars().all()
    for vc in voices:
        db.add(
            VoiceConfig(
                project_id=copy_proj.id,
                engine=vc.engine,
                preset_voice_id=vc.preset_voice_id,
                sample_audio_path=vc.sample_audio_path,
                speaking_rate=vc.speaking_rate,
                volume=vc.volume,
            )
        )

    await db.commit()
    await db.refresh(copy_proj)
    return copy_proj


# --- Scripts ---
@router.post(
    "/api/v1/projects/{project_id}/scripts",
    response_model=ScriptResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Scripts"],
)
async def create_script(
    project_id: str, payload: ScriptCreate, db: AsyncSession = Depends(get_db)
) -> Script:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    existing = await db.execute(
        select(Script).where(Script.project_id == project_id).order_by(Script.version.desc())
    )
    latest = existing.scalars().first()
    next_version = (latest.version + 1) if latest else 1

    script = Script(
        project_id=project_id,
        version=next_version,
        raw_text=payload.raw_text,
        beats_json=payload.beats_json,
        estimated_duration_sec=_estimate_duration_sec(payload.raw_text),
    )
    db.add(script)
    await db.commit()
    await db.refresh(script)
    return script


@router.get(
    "/api/v1/projects/{project_id}/scripts",
    response_model=list[ScriptResponse],
    tags=["Scripts"],
)
async def list_scripts(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> list[Script]:
    result = await db.execute(
        select(Script).where(Script.project_id == project_id).order_by(Script.version.desc())
    )
    return list(result.scalars().all())


# --- Characters ---
@router.post(
    "/api/v1/projects/{project_id}/characters",
    response_model=CharacterResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Characters"],
)
async def upload_character(
    project_id: str,
    name: str = Form(...),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> CharacterReference:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        rel_path, width, height = await storage.save_character_image(project_id, image)
    except InsufficientDiskSpaceError as exc:
        raise HTTPException(status_code=507, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    char = CharacterReference(
        project_id=project_id,
        name=name,
        reference_image_path=rel_path,
        width=width,
        height=height,
        identity_pack_json={"source_width": width, "source_height": height, "locked": True},
    )
    db.add(char)
    await db.commit()
    await db.refresh(char)
    return char


@router.get(
    "/api/v1/projects/{project_id}/characters",
    response_model=list[CharacterResponse],
    tags=["Characters"],
)
async def list_characters(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> list[CharacterReference]:
    result = await db.execute(
        select(CharacterReference).where(CharacterReference.project_id == project_id)
    )
    return list(result.scalars().all())


# --- Voices ---
@router.post(
    "/api/v1/projects/{project_id}/voices",
    response_model=VoiceConfigResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Voices"],
)
async def configure_voice(
    project_id: str,
    engine: str = Form("kokoro"),
    preset_voice_id: str | None = Form("af_heart"),
    speaking_rate: float = Form(1.0),
    sample_audio: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
) -> VoiceConfig:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    validated = VoiceConfigCreate(
        engine=engine,  # type: ignore[arg-type]
        preset_voice_id=preset_voice_id,
        speaking_rate=speaking_rate,
    )

    sample_path: str | None = None
    if sample_audio is not None:
        try:
            sample_path = await storage.save_voice_sample(project_id, sample_audio)
        except InsufficientDiskSpaceError as exc:
            raise HTTPException(status_code=507, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    voice = VoiceConfig(
        project_id=project_id,
        engine=validated.engine,
        preset_voice_id=validated.preset_voice_id,
        sample_audio_path=sample_path,
        speaking_rate=validated.speaking_rate,
    )
    db.add(voice)
    await db.commit()
    await db.refresh(voice)
    return voice


@router.get(
    "/api/v1/projects/{project_id}/voices",
    response_model=list[VoiceConfigResponse],
    tags=["Voices"],
)
async def list_voices(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> list[VoiceConfig]:
    result = await db.execute(
        select(VoiceConfig).where(VoiceConfig.project_id == project_id)
    )
    return list(result.scalars().all())


# --- Generation Jobs ---
@router.post(
    "/api/v1/projects/{project_id}/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Jobs"],
)
async def create_generation_job(
    project_id: str,
    payload: JobCreate,
    dispatch: bool = True,
    db: AsyncSession = Depends(get_db),
) -> GenerationJob:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    job = GenerationJob(
        project_id=project_id,
        script_id=payload.script_id,
        character_id=payload.character_id,
        voice_config_id=payload.voice_config_id,
        max_retries=payload.max_retries,
        status="queued",
        current_stage="queued",
        progress_pct=0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    if dispatch:
        try:
            async_result = run_video_generation_job.apply_async(args=[job.id], queue="gpu")
            job.celery_task_id = async_result.id
            await db.commit()
            await db.refresh(job)
        except Exception as exc:
            # Record broker dispatch warning without losing the DB job record
            db.add(
                JobLog(
                    job_id=job.id,
                    level="WARNING",
                    stage="queued",
                    message=f"Celery dispatch deferred (broker unavailable): {exc}",
                )
            )
            await db.commit()

    return job


@router.get(
    "/api/v1/projects/{project_id}/jobs",
    response_model=list[JobResponse],
    tags=["Jobs"],
)
async def list_project_jobs(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> list[GenerationJob]:
    result = await db.execute(
        select(GenerationJob)
        .where(GenerationJob.project_id == project_id)
        .order_by(GenerationJob.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/api/v1/jobs/{job_id}", response_model=JobResponse, tags=["Jobs"])
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)) -> GenerationJob:
    job = await db.get(GenerationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/api/v1/jobs/{job_id}", response_model=JobResponse, tags=["Jobs"])
async def update_job_status(
    job_id: str, payload: JobStatusUpdate, db: AsyncSession = Depends(get_db)
) -> GenerationJob:
    job = await db.get(GenerationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    await db.commit()
    await db.refresh(job)
    return job


@router.post("/api/v1/jobs/{job_id}/retry", response_model=JobResponse, tags=["Jobs"])
async def retry_job(job_id: str, db: AsyncSession = Depends(get_db)) -> GenerationJob:
    job = await db.get(GenerationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = "queued"
    job.error_message = None
    try:
        async_result = run_video_generation_job.apply_async(args=[job.id], queue="gpu")
        job.celery_task_id = async_result.id
    except Exception:
        pass
    await db.commit()
    await db.refresh(job)
    return job


@router.get("/api/v1/jobs/{job_id}/logs", response_model=list[JobLogResponse], tags=["Jobs"])
async def get_job_logs(job_id: str, db: AsyncSession = Depends(get_db)) -> list[JobLog]:
    result = await db.execute(
        select(JobLog).where(JobLog.job_id == job_id).order_by(JobLog.id.asc())
    )
    return list(result.scalars().all())


@router.get("/api/v1/jobs/{job_id}/events", tags=["Jobs"])
async def stream_job_events(job_id: str):
    async def event_generator():
        for _ in range(30):
            async with AsyncSessionLocal() as session:
                job = await session.get(GenerationJob, job_id)
                if not job:
                    yield f"event: error\ndata: {json.dumps({'detail': 'Job not found'})}\n\n"
                    return
                payload = {
                    "id": job.id,
                    "status": job.status,
                    "current_stage": job.current_stage,
                    "progress_pct": job.progress_pct,
                }
                yield f"data: {json.dumps(payload)}\n\n"
                if job.status in {"completed", "failed", "cancelled"}:
                    return
            await asyncio.sleep(1.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
