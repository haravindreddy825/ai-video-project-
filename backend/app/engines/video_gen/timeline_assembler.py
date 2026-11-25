from pathlib import Path
import subprocess
from typing import Optional

import cv2
import imageio_ffmpeg

from app.core.storage import StorageManager
from app.engines.audio.tts_engine import KokoroONNXTTSEngine
from app.engines.compositor.audio_mixer import AudioMixer
from app.engines.compositor.subtitle_renderer import SubtitleRenderer
from app.engines.audio.alignment import AudioAligner


class FlowTimelineAssembler:
    """
    Assembles N generated AI video clips into one continuous 30s/60s/90s/120s MP4,
    normalizing aspect ratio (16:9 / 9:16 / 1:1), adding Kokoro-82M narration,
    optional BGM & SFX mixing, and synchronized ASS captions.
    """

    RESOLUTION_BY_AR = {
        "16:9": (1920, 1080),
        "9:16": (1080, 1920),
        "1:1": (1080, 1080),
    }

    def __init__(self, storage: Optional[StorageManager] = None) -> None:
        self.storage = storage or StorageManager()
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def assemble(
        self,
        project_id: str,
        clip_paths: list[Path],
        narration_script: str,
        aspect_ratio: str,
        voice_id: str,
        output_mp4: Path,
        bgm_path: Optional[Path] = None,
        sfx_path: Optional[Path] = None,
        include_subtitles: bool = True,
        fps: int = 30,
    ) -> dict:
        if not clip_paths:
            raise ValueError("No generated video clips available to assemble.")

        width, height = self.RESOLUTION_BY_AR.get(aspect_ratio, (1920, 1080))
        work_dir = self.storage.intermediate_dir / f"flow_{project_id}"
        work_dir.mkdir(parents=True, exist_ok=True)

        # 1. Normalize each generated clip to target resolution & FPS
        norm_clips: list[Path] = []
        for i, clip in enumerate(clip_paths):
            norm_out = work_dir / f"norm_{i:04d}.mp4"
            cmd = [
                self.ffmpeg_exe,
                "-y",
                "-i",
                str(clip.resolve()),
                "-vf",
                f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={fps},setsar=1",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                str(norm_out),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"Clip normalize failed ({i}): {res.stderr[-300:]}")
            norm_clips.append(norm_out)

        concat_txt = work_dir / "flow_concat.txt"
        concat_txt.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in norm_clips),
            encoding="utf-8",
        )
        stitched_v = work_dir / "stitched_video.mp4"
        res_cat = subprocess.run(
            [
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
                str(stitched_v),
            ],
            capture_output=True,
            text=True,
        )
        if res_cat.returncode != 0:
            raise RuntimeError(f"Video stitch failed: {res_cat.stderr[-300:]}")

        # 2. Generate narration via Kokoro-82M + optional alignment for captions
        narration_wav = work_dir / "narration.wav"
        tts = KokoroONNXTTSEngine(auto_download=False)
        tts_stats = tts.synthesize(narration_script, narration_wav, voice_id=voice_id)
        master_wav = work_dir / "master_narration.wav"
        AudioMixer().prepare_master_audio(narration_wav, master_wav)

        ass_path: Optional[Path] = None
        if include_subtitles:
            align_res = AudioAligner().align(narration_wav, narration_script)
            ass_path = work_dir / "flow_captions.ass"
            SubtitleRenderer.generate_ass(align_res.model_dump(), ass_path)

        # 3. Mix narration + optional BGM/SFX and burn subtitles
        output_mp4.parent.mkdir(parents=True, exist_ok=True)
        inputs = ["-i", str(stitched_v.resolve()), "-i", str(master_wav.resolve())]
        audio_filters = ["[1:a]volume=1.0[narr]"]
        mix_labels = ["[narr]"]

        if bgm_path and bgm_path.exists():
            idx = len(inputs) // 2
            inputs.extend(["-stream_loop", "-1", "-i", str(bgm_path.resolve())])
            audio_filters.append(f"[{idx}:a]volume=0.18[bgm]")
            mix_labels.append("[bgm]")
        if sfx_path and sfx_path.exists():
            idx = len(inputs) // 2
            inputs.extend(["-i", str(sfx_path.resolve())])
            audio_filters.append(f"[{idx}:a]volume=0.45[sfx]")
            mix_labels.append("[sfx]")

        if len(mix_labels) > 1:
            audio_filters.append(
                f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=2[aout]"
            )
            a_map = "[aout]"
        else:
            audio_filters = []
            a_map = "1:a"

        filter_parts = list(audio_filters)
        if ass_path and ass_path.exists():
            filter_parts.append(f"[0:v]ass={ass_path.name}[vout]")
            v_map = "[vout]"
        else:
            v_map = "0:v"

        final_cmd = [
            self.ffmpeg_exe,
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(filter_parts) if len(filter_parts) > 1 or v_map == "[vout]" else "",
        ]
        if final_cmd[-1] == "":
            final_cmd = final_cmd[:-2]
            final_cmd.extend(["-map", "0:v", "-map", "1:a"])
        else:
            final_cmd.extend(["-map", v_map, "-map", a_map])

        final_cmd.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                "-movflags",
                "+faststart",
                str(output_mp4.resolve()),
            ]
        )

        res_final = subprocess.run(
            final_cmd,
            cwd=str(work_dir.resolve()),
            capture_output=True,
            text=True,
        )
        if res_final.returncode != 0:
            raise RuntimeError(f"Flow final assembly failed: {res_final.stderr[-400:]}")

        cap = cv2.VideoCapture(str(output_mp4))
        fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        out_fps = cap.get(cv2.CAP_PROP_FPS) or float(fps)
        cap.release()
        return {
            "duration_sec": round(fc / out_fps, 2) if out_fps else float(tts_stats["duration_sec"]),
            "width": width,
            "height": height,
            "clips_count": len(clip_paths),
        }
