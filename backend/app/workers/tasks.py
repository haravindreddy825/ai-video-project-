from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from celery import Task
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.core.gpu_lock import CrossProcessGPULock
from app.core.logging import logger
from app.core.vram import ComputeRouter, VRAMMonitor
from app.db.session import SyncSessionLocal
from app.models.entities import GenerationJob, JobLog
from app.workers.celery_app import celery_app


PIPELINE_STAGES = [
    ("script_planning", 10, False),
    ("voice_generation", 30, True),
    ("whisper_alignment", 45, True),
    ("visual_generation", 65, True),
    ("avatar_animation", 85, True),
    ("continuity_and_composite", 100, False),
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _save_checkpoint(job_id: str, checkpoint: dict[str, Any]) -> None:
    job_dir = settings.resolved_storage_root / "intermediate" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "checkpoint.json").write_text(
        json.dumps(checkpoint, indent=2), encoding="utf-8"
    )


def _log_job(
    session,
    job_id: str,
    stage: str,
    message: str,
    level: str = "INFO",
    vram_used_mb: int | None = None,
) -> None:
    session.add(
        JobLog(
            job_id=job_id,
            level=level,
            stage=stage,
            message=message,
            vram_used_mb=vram_used_mb,
        )
    )


@celery_app.task(name="app.workers.tasks.ping_worker")
def ping_worker(payload: str = "ping") -> dict[str, Any]:
    vram = VRAMMonitor.get_status()
    return {
        "status": "ok",
        "echo": payload,
        "gpu_name": vram.gpu_name,
        "vram_free_mb": vram.free_mb,
    }


@celery_app.task(
    bind=True,
    name="app.workers.tasks.run_video_generation_job",
    max_retries=3,
    default_retry_delay=5,
)
def run_video_generation_job(self: Task, job_id: str) -> dict[str, Any]:
    """
    Executes the 6-stage voice-first pipeline with:
    - Per-stage JSON checkpointing for crash/retry recovery
    - Cross-process GPU locking & VRAM monitoring on GPU stages
    - Automatic exponential-backoff retry on transient failures
    """
    gpu_lock = CrossProcessGPULock()

    with SyncSessionLocal() as session:
        job = session.get(GenerationJob, job_id)
        if not job:
            raise ValueError(f"GenerationJob {job_id} not found.")

        if job.status == "cancelled":
            return {"job_id": job_id, "status": "cancelled"}

        checkpoint: dict[str, Any] = dict(job.checkpoint_json or {})
        completed_stages = set(checkpoint.get("completed_stages", []))

        job.status = "running"
        job.started_at = job.started_at or _utcnow()
        job.compute_target = ComputeRouter.select_target(settings.AVATAR_ENGINE)
        _log_job(session, job_id, "init", f"Started job on {job.compute_target}")
        session.commit()

        try:
            for stage_name, pct, uses_gpu in PIPELINE_STAGES:
                if stage_name in completed_stages:
                    continue

                job.current_stage = stage_name
                session.commit()

                if uses_gpu:
                    with gpu_lock.acquire(owner=f"job-{job_id}-{stage_name}"):
                        vram = VRAMMonitor.get_status()
                        _log_job(
                            session,
                            job_id,
                            stage_name,
                            f"Executing GPU stage '{stage_name}' (Phase 1 core scaffold)",
                            vram_used_mb=vram.used_mb,
                        )
                else:
                    _log_job(
                        session,
                        job_id,
                        stage_name,
                        f"Executing CPU stage '{stage_name}' (Phase 1 core scaffold)",
                    )

                completed_stages.add(stage_name)
                checkpoint = {
                    **checkpoint,
                    "completed_stages": list(completed_stages),
                    "last_stage": stage_name,
                    "resolution": f"{settings.OUTPUT_WIDTH}x{settings.OUTPUT_HEIGHT}",
                }
                _save_checkpoint(job_id, checkpoint)

                job.checkpoint_json = checkpoint
                flag_modified(job, "checkpoint_json")
                job.progress_pct = pct
                session.commit()

            job.status = "completed"
            job.current_stage = "completed"
            job.completed_at = _utcnow()
            _log_job(session, job_id, "completed", "Pipeline stages completed cleanly.")
            session.commit()
            return {"job_id": job_id, "status": "completed", "progress_pct": 100}

        except Exception as exc:
            logger.exception("Job %s failed at stage %s", job_id, job.current_stage)
            job.retry_count += 1
            job.error_message = str(exc)

            if job.retry_count <= job.max_retries:
                job.status = "retrying"
                _log_job(
                    session,
                    job_id,
                    job.current_stage,
                    f"Retrying ({job.retry_count}/{job.max_retries}): {exc}",
                    level="WARNING",
                )
                session.commit()
                raise self.retry(exc=exc, countdown=2 ** job.retry_count)

            job.status = "failed"
            _log_job(
                session,
                job_id,
                job.current_stage,
                f"Job permanently failed: {exc}",
                level="ERROR",
            )
            session.commit()
            raise
