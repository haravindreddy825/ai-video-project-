"""
Optional model downloader for Phase 2 Audio & Alignment Pipeline.
Checks available disk space before downloading:
  - Kokoro-82M ONNX (~310 MB) + voices-v1.0.bin (~27 MB) [Apache-2.0]
  - faster-whisper base.en (~145 MB) [MIT]
"""
from pathlib import Path
import sys
import urllib.request

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.core.storage import StorageManager
from app.engines.audio.tts_engine import KOKORO_ONNX_URL, KOKORO_VOICES_URL


def main() -> None:
    storage = StorageManager()
    stats = storage.get_disk_stats()
    print(f"Disk free: {stats['free_gb']} GB (minimum required: {stats['min_free_gb']} GB)")
    storage.ensure_disk_budget()

    kokoro_dir = storage.models_dir / "kokoro"
    kokoro_dir.mkdir(parents=True, exist_ok=True)

    for url, filename in (
        (KOKORO_ONNX_URL, settings.KOKORO_MODEL_FILENAME),
        (KOKORO_VOICES_URL, settings.KOKORO_VOICES_FILENAME),
    ):
        dest = kokoro_dir / filename
        if dest.exists():
            print(f"[OK] Already exists: {dest}")
        else:
            print(f"[DL] Downloading {filename} ...")
            urllib.request.urlretrieve(url, dest)
            print(f"[OK] Saved: {dest} ({dest.stat().st_size / (1024*1024):.1f} MB)")

    whisper_dir = storage.models_dir / "whisper"
    whisper_dir.mkdir(parents=True, exist_ok=True)
    print(f"[DL] Ensuring faster-whisper '{settings.ASR_MODEL_SIZE}' (CPU INT8) ...")
    from faster_whisper import WhisperModel

    WhisperModel(
        settings.ASR_MODEL_SIZE,
        device="cpu",
        compute_type="int8",
        download_root=str(whisper_dir),
    )
    print("[OK] Audio & alignment models ready.")


if __name__ == "__main__":
    main()
