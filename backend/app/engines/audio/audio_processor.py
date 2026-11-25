from pathlib import Path
import numpy as np
import soundfile as sf


class AudioProcessor:
    """Handles WAV inspection, volume scaling, silence padding, and normalization."""

    @staticmethod
    def inspect_wav(wav_path: Path) -> dict[str, float | int]:
        data, sr = sf.read(str(wav_path), dtype="float32")
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        duration_sec = len(data) / float(sr) if sr > 0 else 0.0
        rms = float(np.sqrt(np.mean(np.square(data)))) if len(data) else 0.0
        peak = float(np.max(np.abs(data))) if len(data) else 0.0
        rms_db = float(20.0 * np.log10(max(rms, 1e-9)))
        peak_db = float(20.0 * np.log10(max(peak, 1e-9)))
        return {
            "sample_rate": int(sr),
            "samples": int(len(data)),
            "duration_sec": round(duration_sec, 4),
            "rms_db": round(rms_db, 2),
            "peak_db": round(peak_db, 2),
        }

    @staticmethod
    def apply_volume_and_save(
        samples: np.ndarray,
        sample_rate: int,
        output_path: Path,
        volume: float = 1.0,
    ) -> dict[str, float | int]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        audio = np.asarray(samples, dtype=np.float32)
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        if volume != 1.0:
            audio = audio * float(volume)

        # Prevent digital clipping while preserving dynamics
        peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
        if peak > 0.98:
            audio = audio * (0.98 / peak)

        sf.write(str(output_path), audio, sample_rate, subtype="PCM_16")
        return AudioProcessor.inspect_wav(output_path)
