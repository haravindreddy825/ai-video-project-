from pathlib import Path
import subprocess
import time
from typing import Callable, Optional

import imageio_ffmpeg

from app.core.logging import logger


class ExportCancelledError(RuntimeError):
    """Raised when an active video export is cancelled by the user."""


class VerticalVideoCompositor:
    """
    Composes Top (1080x960 visuals) + Bottom (1080x960 avatar) into a
    1080x1920 vertical 9:16 30fps H.264/AAC MP4 synchronized to narration audio.
    """

    def __init__(self) -> None:
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def detect_nvenc(self) -> bool:
        cmd = [
            self.ffmpeg_exe,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=256x256:d=0.1",
            "-c:v",
            "h264_nvenc",
            "-f",
            "null",
            "-",
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=5)
            return res.returncode == 0
        except Exception:
            return False

    def compose(
        self,
        top_visuals_mp4: Path,
        bottom_avatar_mp4: Path,
        master_audio_wav: Path,
        output_mp4: Path,
        duration_sec: float,
        subtitle_ass: Optional[Path] = None,
        fps: int = 30,
        prefer_nvenc: bool = False,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> str:
        output_mp4.parent.mkdir(parents=True, exist_ok=True)

        use_nvenc = prefer_nvenc and self.detect_nvenc()
        encoder = "h264_nvenc" if use_nvenc else "libx264"

        filter_parts = [
            f"[0:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960,fps={fps},setsar=1[top]",
            f"[1:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960,fps={fps},setsar=1[bot]",
            "[top][bot]vstack=inputs=2[stacked]",
        ]

        cwd = str(output_mp4.parent.resolve())
        if subtitle_ass and subtitle_ass.exists():
            # Run with cwd=subtitle_ass.parent so relative filename avoids Windows drive colon escaping
            cwd = str(subtitle_ass.parent.resolve())
            filter_parts.append(f"[stacked]ass={subtitle_ass.name}[vout]")
            v_map = "[vout]"
        else:
            v_map = "[stacked]"

        filter_complex = ";".join(filter_parts)

        encode_args = (
            ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "21"]
            if use_nvenc
            else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
        )

        cmd = [
            self.ffmpeg_exe,
            "-y",
            "-i",
            str(top_visuals_mp4.resolve()),
            "-i",
            str(bottom_avatar_mp4.resolve()),
            "-i",
            str(master_audio_wav.resolve()),
            "-filter_complex",
            filter_complex,
            "-map",
            v_map,
            "-map",
            "2:a",
            *encode_args,
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(fps),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-t",
            f"{duration_sec:.3f}",
            "-movflags",
            "+faststart",
            str(output_mp4.resolve()),
        ]

        logger.info("Starting FFmpeg 1080x1920 composition (encoder=%s)", encoder)
        stderr_log = output_mp4.with_suffix(".ffmpeg.log")
        with open(stderr_log, "w", encoding="utf-8") as log_f:
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=log_f,
                text=True,
            )

            while proc.poll() is None:
                if cancel_check and cancel_check():
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    raise ExportCancelledError("Export cancelled by user.")
                time.sleep(0.3)

        stderr = stderr_log.read_text(encoding="utf-8", errors="ignore") if stderr_log.exists() else ""
        stderr_log.unlink(missing_ok=True)
        if proc.returncode != 0:
            raise RuntimeError(
                f"FFmpeg final composition failed ({proc.returncode}): {stderr[-500:]}"
            )

        return encoder
