from pathlib import Path
import numpy as np
import soundfile as sf

from app.engines.avatar.schemas import AvatarTimelineSegment, EmotionType


class AvatarTimelineDriver:
    """
    Converts Phase 2 alignment_json, script_intelligence_json, and WAV audio
    into frame-level speech energy + emotion/gesture/head-motion timeline segments.
    """

    EMOTION_MAP: dict[str, EmotionType] = {
        "happy": "happy",
        "enthusiastic": "happy",
        "serious": "serious",
        "curious": "curious",
        "surprised": "surprised",
        "thinking": "thinking",
        "explaining": "explaining",
        "confident": "confident",
        "concerned": "concerned",
        "calm": "explaining",
        "neutral": "neutral",
    }

    @classmethod
    def extract_audio_envelope(
        cls, wav_path: Path, fps: int = 25
    ) -> tuple[np.ndarray, float]:
        """Return normalized per-frame speech energy [0..1] and exact WAV duration_sec."""
        data, sr = sf.read(str(wav_path), dtype="float32")
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        duration_sec = len(data) / float(sr) if sr > 0 else 0.0
        total_frames = max(1, int(round(duration_sec * fps)))
        samples_per_frame = max(1, int(sr / fps))

        rms_values = np.zeros(total_frames, dtype=np.float32)
        for i in range(total_frames):
            start = i * samples_per_frame
            end = min(len(data), start + samples_per_frame)
            if start < len(data):
                chunk = data[start:end]
                rms_values[i] = float(np.sqrt(np.mean(np.square(chunk))))

        # Normalize using 95th percentile so loud peaks don't crush normal speech
        ref = float(np.percentile(rms_values, 95)) if len(rms_values) else 1.0
        ref = max(ref, 1e-4)
        norm = np.clip(rms_values / ref, 0.0, 1.0)

        # Smooth envelope slightly (3-frame moving average) for natural jaw inertia
        kernel = np.array([0.25, 0.5, 0.25], dtype=np.float32)
        smoothed = np.convolve(norm, kernel, mode="same")
        # Noise gate so mouth stays closed during silence/pauses
        smoothed[smoothed < 0.06] = 0.0
        return smoothed, duration_sec

    @classmethod
    def build_segments(
        cls,
        alignment_json: dict | None,
        script_intelligence_json: dict | None,
        duration_sec: float,
    ) -> list[AvatarTimelineSegment]:
        total_ms = max(100, int(round(duration_sec * 1000)))
        sentences = (alignment_json or {}).get("sentences") or []
        pauses = (alignment_json or {}).get("pauses") or []
        intel_sents = (script_intelligence_json or {}).get("sentences") or []

        if not sentences:
            return [
                AvatarTimelineSegment(
                    index=0,
                    start_ms=0,
                    end_ms=total_ms,
                    emotion="explaining",
                    facial_expression="natural_attentive_expression",
                    hand_gesture="open_palm_explanation",
                    head_movement="natural_micro_nod",
                    is_pause=False,
                )
            ]

        segments: list[AvatarTimelineSegment] = []
        pause_by_after_idx = {int(p["after_sentence_index"]): p for p in pauses}

        for idx, sent in enumerate(sentences):
            intel = intel_sents[idx] if idx < len(intel_sents) else {}
            raw_emo = str(intel.get("emotion", "explaining")).lower()
            stype = str(intel.get("sentence_type", "statement")).lower()

            if stype == "explanation" and raw_emo == "serious":
                emotion: EmotionType = "explaining"
            elif stype == "conclusion" and raw_emo == "enthusiastic":
                emotion = "confident"
            else:
                emotion = cls.EMOTION_MAP.get(raw_emo, "neutral")

            segments.append(
                AvatarTimelineSegment(
                    index=len(segments),
                    start_ms=int(sent["start_ms"]),
                    end_ms=int(sent["end_ms"]),
                    emotion=emotion,
                    facial_expression=str(
                        intel.get("facial_expression", "natural_attentive_expression")
                    ),
                    hand_gesture=str(intel.get("hand_gesture", "open_palm_explanation")),
                    head_movement=str(intel.get("head_movement", "natural_micro_nod")),
                    is_pause=False,
                    highlight_words=list(intel.get("highlight_words", [])),
                )
            )

            if idx in pause_by_after_idx:
                p = pause_by_after_idx[idx]
                segments.append(
                    AvatarTimelineSegment(
                        index=len(segments),
                        start_ms=int(p["start_ms"]),
                        end_ms=int(p["end_ms"]),
                        emotion="thinking",
                        facial_expression="calm_blink_and_breathe",
                        hand_gesture="resting_neutral",
                        head_movement="subtle_settle",
                        is_pause=True,
                    )
                )

        return segments
