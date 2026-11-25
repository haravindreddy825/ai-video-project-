from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.storage import InsufficientDiskSpaceError, StorageManager
from app.db.session import AsyncSessionLocal, SyncSessionLocal, get_db
from app.engines.audio.alignment import AudioAligner
from app.engines.audio.emotion_planner import EmotionPlanner
from app.engines.audio.schemas import (
    AudioAlignRequest,
    AudioGenerateRequest,
    AudioTrackResponse,
    VoicePreset,
)
from app.engines.audio.tts_engine import KokoroONNXTTSEngine
from app.engines.audio.voice_manager import VoiceManager
from app.models.entities import AudioTrack, Project, Script

audio_router = APIRouter()
storage = StorageManager()


def execute_audio_pipeline(audio_id: str, auto_align: bool = True) -> None:
    """Runs Kokoro-82M TTS, EmotionPlanner, and faster-whisper alignment."""
    tts = KokoroONNXTTSEngine(auto_download=False)
    aligner = AudioAligner()

    with SyncSessionLocal() as session:
        track = session.get(AudioTrack, audio_id)
        if not track:
            return

        try:
            track.status = "generating"
            track.progress_pct = 5
            session.commit()

            def _progress(pct: int, _msg: str) -> None:
                track.progress_pct = pct
                session.commit()

            out_dir = storage.outputs_dir / track.project_id / "audio"
            out_dir.mkdir(parents=True, exist_ok=True)
            wav_path = out_dir / f"{track.id}.wav"

            tts_stats = tts.synthesize(
                text=track.original_script_text,
                output_wav_path=wav_path,
                voice_id=track.voice_id,
                speed=track.speed,
                volume=track.volume,
                progress_cb=_progress,
            )

            track.audio_file_path = str(wav_path.relative_to(storage.root)).replace("\\", "/")
            track.sample_rate = int(tts_stats["sample_rate"])
            track.duration_sec = float(tts_stats["duration_sec"])
            track.progress_pct = 65

            # Script intelligence (original_script_text remains untouched)
            intel = EmotionPlanner.analyze(track.original_script_text)
            track.script_intelligence_json = intel.model_dump()
            session.commit()

            if auto_align:
                track.status = "aligning"
                track.progress_pct = 75
                session.commit()
                alignment = aligner.align(wav_path, track.original_script_text)
                track.alignment_json = alignment.model_dump()

            track.status = "completed"
            track.progress_pct = 100
            track.error_message = None
            session.commit()
        except Exception as exc:
            logger.exception("Audio generation failed for track %s", audio_id)
            track.status = "failed"
            track.error_message = str(exc)
            session.commit()


@audio_router.get("/api/v1/audio/voices", response_model=list[VoicePreset], tags=["Audio"])
async def list_voice_presets() -> list[VoicePreset]:
    return VoiceManager.list_presets()


@audio_router.post(
    "/api/v1/projects/{project_id}/audio/generate",
    response_model=AudioTrackResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Audio"],
)
async def generate_project_audio(
    project_id: str,
    payload: AudioGenerateRequest,
    background_tasks: BackgroundTasks,
    sync: bool = Query(default=False, description="Run synchronously instead of background"),
    db: AsyncSession = Depends(get_db),
) -> AudioTrack:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        VoiceManager.validate_voice_id(payload.voice_id)
        storage.ensure_disk_budget()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except InsufficientDiskSpaceError as exc:
        raise HTTPException(status_code=507, detail=str(exc)) from exc

    script_text = payload.script_text
    if not script_text and payload.script_id:
        script = await db.get(Script, payload.script_id)
        if not script or script.project_id != project_id:
            raise HTTPException(status_code=404, detail="Script not found")
        script_text = script.raw_text

    if not script_text:
        raise HTTPException(
            status_code=400, detail="Either script_text or a valid script_id is required."
        )

    track = AudioTrack(
        project_id=project_id,
        script_id=payload.script_id,
        engine="kokoro",
        voice_id=payload.voice_id,
        speed=payload.speed,
        volume=payload.volume,
        status="queued",
        progress_pct=0,
        original_script_text=script_text,
    )
    db.add(track)
    await db.commit()
    await db.refresh(track)

    if sync:
        execute_audio_pipeline(track.id, auto_align=payload.auto_align)
        await db.refresh(track)
    else:
        background_tasks.add_task(execute_audio_pipeline, track.id, payload.auto_align)

    return track


@audio_router.get(
    "/api/v1/projects/{project_id}/audio",
    response_model=list[AudioTrackResponse],
    tags=["Audio"],
)
async def list_project_audio(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> list[AudioTrack]:
    result = await db.execute(
        select(AudioTrack)
        .where(AudioTrack.project_id == project_id)
        .order_by(AudioTrack.created_at.desc())
    )
    return list(result.scalars().all())


@audio_router.get("/api/v1/audio/{audio_id}", response_model=AudioTrackResponse, tags=["Audio"])
async def get_audio_track(
    audio_id: str, db: AsyncSession = Depends(get_db)
) -> AudioTrack:
    track = await db.get(AudioTrack, audio_id)
    if not track:
        raise HTTPException(status_code=404, detail="Audio track not found")
    return track


@audio_router.get("/api/v1/audio/{audio_id}/preview", tags=["Audio"])
async def preview_audio_file(audio_id: str, db: AsyncSession = Depends(get_db)):
    track = await db.get(AudioTrack, audio_id)
    if not track or not track.audio_file_path:
        raise HTTPException(status_code=404, detail="Audio file not available")
    wav_path = (storage.root / track.audio_file_path).resolve()
    if not wav_path.exists():
        raise HTTPException(status_code=404, detail="Audio file missing on disk")
    return FileResponse(str(wav_path), media_type="audio/wav", filename=f"{audio_id}.wav")


@audio_router.get("/api/v1/audio/{audio_id}/alignment", tags=["Audio"])
async def get_audio_alignment(
    audio_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    track = await db.get(AudioTrack, audio_id)
    if not track:
        raise HTTPException(status_code=404, detail="Audio track not found")
    if not track.alignment_json:
        raise HTTPException(status_code=404, detail="Alignment data not yet generated")
    return {
        "audio_id": track.id,
        "duration_sec": track.duration_sec,
        "alignment": track.alignment_json,
        "script_intelligence": track.script_intelligence_json,
    }


@audio_router.post("/api/v1/audio/{audio_id}/align", response_model=AudioTrackResponse, tags=["Audio"])
async def align_audio_track(
    audio_id: str,
    payload: AudioAlignRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> AudioTrack:
    track = await db.get(AudioTrack, audio_id)
    if not track or not track.audio_file_path:
        raise HTTPException(status_code=404, detail="Audio track or WAV file not found")

    wav_path = (storage.root / track.audio_file_path).resolve()
    if not wav_path.exists():
        raise HTTPException(status_code=404, detail="WAV file missing on disk")

    track.status = "aligning"
    track.progress_pct = 75
    await db.commit()

    try:
        aligner = AudioAligner()
        if payload and payload.model_size:
            aligner.transcriber.model_size = payload.model_size
        lang = payload.language if payload else "en"
        result = aligner.align(wav_path, track.original_script_text, language=lang)
        track.alignment_json = result.model_dump()
        track.status = "completed"
        track.progress_pct = 100
        track.error_message = None
    except Exception as exc:
        track.status = "failed"
        track.error_message = str(exc)

    await db.commit()
    await db.refresh(track)
    return track
