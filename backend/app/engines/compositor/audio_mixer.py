from pathlib import Path
import subprocess

import imageio_ffmpeg


class AudioMixer:
    """
    Masters the authoritative Phase 2 narration WAV with EBU R128 loudness
    normalization (-16 LUFS) and 48kHz PCM output without altering duration.
    """

    def __init__(self) -> None:
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def prepare_master_audio(self, source_wav: Path, out_wav: Path) -> Path:
        if not source_wav.exists():
            raise FileNotFoundError(f"Authoritative narration WAV missing: {source_wav}")

        out_wav.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ffmpeg_exe,
            "-y",
            "-i",
            str(source_wav.resolve()),
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(out_wav.resolve()),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Audio mastering failed: {res.stderr[-300:]}")
        return out_wav
