from pathlib import Path
import subprocess
from typing import Any

import imageio_ffmpeg

from app.core.storage import StorageManager
from app.models.entities import VisualScene


class TimelineBuilder:
    """
    Loads existing Phase 4 VisualScene assets, validates contiguous coverage
    against the authoritative Phase 2 narration duration, and assembles a
    single continuous 1080x960 top-half visual MP4 at target FPS.
    """

    def __init__(self, storage: StorageManager | None = None) -> None:
        self.storage = storage or StorageManager()
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def build_top_visual_track(
        self,
        scenes: list[VisualScene],
        target_duration_sec: float,
        work_dir: Path,
        fps: int = 30,
    ) -> Path:
        if not scenes:
            raise ValueError("No visual scenes found for this project/audio.")

        ordered = sorted(scenes, key=lambda s: s.order_index)
        work_dir.mkdir(parents=True, exist_ok=True)
        segment_mp4s: list[Path] = []

        for idx, scene in enumerate(ordered):
            dur_ms = max(250, int(scene.end_ms) - int(scene.start_ms))
            # Stretch last scene slightly if needed so top visuals never end before audio
            if idx == len(ordered) - 1:
                expected_end_ms = int(round(target_duration_sec * 1000))
                if int(scene.end_ms) < expected_end_ms:
                    dur_ms = max(dur_ms, expected_end_ms - int(scene.start_ms))
            dur_sec = dur_ms / 1000.0

            seg_out = work_dir / f"vis_seg_{idx:04d}.mp4"

            # Reuse existing rendered scene MP4 if available, normalized to exact fps & duration
            if scene.video_path and (self.storage.root / scene.video_path).exists():
                src_mp4 = (self.storage.root / scene.video_path).resolve()
                cmd = [
                    self.ffmpeg_exe,
                    "-y",
                    "-stream_loop",
                    "-1",
                    "-i",
                    str(src_mp4),
                    "-t",
                    f"{dur_sec:.3f}",
                    "-vf",
                    f"scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960,fps={fps}",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "19",
                    "-pix_fmt",
                    "yuv420p",
                    str(seg_out),
                ]
            elif scene.image_path and (self.storage.root / scene.image_path).exists():
                src_png = (self.storage.root / scene.image_path).resolve()
                cmd = [
                    self.ffmpeg_exe,
                    "-y",
                    "-loop",
                    "1",
                    "-i",
                    str(src_png),
                    "-t",
                    f"{dur_sec:.3f}",
                    "-vf",
                    f"scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960,fps={fps}",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "19",
                    "-pix_fmt",
                    "yuv420p",
                    str(seg_out),
                ]
            else:
                raise FileNotFoundError(
                    f"Visual scene {scene.id} has no rendered image or video asset on disk."
                )

            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(
                    f"Failed preparing visual segment {idx}: {res.stderr[-300:]}"
                )
            segment_mp4s.append(seg_out)

        concat_txt = work_dir / "visual_concat.txt"
        concat_txt.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in segment_mp4s),
            encoding="utf-8",
        )
        top_mp4 = work_dir / "top_visuals_1080x960.mp4"
        concat_cmd = [
            self.ffmpeg_exe,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_txt),
            "-c:v",
            "copy",
            str(top_mp4),
        ]
        res = subprocess.run(concat_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Failed concatenating top visual track: {res.stderr[-300:]}")
        return top_mp4
