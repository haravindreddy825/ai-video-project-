from pathlib import Path
import re
import subprocess

import cv2
import imageio_ffmpeg
import numpy as np

from app.engines.compositor.schemas import ExportValidationReport


class ExportValidator:
    """
    Validates the final 1080x1920 MP4 output for exact resolution, 30 FPS,
    H.264/AAC codecs, yuv420p pixel format, zero black frames, non-empty
    top/bottom halves, and audio/video duration sync (< 120ms drift).
    """

    @staticmethod
    def _probe_codecs(mp4_path: Path) -> tuple[str, str, str]:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        proc = subprocess.run(
            [ffmpeg_exe, "-i", str(mp4_path.resolve())],
            capture_output=True,
            text=True,
        )
        info = proc.stderr or ""
        v_match = re.search(r"Video:\s*([a-zA-Z0-9_]+).*?\b(yuv\w+)\b", info, re.DOTALL)
        a_match = re.search(r"Audio:\s*([a-zA-Z0-9_]+)", info)
        v_codec = v_match.group(1) if v_match else "unknown"
        pix_fmt = v_match.group(2) if v_match else "unknown"
        a_codec = a_match.group(1) if a_match else "unknown"
        return v_codec, pix_fmt, a_codec

    @classmethod
    def validate(
        cls, mp4_path: Path, expected_audio_duration_sec: float
    ) -> ExportValidationReport:
        if not mp4_path.exists():
            raise FileNotFoundError(f"Exported MP4 not found: {mp4_path}")

        v_codec, pix_fmt, a_codec = cls._probe_codecs(mp4_path)

        cap = cv2.VideoCapture(str(mp4_path))
        if not cap.isOpened():
            raise RuntimeError(f"OpenCV could not open exported MP4: {mp4_path}")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = round(float(cap.get(cv2.CAP_PROP_FPS) or 0.0), 2)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration_sec = round(frame_count / fps, 4) if fps > 0 else 0.0
        drift_ms = round(abs(duration_sec - expected_audio_duration_sec) * 1000.0, 2)

        sample_indices = sorted(
            {
                0,
                max(0, frame_count // 4),
                max(0, frame_count // 2),
                max(0, (3 * frame_count) // 4),
                max(0, frame_count - 2),
            }
        )
        black_frames = 0
        checked = 0
        warnings: list[str] = []

        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                black_frames += 1
                continue
            checked += 1
            top_mean = float(np.mean(frame[:960, :, :]))
            bot_mean = float(np.mean(frame[960:, :, :]))
            if top_mean < 5.0 or bot_mean < 5.0:
                black_frames += 1

        cap.release()

        if width != 1080 or height != 1920:
            warnings.append(f"Unexpected resolution: {width}x{height} (expected 1080x1920)")
        if abs(fps - 30.0) > 0.5:
            warnings.append(f"Unexpected FPS: {fps} (expected 30)")
        if "h264" not in v_codec.lower():
            warnings.append(f"Unexpected video codec: {v_codec}")
        if "aac" not in a_codec.lower():
            warnings.append(f"Unexpected audio codec: {a_codec}")
        if "yuv420p" not in pix_fmt.lower():
            warnings.append(f"Unexpected pixel format: {pix_fmt}")
        if black_frames > 0:
            warnings.append(f"Detected {black_frames} black/unreadable sample frames")
        if drift_ms > 120.0:
            warnings.append(f"Audio/video drift {drift_ms}ms exceeds 120ms")

        passed = (
            width == 1080
            and height == 1920
            and abs(fps - 30.0) <= 0.5
            and "h264" in v_codec.lower()
            and "aac" in a_codec.lower()
            and "yuv420p" in pix_fmt.lower()
            and black_frames == 0
            and drift_ms <= 120.0
        )

        return ExportValidationReport(
            width=width,
            height=height,
            aspect_ratio="9:16" if width == 1080 and height == 1920 else f"{width}:{height}",
            fps=fps,
            video_codec=v_codec,
            audio_codec=a_codec,
            pixel_format=pix_fmt,
            duration_sec=duration_sec,
            audio_duration_sec=round(expected_audio_duration_sec, 4),
            av_drift_ms=drift_ms,
            black_frame_count=black_frames,
            samples_checked=checked,
            passed=passed,
            warnings=warnings,
        )
