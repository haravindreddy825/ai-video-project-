from abc import ABC, abstractmethod
from pathlib import Path
import re
from typing import Callable, Optional
import urllib.request

import numpy as np

from app.core.config import settings
from app.core.logging import logger
from app.core.storage import StorageManager
from app.core.vram import VRAMMonitor
from app.engines.audio.audio_processor import AudioProcessor
from app.engines.audio.emotion_planner import EmotionPlanner
from app.engines.audio.voice_manager import VoiceManager


KOKORO_ONNX_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
)
KOKORO_VOICES_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
)


class BaseTTSEngine(ABC):
    @abstractmethod
    def synthesize(
        self,
        text: str,
        output_wav_path: Path,
        voice_id: str = "af_heart",
        speed: float = 1.0,
        volume: float = 1.0,
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> dict:
        """Synthesize full narration text to a WAV file and return metadata."""


class KokoroONNXTTSEngine(BaseTTSEngine):
    """
    Kokoro-82M ONNX TTS engine (CPU-first for 6GB VRAM safety).
    Splits long scripts (2+ minutes) into phoneme-safe chunks (<=320 chars)
    so zero text is dropped, inserts natural pauses, and writes PCM_16 WAV.
    """

    SAMPLE_RATE = 24000
    MAX_CHUNK_CHARS = 320

    def __init__(self, models_dir: Optional[Path] = None, auto_download: bool = False) -> None:
        self.storage = StorageManager()
        self.models_dir = models_dir or (self.storage.models_dir / "kokoro")
        self.model_path = self.models_dir / settings.KOKORO_MODEL_FILENAME
        self.voices_path = self.models_dir / settings.KOKORO_VOICES_FILENAME
        self.auto_download = auto_download
        self._kokoro = None

    def ensure_models(self) -> tuple[Path, Path]:
        if self.model_path.exists() and self.voices_path.exists():
            return self.model_path, self.voices_path

        if not self.auto_download:
            raise FileNotFoundError(
                f"Kokoro ONNX model files not found in {self.models_dir}. "
                "Run `python scripts/download_audio_models.py` first."
            )

        self.storage.ensure_disk_budget()
        self.models_dir.mkdir(parents=True, exist_ok=True)
        for url, dest in (
            (KOKORO_ONNX_URL, self.model_path),
            (KOKORO_VOICES_URL, self.voices_path),
        ):
            if not dest.exists():
                logger.info("Downloading %s -> %s", url, dest)
                urllib.request.urlretrieve(url, dest)
        return self.model_path, self.voices_path

    def _load(self):
        if self._kokoro is not None:
            return self._kokoro

        ram = VRAMMonitor.get_ram_stats()
        if ram["available_gb"] < 1.0:
            raise MemoryError(
                f"Insufficient system RAM ({ram['available_gb']} GB available) to load Kokoro-82M."
            )

        model_path, voices_path = self.ensure_models()
        from kokoro_onnx import Kokoro

        self._kokoro = Kokoro(str(model_path), str(voices_path))
        return self._kokoro

    @classmethod
    def chunk_text(cls, text: str) -> list[str]:
        """Split long scripts into sentence/clause chunks <= MAX_CHUNK_CHARS without losing text."""
        sentences = EmotionPlanner.split_sentences(text)
        chunks: list[str] = []

        for sent in sentences:
            if len(sent) <= cls.MAX_CHUNK_CHARS:
                chunks.append(sent)
                continue

            # Split overly long sentences by punctuation/clauses, then by word budget
            sub_parts = re.split(r"(?<=[,;:])\s+", sent)
            current = ""
            for part in sub_parts:
                if len(part) > cls.MAX_CHUNK_CHARS:
                    words = part.split()
                    buf = ""
                    for w in words:
                        candidate = f"{buf} {w}".strip()
                        if len(candidate) <= cls.MAX_CHUNK_CHARS:
                            buf = candidate
                        else:
                            if buf:
                                chunks.append(buf)
                            buf = w
                    if buf:
                        chunks.append(buf)
                    continue

                candidate = f"{current} {part}".strip()
                if len(candidate) <= cls.MAX_CHUNK_CHARS:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    current = part
            if current:
                chunks.append(current)

        return chunks

    def synthesize(
        self,
        text: str,
        output_wav_path: Path,
        voice_id: str = "af_heart",
        speed: float = 1.0,
        volume: float = 1.0,
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> dict:
        VoiceManager.validate_voice_id(voice_id)
        chunks = self.chunk_text(text)
        if not chunks:
            raise ValueError("Cannot synthesize empty script text.")

        self.storage.ensure_disk_budget()
        kokoro = self._load()

        audio_parts: list[np.ndarray] = []
        inter_sentence_silence = np.zeros(int(self.SAMPLE_RATE * 0.18), dtype=np.float32)

        total = len(chunks)
        for idx, chunk in enumerate(chunks):
            if progress_cb:
                pct = 10 + int((idx / total) * 50)
                progress_cb(pct, f"Synthesizing chunk {idx + 1}/{total}")

            samples, sr = kokoro.create(
                chunk,
                voice=voice_id,
                speed=float(speed),
                lang="en-us",
            )
            audio_parts.append(np.asarray(samples, dtype=np.float32))
            if idx < total - 1:
                audio_parts.append(inter_sentence_silence)

        combined = np.concatenate(audio_parts)
        stats = AudioProcessor.apply_volume_and_save(
            combined, self.SAMPLE_RATE, output_wav_path, volume=volume
        )
        return {
            "engine": "kokoro-82m-onnx",
            "device": "cpu",
            "voice_id": voice_id,
            "chunks_count": total,
            **stats,
        }
