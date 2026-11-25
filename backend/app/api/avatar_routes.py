from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.gpu_lock import CrossProcessGPULock
from app.core.logging import logger
from app.core.storage import InsufficientDiskSpaceError, StorageManager
from app.db.session import SyncSessionLocal, get_db
from app.engines.avatar.engine import AvatarEngineOrchestrator
from app.engines.avatar.identity_manager import CharacterIdentityManager
from app.engines.avatar.schemas import (
    AvatarGenerateRequest,
    AvatarJobResponse,
    CharacterIdentityPack,
)
from app.engines.avatar.timeline_driver import AvatarTimelineDriver
from app.models.entities import AudioTrack, AvatarJob, CharacterReference, Project
from app.schemas.studio import CharacterResponse

avatar_router = APIRouter()
storage = StorageManager()
identity_mgr = CharacterIdentityManager(storage)


def execute_avatar_pipeline(
    avatar_job_id: str,
    requested_adapter: str = "auto",
    chunk_duration_sec: float = 12.0,
) -> None:
    orchestrator = AvatarEngineOrchestrator()
    gpu_lock = CrossProcessGPULock()

    with SyncSessionLocal() as session:
        job = session.get(AvatarJob, avatar_job_id)
        if not job:
            return
        char = session.get(CharacterReference, job.character_id)
        track = session.get(AudioTrack, job.audio_id)
        if not char or not track or not track.audio_file_path:
            job.status = "failed"
            job.error_message = "Missing character reference or completed audio track."
            session.commit()
            return

        try:
            job.status = "running"
            job.progress_pct = 5
            session.commit()

            # Build or reuse canonical 1080x960 CharacterIdentityPack
            pack_dict = char.identity_pack_json or {}
            if "canonical_image_path" not in pack_dict:
                pack = identity_mgr.build_identity_pack(
                    char.id,
                    char.project_id,
                    char.reference_image_path,
                    approved=bool(pack_dict.get("approved", False)),
                )
                char.identity_pack_json = pack.model_dump()
                session.commit()
            else:
                pack = CharacterIdentityPack(**pack_dict)

            wav_path = (storage.root / track.audio_file_path).resolve()
            segments = AvatarTimelineDriver.build_segments(
                track.alignment_json,
                track.script_intelligence_json,
                track.duration_sec,
            )

            out_dir = storage.outputs_dir / job.project_id / "avatar"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_mp4 = out_dir / f"{job.id}.mp4"

            def _progress(pct: int, _msg: str) -> None:
                job.progress_pct = pct
                session.commit()

            with gpu_lock.acquire(owner=f"avatar-{job.id}"):
                adapter_used, report = orchestrator.render_with_fallback(
                    requested_adapter=requested_adapter,
                    identity_pack=pack,
                    audio_wav_path=wav_path,
                    segments=segments,
                    output_mp4_path=out_mp4,
                    fps=job.fps,
                    chunk_duration_sec=chunk_duration_sec,
                    progress_cb=_progress,
                )

            job.adapter_used = adapter_used
            job.video_file_path = str(out_mp4.relative_to(storage.root)).replace("\\", "/")
            job.duration_sec = report.video_duration_sec
            job.continuity_report_json = report.model_dump()
            job.status = "completed"
            job.progress_pct = 100
            job.error_message = None
            session.commit()
        except Exception as exc:
            logger.exception("Avatar animation failed for job %s", avatar_job_id)
            job.status = "failed"
            job.error_message = str(exc)
            session.commit()


@avatar_router.get("/api/v1/characters/{character_id}/preview", tags=["Characters"])
async def preview_canonical_character(
    character_id: str, db: AsyncSession = Depends(get_db)
):
    char = await db.get(CharacterReference, character_id)
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    pack_dict = char.identity_pack_json or {}
    if "canonical_image_path" not in pack_dict:
        pack = identity_mgr.build_identity_pack(
            char.id, char.project_id, char.reference_image_path
        )
        char.identity_pack_json = pack.model_dump()
        await db.commit()
        rel_path = pack.canonical_image_path
    else:
        rel_path = pack_dict["canonical_image_path"]

    img_path = (storage.root / rel_path).resolve()
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Canonical preview image missing")
    return FileResponse(str(img_path), media_type="image/png")


