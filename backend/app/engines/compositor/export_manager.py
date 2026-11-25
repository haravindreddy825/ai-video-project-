from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.logging import logger
from app.core.storage import StorageManager
from app.db.session import SyncSessionLocal
from app.engines.compositor.audio_mixer import AudioMixer
from app.engines.compositor.compositor import (
    ExportCancelledError,
    VerticalVideoCompositor,
)
from app.engines.compositor.subtitle_renderer import SubtitleRenderer
from app.engines.compositor.timeline_builder import TimelineBuilder
from app.engines.compositor.validation import ExportValidator
from app.models.entities import AudioTrack, AvatarJob, VideoExport, VisualScene


class ExportManager:
    """Orchestrates Phase 5 final 1080x1920 MP4 composition, logging, and validation."""

    def __init__(self, storage: StorageManager | None = None) -> None:
        self.storage = storage or StorageManager()
        self.timeline_builder = TimelineBuilder(self.storage)
        self.audio_mixer = AudioMixer()
        self.compositor = VerticalVideoCompositor()

    @staticmethod
    def _append_log(session, export_job: VideoExport, stage: str, message: str) -> None:
        logs = list(export_job.logs_json or [])
        logs.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stage": stage,
                "message": message,
            }
        )
        export_job.logs_json = logs
        flag_modified(export_job, "logs_json")

    def run_export(self, export_id: str, prefer_nvenc: bool = False) -> None:
        work_dir = self.storage.intermediate_dir / f"export_{export_id}"
        work_dir.mkdir(parents=True, exist_ok=True)

        with SyncSessionLocal() as session:
            job = session.get(VideoExport, export_id)
            if not job:
                return
            if job.status == "cancelled":
                return

            track = session.get(AudioTrack, job.audio_id)
            avatar = session.get(AvatarJob, job.avatar_job_id)
            scenes = list(
                session.execute(
                    select(VisualScene)
                    .where(
                        VisualScene.project_id == job.project_id,
                        VisualScene.audio_id == job.audio_id,
                    )
                    .order_by(VisualScene.order_index.asc())
                )
                .scalars()
                .all()
            )

            if not track or not track.audio_file_path:
                job.status = "failed"
                job.error_message = "Completed Phase 2 audio track not found."
                session.commit()
                return
            if not avatar or not avatar.video_file_path:
                job.status = "failed"
                job.error_message = "Completed Phase 3 avatar video not found."
                session.commit()
                return
            if not scenes:
                job.status = "failed"
                job.error_message = "No Phase 4 visual scenes found for this audio."
                session.commit()
                return

            try:
                job.status = "running"
                job.progress_pct = 10
                self._append_log(session, job, "init", "Starting final 1080x1920 composition.")
                session.commit()

                # 1. Build top 1080x960 visual track from existing Phase 4 assets
                top_mp4 = self.timeline_builder.build_top_visual_track(
                    scenes=scenes,
                    target_duration_sec=track.duration_sec,
                    work_dir=work_dir,
                    fps=job.fps,
                )
                job.progress_pct = 35
                self._append_log(session, job, "visuals", f"Prepared top 1080x960 track ({len(scenes)} scenes).")
                session.commit()

                # 2. Master authoritative Phase 2 narration audio
                source_wav = (self.storage.root / track.audio_file_path).resolve()
                master_wav = work_dir / "master_audio.wav"
                self.audio_mixer.prepare_master_audio(source_wav, master_wav)
                job.progress_pct = 50
                self._append_log(session, job, "audio", "Mastered narration audio (-16 LUFS, 48kHz).")
                session.commit()

                # 3. Optional synchronized ASS captions
                ass_path: Path | None = None
                if job.include_subtitles:
                    ass_path = work_dir / "captions.ass"
                    SubtitleRenderer.generate_ass(track.alignment_json, ass_path)
                    job.subtitle_ass_path = str(ass_path.relative_to(self.storage.root)).replace("\\", "/")
                    self._append_log(session, job, "subtitles", "Generated ASS captions from word alignment.")
                    session.commit()

                # 4. Compose final 1080x1920 MP4
                out_dir = self.storage.outputs_dir / job.project_id / "exports"
                out_dir.mkdir(parents=True, exist_ok=True)
                out_mp4 = out_dir / f"{job.id}.mp4"
                avatar_mp4 = (self.storage.root / avatar.video_file_path).resolve()

                def _is_cancelled() -> bool:
                    with SyncSessionLocal() as check_sess:
                        fresh = check_sess.get(VideoExport, export_id)
                        return bool(fresh and fresh.status == "cancelled")

                encoder = self.compositor.compose(
                    top_visuals_mp4=top_mp4,
                    bottom_avatar_mp4=avatar_mp4,
                    master_audio_wav=master_wav,
                    output_mp4=out_mp4,
                    duration_sec=track.duration_sec,
                    subtitle_ass=ass_path,
                    fps=job.fps,
                    prefer_nvenc=prefer_nvenc,
                    cancel_check=_is_cancelled,
                )
                job.encoder_used = encoder
                job.progress_pct = 85
                self._append_log(session, job, "compose", f"Encoded final MP4 with {encoder}.")
                session.commit()

                # 5. Validate final MP4
                report = ExportValidator.validate(out_mp4, track.duration_sec)
                job.output_mp4_path = str(out_mp4.relative_to(self.storage.root)).replace("\\", "/")
                job.duration_sec = report.duration_sec
                job.validation_report_json = report.model_dump()
                job.status = "completed" if report.passed else "failed"
                job.progress_pct = 100
                if not report.passed:
                    job.error_message = "; ".join(report.warnings)
                self._append_log(
                    session,
                    job,
                    "validate",
                    f"Validation passed={report.passed}, drift={report.av_drift_ms}ms, black_frames={report.black_frame_count}.",
                )
                session.commit()
            except ExportCancelledError:
                job.status = "cancelled"
                self._append_log(session, job, "cancelled", "Export cancelled safely.")
                session.commit()
            except Exception as exc:
                logger.exception("Export failed for %s", export_id)
                job.status = "failed"
                job.error_message = str(exc)
                self._append_log(session, job, "error", str(exc))
                session.commit()
            finally:
                shutil.rmtree(work_dir, ignore_errors=True)
