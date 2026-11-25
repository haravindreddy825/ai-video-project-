from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import InsufficientDiskSpaceError, StorageManager
from app.db.session import get_db
from app.engines.compositor.export_manager import ExportManager
from app.engines.compositor.schemas import ExportCreateRequest, VideoExportResponse
from app.models.entities import AudioTrack, AvatarJob, Project, VideoExport

export_router = APIRouter()
storage = StorageManager()
export_mgr = ExportManager(storage)


@export_router.post(
    "/api/v1/projects/{project_id}/exports",
    response_model=VideoExportResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Exports"],
)
async def create_video_export(
    project_id: str,
    payload: ExportCreateRequest,
    background_tasks: BackgroundTasks,
    sync: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> VideoExport:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        storage.ensure_disk_budget()
    except InsufficientDiskSpaceError as exc:
        raise HTTPException(status_code=507, detail=str(exc)) from exc

    track = await db.get(AudioTrack, payload.audio_id)
    if not track or track.project_id != project_id or not track.audio_file_path:
        raise HTTPException(status_code=404, detail="Completed audio track not found")

    avatar = await db.get(AvatarJob, payload.avatar_job_id)
    if not avatar or avatar.project_id != project_id or not avatar.video_file_path:
        raise HTTPException(status_code=404, detail="Completed avatar job not found")

    export_job = VideoExport(
        project_id=project_id,
        audio_id=payload.audio_id,
        avatar_job_id=payload.avatar_job_id,
        include_subtitles=payload.include_subtitles,
        fps=payload.fps,
        status="queued",
        progress_pct=0,
    )
    db.add(export_job)
    await db.commit()
    await db.refresh(export_job)

    if sync:
        export_mgr.run_export(export_job.id, prefer_nvenc=payload.prefer_nvenc)
        await db.refresh(export_job)
    else:
        background_tasks.add_task(
            export_mgr.run_export, export_job.id, payload.prefer_nvenc
        )

    return export_job


@export_router.get(
    "/api/v1/projects/{project_id}/exports",
    response_model=list[VideoExportResponse],
    tags=["Exports"],
)
async def list_project_exports(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> list[VideoExport]:
    result = await db.execute(
        select(VideoExport)
        .where(VideoExport.project_id == project_id)
        .order_by(VideoExport.created_at.desc())
    )
    return list(result.scalars().all())


@export_router.get(
    "/api/v1/exports/{export_id}",
    response_model=VideoExportResponse,
    tags=["Exports"],
)
async def get_export_status(
    export_id: str, db: AsyncSession = Depends(get_db)
) -> VideoExport:
    job = await db.get(VideoExport, export_id)
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")
    return job


@export_router.get("/api/v1/exports/{export_id}/preview", tags=["Exports"])
async def preview_final_video(
    export_id: str, db: AsyncSession = Depends(get_db)
):
    job = await db.get(VideoExport, export_id)
    if not job or not job.output_mp4_path:
        raise HTTPException(status_code=404, detail="Exported MP4 not available")
    mp4_path = (storage.root / job.output_mp4_path).resolve()
    if not mp4_path.exists():
        raise HTTPException(status_code=404, detail="Exported MP4 missing on disk")
    return FileResponse(str(mp4_path), media_type="video/mp4")


@export_router.get("/api/v1/exports/{export_id}/download", tags=["Exports"])
async def download_final_video(
    export_id: str, db: AsyncSession = Depends(get_db)
):
    job = await db.get(VideoExport, export_id)
    if not job or not job.output_mp4_path:
        raise HTTPException(status_code=404, detail="Exported MP4 not available")
    mp4_path = (storage.root / job.output_mp4_path).resolve()
    if not mp4_path.exists():
        raise HTTPException(status_code=404, detail="Exported MP4 missing on disk")
    return FileResponse(
        str(mp4_path),
        media_type="video/mp4",
        filename=f"ai_video_studio_{export_id}.mp4",
    )


@export_router.post(
    "/api/v1/exports/{export_id}/cancel",
    response_model=VideoExportResponse,
    tags=["Exports"],
)
async def cancel_export(
    export_id: str, db: AsyncSession = Depends(get_db)
) -> VideoExport:
    job = await db.get(VideoExport, export_id)
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")
    if job.status in ("queued", "running"):
        job.status = "cancelled"
        await db.commit()
        await db.refresh(job)
    return job


@export_router.post(
    "/api/v1/exports/{export_id}/re-export",
    response_model=VideoExportResponse,
    tags=["Exports"],
)
async def re_export_video(
    export_id: str,
    background_tasks: BackgroundTasks,
    sync: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> VideoExport:
    old = await db.get(VideoExport, export_id)
    if not old:
        raise HTTPException(status_code=404, detail="Export job not found")

    new_job = VideoExport(
        project_id=old.project_id,
        audio_id=old.audio_id,
        avatar_job_id=old.avatar_job_id,
        include_subtitles=old.include_subtitles,
        fps=old.fps,
        status="queued",
        progress_pct=0,
    )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)

    if sync:
        export_mgr.run_export(new_job.id)
        await db.refresh(new_job)
    else:
        background_tasks.add_task(export_mgr.run_export, new_job.id)
    return new_job