@avatar_router.post(
    "/api/v1/characters/{character_id}/approve",
    response_model=CharacterResponse,
    tags=["Characters"],
)
async def approve_character(
    character_id: str, db: AsyncSession = Depends(get_db)
) -> CharacterReference:
    char = await db.get(CharacterReference, character_id)
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    pack_dict = dict(char.identity_pack_json or {})
    if "canonical_image_path" not in pack_dict:
        pack = identity_mgr.build_identity_pack(
            char.id, char.project_id, char.reference_image_path, approved=True
        )
        char.identity_pack_json = pack.model_dump()
    else:
        pack_dict["approved"] = True
        char.identity_pack_json = pack_dict

    await db.commit()
    await db.refresh(char)
    return char


@avatar_router.post(
    "/api/v1/projects/{project_id}/avatar/generate",
    response_model=AvatarJobResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Avatar"],
)
async def generate_avatar_video(
    project_id: str,
    payload: AvatarGenerateRequest,
    background_tasks: BackgroundTasks,
    sync: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> AvatarJob:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        storage.ensure_disk_budget()
    except InsufficientDiskSpaceError as exc:
        raise HTTPException(status_code=507, detail=str(exc)) from exc

    char = await db.get(CharacterReference, payload.character_id)
    if not char or char.project_id != project_id:
        raise HTTPException(status_code=404, detail="Character not found in project")

    track = await db.get(AudioTrack, payload.audio_id)
    if not track or track.project_id != project_id or not track.audio_file_path:
        raise HTTPException(status_code=404, detail="Completed audio track not found in project")

    job = AvatarJob(
        project_id=project_id,
        character_id=payload.character_id,
        audio_id=payload.audio_id,
        adapter_used=payload.adapter,
        status="queued",
        progress_pct=0,
        fps=payload.fps,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    if sync:
        execute_avatar_pipeline(job.id, payload.adapter, payload.chunk_duration_sec)
        await db.refresh(job)
    else:
        background_tasks.add_task(
            execute_avatar_pipeline, job.id, payload.adapter, payload.chunk_duration_sec
        )

    return job


@avatar_router.get(
    "/api/v1/projects/{project_id}/avatar",
    response_model=list[AvatarJobResponse],
    tags=["Avatar"],
)
async def list_project_avatar_jobs(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> list[AvatarJob]:
    result = await db.execute(
        select(AvatarJob)
        .where(AvatarJob.project_id == project_id)
        .order_by(AvatarJob.created_at.desc())
    )
    return list(result.scalars().all())


@avatar_router.get("/api/v1/avatar/{avatar_job_id}", response_model=AvatarJobResponse, tags=["Avatar"])
async def get_avatar_job(
    avatar_job_id: str, db: AsyncSession = Depends(get_db)
) -> AvatarJob:
    job = await db.get(AvatarJob, avatar_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Avatar job not found")
    return job


@avatar_router.get("/api/v1/avatar/{avatar_job_id}/preview", tags=["Avatar"])
async def preview_avatar_video(
    avatar_job_id: str, db: AsyncSession = Depends(get_db)
):
    job = await db.get(AvatarJob, avatar_job_id)
    if not job or not job.video_file_path:
        raise HTTPException(status_code=404, detail="Avatar video not available")
    mp4_path = (storage.root / job.video_file_path).resolve()
    if not mp4_path.exists():
        raise HTTPException(status_code=404, detail="Avatar MP4 missing on disk")
    return FileResponse(str(mp4_path), media_type="video/mp4", filename=f"{avatar_job_id}.mp4")
