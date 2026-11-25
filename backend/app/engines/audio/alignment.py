from pathlib import Path
import re
from typing import Optional

from app.engines.audio.audio_processor import AudioProcessor
from app.engines.audio.schemas import (
    AlignmentResult,
    AlignmentValidation,
    PauseSegment,
    SentenceTiming,
    WordTiming,
)
from app.engines.audio.transcription import FasterWhisperTranscriber


class AudioAligner:
    """
    Produces sentence-level and word-level timestamps, detects inter-sentence
    pauses, preserves punctuation, and validates timing against actual WAV duration.
    """

    PAUSE_THRESHOLD_MS = 180

    def __init__(self, transcriber: Optional[FasterWhisperTranscriber] = None) -> None:
        self.transcriber = transcriber or FasterWhisperTranscriber()

    @staticmethod
    def _split_into_punctuated_sentences(words: list[WordTiming]) -> list[SentenceTiming]:
        if not words:
            return []

        sentences: list[SentenceTiming] = []
        buf: list[WordTiming] = []
        idx = 0

        for w in words:
            buf.append(w)
            if re.search(r"[.!?][\"'\)]*$", w.word):
                text = " ".join(x.word for x in buf).strip()
                sentences.append(
                    SentenceTiming(
                        index=idx,
                        text=text,
                        start_ms=buf[0].start_ms,
                        end_ms=buf[-1].end_ms,
                        words=list(buf),
                    )
                )
                idx += 1
                buf.clear()

        if buf:
            text = " ".join(x.word for x in buf).strip()
            sentences.append(
                SentenceTiming(
                    index=idx,
                    text=text,
                    start_ms=buf[0].start_ms,
                    end_ms=buf[-1].end_ms,
                    words=list(buf),
                )
            )
        return sentences

    @classmethod
    def _detect_pauses(cls, sentences: list[SentenceTiming]) -> list[PauseSegment]:
        pauses: list[PauseSegment] = []
        for i in range(len(sentences) - 1):
            gap = sentences[i + 1].start_ms - sentences[i].end_ms
            if gap >= cls.PAUSE_THRESHOLD_MS:
                pauses.append(
                    PauseSegment(
                        after_sentence_index=i,
                        start_ms=sentences[i].end_ms,
                        end_ms=sentences[i + 1].start_ms,
                        duration_ms=gap,
                    )
                )
        return pauses

    @staticmethod
    def _validate(
        words: list[WordTiming],
        audio_duration_ms: int,
        expected_script: str,
    ) -> AlignmentValidation:
        warnings: list[str] = []
        expected_words = len(re.findall(r"[A-Za-z0-9']+", expected_script))
        transcribed_words = len(words)
        coverage = round(transcribed_words / max(expected_words, 1), 4)

        monotonic_ok = True
        prev_start = 0
        for w in words:
            if w.start_ms < prev_start or w.end_ms < w.start_ms:
                monotonic_ok = False
                break
            prev_start = w.start_ms

        last_end = words[-1].end_ms if words else 0
        within_duration_ok = last_end <= (audio_duration_ms + 300)

        if not words:
            warnings.append("No words transcribed from generated audio.")
        if not monotonic_ok:
            warnings.append("Non-monotonic word timestamps detected.")
        if not within_duration_ok:
            warnings.append(
                f"Last word end ({last_end}ms) exceeds WAV duration ({audio_duration_ms}ms)."
            )
        if coverage < 0.75:
            warnings.append(
                f"Low word coverage ratio ({coverage:.2f}): expected ~{expected_words}, got {transcribed_words}."
            )

        passed = bool(words) and monotonic_ok and within_duration_ok and coverage >= 0.75
        return AlignmentValidation(
            audio_duration_ms=audio_duration_ms,
            last_word_end_ms=last_end,
            word_count_expected=expected_words,
            word_count_transcribed=transcribed_words,
            coverage_ratio=coverage,
            monotonic_ok=monotonic_ok,
            within_duration_ok=within_duration_ok,
            passed=passed,
            warnings=warnings,
        )

    def align(
        self, wav_path: Path, expected_script: str, language: str = "en"
    ) -> AlignmentResult:
        wav_info = AudioProcessor.inspect_wav(wav_path)
        audio_duration_sec = float(wav_info["duration_sec"])
        audio_duration_ms = int(round(audio_duration_sec * 1000))

        raw = self.transcriber.transcribe_with_words(wav_path, language=language)

        all_words: list[WordTiming] = []
        for seg in raw["segments"]:
            for w in seg["words"]:
                if not w["word"]:
                    continue
                # Clamp word timestamps strictly within actual WAV bounds
                start_ms = min(max(0, w["start_ms"]), audio_duration_ms)
                end_ms = min(max(start_ms, w["end_ms"]), audio_duration_ms)
                all_words.append(
                    WordTiming(
                        word=w["word"],
                        start_ms=start_ms,
                        end_ms=end_ms,
                        confidence=w["confidence"],
                    )
                )

        sentences = self._split_into_punctuated_sentences(all_words)
        pauses = self._detect_pauses(sentences)
        full_transcript = " ".join(s.text for s in sentences).strip()
        validation = self._validate(all_words, audio_duration_ms, expected_script)

        return AlignmentResult(
            language=raw.get("language", language),
            full_transcript=full_transcript,
            audio_duration_sec=audio_duration_sec,
            sentences=sentences,
            words=all_words,
            pauses=pauses,
            validation=validation,
        )
