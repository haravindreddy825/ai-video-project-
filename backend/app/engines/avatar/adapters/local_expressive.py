import math
from pathlib import Path
import subprocess
from typing import Callable, Optional

import cv2
import imageio_ffmpeg
import numpy as np

from app.core.logging import logger
from app.core.storage import StorageManager
from app.engines.avatar.adapters.base import BaseAvatarAdapter
from app.engines.avatar.continuity import ContinuityVerifier
from app.engines.avatar.schemas import (
    AvatarTimelineSegment,
    CharacterIdentityPack,
    ContinuityReport,
)
from app.engines.avatar.timeline_driver import AvatarTimelineDriver


class LocalExpressiveAvatarAdapter(BaseAvatarAdapter):
    """
    Local 6GB-safe, identity-locked expressive avatar animation engine (OpenCV + FFmpeg).
    Drives:
      - Audio-synchronized lip/jaw opening (closed during pauses)
      - 9 facial expressions (happy, serious, curious, surprised, thinking,
        explaining, confident, concerned, neutral)
      - Natural periodic blinking & eye micro-gaze
      - Script-aligned head tilts, nods, and upper-body breathing/sway
      - Chunked rendering with boundary SSIM continuity verification
    """

    name = "local_expressive"

    EMOTION_PARAMS: dict[str, tuple[float, float, float]] = {
        # (brow_lift_px, smile_curve_px, target_head_tilt_deg)
        "happy": (2.5, 4.0, 0.8),
        "serious": (-2.0, -1.0, -0.3),
        "curious": (3.5, 1.0, 2.2),
        "surprised": (5.0, 1.5, -0.5),
        "thinking": (1.5, -0.5, 1.8),
        "explaining": (2.0, 2.0, 0.6),
        "confident": (1.5, 3.0, 0.0),
        "concerned": (-2.5, -2.0, -1.2),
        "neutral": (0.0, 0.0, 0.0),
    }

    def __init__(self, storage: Optional[StorageManager] = None) -> None:
        self.storage = storage or StorageManager()
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    @staticmethod
    def _segment_at_ms(
        segments: list[AvatarTimelineSegment], t_ms: int
    ) -> AvatarTimelineSegment:
        for seg in segments:
            if seg.start_ms <= t_ms <= seg.end_ms:
                return seg
        return segments[-1] if segments else AvatarTimelineSegment(index=0, start_ms=0, end_ms=1000)

    @staticmethod
    def _blink_factor(t_sec: float) -> float:
        """Return 0.0 (open) to 1.0 (closed) for natural ~3.4s blink cycle."""
        period = 3.4
        phase = t_sec % period
        if 3.15 <= phase <= 3.31:
            # Smooth sine pulse over 160ms
            return math.sin(math.pi * (phase - 3.15) / 0.16)
        return 0.0

    @classmethod
    def _render_frame(
        cls,
        base_img: np.ndarray,
        pack: CharacterIdentityPack,
        t_sec: float,
        speech_energy: float,
        seg: AvatarTimelineSegment,
        grid_x: np.ndarray,
        grid_y: np.ndarray,
    ) -> np.ndarray:
        h, w = base_img.shape[:2]
        brow_lift, smile_px, target_tilt = cls.EMOTION_PARAMS.get(
            seg.emotion, (0.0, 0.0, 0.0)
        )

        # 1. Lip & jaw displacement driven by speech energy (0 during pauses)
        mouth_open = 0.0 if seg.is_pause else float(speech_energy)
        mx, my = float(pack.mouth_center.x), float(pack.mouth_center.y)
        face_w = float(pack.face_box.w)
        mouth_rx = max(18.0, face_w * 0.22)
        mouth_ry = max(12.0, face_w * 0.14)

        dx = np.zeros_like(grid_x)
        dy = np.zeros_like(grid_y)

        # Localized mouth/jaw warp
        dist_m2 = ((grid_x - mx) / mouth_rx) ** 2 + ((grid_y - my) / mouth_ry) ** 2
        mouth_mask = np.exp(-np.clip(dist_m2, 0.0, 8.0))
        # Lower lip moves down when speaking; mouth corners lift/drop with smile_px
        lower_half = np.where(grid_y >= my, 1.0, -0.25)
        dy -= mouth_mask * lower_half * (mouth_open * 10.0)
        corner_factor = np.clip(np.abs(grid_x - mx) / mouth_rx, 0.0, 1.2)
        dy += mouth_mask * corner_factor * (smile_px * 0.8)

        # 2. Natural blinking & eyebrow expression
        blink = cls._blink_factor(t_sec)
        eye_rx = max(12.0, face_w * 0.11)
        eye_ry = max(7.0, face_w * 0.06)
        for eye in (pack.eye_left, pack.eye_right):
            ex, ey = float(eye.x), float(eye.y)
            d_eye2 = ((grid_x - ex) / eye_rx) ** 2 + ((grid_y - ey) / eye_ry) ** 2
            eye_mask = np.exp(-np.clip(d_eye2, 0.0, 8.0))
            upper_lid = np.where(grid_y <= ey, 1.0, -0.3)
            dy -= eye_mask * upper_lid * (blink * 5.5)
            # Eyebrow region slightly above eye
            d_brow2 = ((grid_x - ex) / (eye_rx * 1.2)) ** 2 + (
                (grid_y - (ey - eye_ry * 1.6)) / (eye_ry * 1.1)
            ) ** 2
            brow_mask = np.exp(-np.clip(d_brow2, 0.0, 8.0))
            dy += brow_mask * (brow_lift * 0.7)

        # Remap facial expressions onto base image
        map_x = (grid_x + dx).astype(np.float32)
        map_y = (grid_y + dy).astype(np.float32)
        expr_img = cv2.remap(
            base_img,
            map_x,
            map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )

        # 3. Head tilt, nod & upper-body breathing/gesture sway
        breath_y = math.sin(2.0 * math.pi * 0.28 * t_sec) * 2.2
        gesture_amp = 1.0 if not seg.is_pause else 0.25
        if "nod" in seg.head_movement:
            breath_y += math.sin(2.0 * math.pi * 1.1 * t_sec) * 3.0 * gesture_amp

        sway_x = math.sin(2.0 * math.pi * 0.42 * t_sec) * 3.5 * gesture_amp
        if "pointing" in seg.hand_gesture or "open_palm" in seg.hand_gesture:
            sway_x += math.sin(2.0 * math.pi * 0.85 * t_sec) * 2.5 * gesture_amp

        angle = target_tilt + math.sin(2.0 * math.pi * 0.35 * t_sec) * 0.7 * gesture_amp
        scale = 1.015  # Slight zoom prevents any edge artifacts during affine motion
        center = (w * 0.5, pack.shoulder_y * 0.75)
        mat = cv2.getRotationMatrix2D(center, angle, scale)
        mat[0, 2] += sway_x
        mat[1, 2] += breath_y

        animated = cv2.warpAffine(
            expr_img,
            mat,
            (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return animated

    def _encode_chunk_ffmpeg(
        self,
        frames: list[np.ndarray],
        out_mp4: Path,
        fps: int,
        width: int,
        height: int,
    ) -> None:
        cmd = [
            self.ffmpeg_exe,
            "-y",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{width}x{height}",
            "-r",
            str(fps),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            str(out_mp4),
        ]
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        assert proc.stdin is not None
        for frame in frames:
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        stderr = proc.stderr.read().decode("utf-8", errors="ignore") if proc.stderr else ""
        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(f"FFmpeg chunk encode failed ({ret}): {stderr[-400:]}")

    def render(
        self,
        identity_pack: CharacterIdentityPack,
        audio_wav_path: Path,
        segments: list[AvatarTimelineSegment],
        output_mp4_path: Path,
        fps: int = 25,
        chunk_duration_sec: float = 12.0,
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> ContinuityReport:
        canonical_path = (self.storage.root / identity_pack.canonical_image_path).resolve()
        base_img = cv2.imread(str(canonical_path), cv2.IMREAD_COLOR)
        if base_img is None:
            raise FileNotFoundError(f"Canonical character image missing: {canonical_path}")

        h, w = base_img.shape[:2]
        envelope, duration_sec = AvatarTimelineDriver.extract_audio_envelope(
            audio_wav_path, fps=fps
        )
        total_frames = len(envelope)
        frames_per_chunk = max(fps, int(round(chunk_duration_sec * fps)))

        grid_x, grid_y = np.meshgrid(
            np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32)
        )

        work_dir = output_mp4_path.parent / f"_chunks_{output_mp4_path.stem}"
        work_dir.mkdir(parents=True, exist_ok=True)

        chunk_paths: list[Path] = []
        boundary_ssim: list[float] = []
        prev_last_frame: np.ndarray | None = None

        num_chunks = max(1, math.ceil(total_frames / frames_per_chunk))
        for c_idx in range(num_chunks):
            f_start = c_idx * frames_per_chunk
            f_end = min(total_frames, f_start + frames_per_chunk)
            chunk_frames: list[np.ndarray] = []

            for f_idx in range(f_start, f_end):
                t_sec = f_idx / float(fps)
                t_ms = int(round(t_sec * 1000))
                seg = self._segment_at_ms(segments, t_ms)
                frame = self._render_frame(
                    base_img,
                    identity_pack,
                    t_sec,
                    float(envelope[f_idx]),
                    seg,
                    grid_x,
                    grid_y,
                )
                chunk_frames.append(frame)

            if prev_last_frame is not None and chunk_frames:
                score = ContinuityVerifier.compute_frame_ssim(prev_last_frame, chunk_frames[0])
                boundary_ssim.append(score)
            if chunk_frames:
                prev_last_frame = chunk_frames[-1]

            chunk_mp4 = work_dir / f"chunk_{c_idx:04d}.mp4"
            self._encode_chunk_ffmpeg(chunk_frames, chunk_mp4, fps, w, h)
            chunk_paths.append(chunk_mp4)

            if progress_cb:
                pct = 20 + int(((c_idx + 1) / num_chunks) * 65)
                progress_cb(pct, f"Rendered avatar chunk {c_idx + 1}/{num_chunks}")

        # Concatenate chunks & mux with original Phase 2 audio
        concat_list = work_dir / "concat.txt"
        concat_list.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in chunk_paths),
            encoding="utf-8",
        )
        output_mp4_path.parent.mkdir(parents=True, exist_ok=True)

        mux_cmd = [
            self.ffmpeg_exe,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-i",
            str(audio_wav_path.resolve()),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_mp4_path.resolve()),
        ]
        res = subprocess.run(mux_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg final mux failed: {res.stderr[-400:]}")

        # Clean up temporary chunk files
        for p in chunk_paths:
            p.unlink(missing_ok=True)
        concat_list.unlink(missing_ok=True)
        try:
            work_dir.rmdir()
        except OSError:
            pass

        if progress_cb:
            progress_cb(95, "Verifying frame & audio continuity")

        report = ContinuityVerifier.verify_output(
            output_mp4_path, duration_sec, boundary_ssim
        )
        logger.info(
            "Avatar MP4 rendered (%s): drift=%.2fms, ssim_min=%.4f, passed=%s",
            output_mp4_path.name,
            report.av_drift_ms,
            report.boundary_ssim_min,
            report.passed,
        )
        return report
