from pathlib import Path
from typing import Any, Optional

import numpy as np
import soundfile as sf

from app.core.config import settings
from app.core.logging import logger
from app.core.vram import ComputeRouter, VRAMMonitor


class FasterWhisperTranscriber:
    """
    Transcribes generated narration WAV using faster-whisper with word-level
    timestamps and punctuation preservation. Prefers CPU INT8 on 6GB laptops.
    """

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
    ) -> None:
        self.model_size = model_size or settings.ASR_MODEL_SIZE
        self.device = device or settings.AUDIO_EXECUTION_DEVICE
        self.compute_type = compute_type or settings.ASR_COMPUTE_TYPE
        self._model = None

    def _resolve_device(self) -> tuple[str, str]:
        if self.device == "cpu":
            return "cpu", "int8"
        if self.device in ("cuda", "auto"):
            target = ComputeRouter.select_target("faster-whisper")
            vram = VRAMMonitor.get_status()
            if target == "local_gpu" and vram.available and vram.free_mb >= 2500:
                return "cuda", "float16"
        return "cpu", "int8"

    def _load(self):
        if self._model is not None:
            return self._model

        from faster_whisper import WhisperModel

        dev, ctype = self._resolve_device()
        models_cache = settings.resolved_storage_root / "models" / "whisper"
        models_cache.mkdir(parents=True, exist_ok=True)
        logger.info("Loading faster-whisper (%s, device=%s, compute=%s)", self.model_size, dev, ctype)
        self._model = WhisperModel(
            self.model_size,
            device=dev,
            compute_type=ctype,
            download_root=str(models_cache),
        )
        return self._model

    @staticmethod
    def _load_audio_16k(wav_path: Path) -> np.ndarray:
        data, sr = sf.read(str(wav_path), dtype="float32")
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        if sr == 16000 or len(data) == 0:
            return data.astype(np.float32)
        target_len = int(round(len(data) * 16000.0 / float(sr)))
        x_old = np.linspace(0.0, 1.0, num=len(data), endpoint=False)
        x_new = np.linspace(0.0, 1.0, num=target_len, endpoint=False)
        return np.interp(x_new, x_old, data).astype(np.float32)

    def transcribe_with_words(
        self, wav_path: Path, language: str = "en", max_retries: int = 2
    ) -> dict[str, Any]:
        if not wav_path.exists():
            raise FileNotFoundError(f"Audio file not found for transcription: {wav_path}")

        audio_16k = self._load_audio_16k(wav_path)
        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                model = self._load()
                segments_iter, info = model.transcribe(
                    audio_16k,
                    language=language,
                    word_timestamps=True,
                    vad_filter=False,
                    condition_on_previous_text=True,
                )

                raw_segments: list[dict[str, Any]] = []
                for seg in segments_iter:
                    words = []
                    for w in seg.words or []:
                        words.append(
                            {
                                "word": w.word.strip(),
                                "start_ms": max(0, int(round(w.start * 1000))),
                                "end_ms": max(0, int(round(w.end * 1000))),
                                "confidence": round(float(getattr(w, "probability", 1.0)), 4),
                            }
                        )
                    raw_segments.append(
                        {
                            "text": seg.text.strip(),
                            "start_ms": max(0, int(round(seg.start * 1000))),
                            "end_ms": max(0, int(round(seg.end * 1000))),
                            "words": words,
                        }
                    )

                return {
                    "language": getattr(info, "language", language),
                    "duration_sec": float(getattr(info, "duration", 0.0)),
                    "segments": raw_segments,
                }
            except Exception as exc:
                last_exc = exc
                logger.warning("faster-whisper attempt %d/%d failed: %s", attempt, max_retries, exc)
                self._model = None

        raise RuntimeError(f"Transcription failed after {max_retries} attempts: {last_exc}")
