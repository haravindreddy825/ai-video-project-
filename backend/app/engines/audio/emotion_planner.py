import re
from typing import Literal

from app.engines.audio.schemas import (
    ScriptIntelligenceResult,
    SentenceInstruction,
)


class EmotionPlanner:
    """
    Analyzes a script into sentence-level presentation instructions
    (sentence type, emotion, facial expression, hand gesture, head movement,
    and highlight keywords) WITHOUT modifying the original script text.
    """

    STOPWORDS = {
        "a", "an", "and", "are", "as", "at", "be", "because", "but", "by",
        "can", "do", "does", "for", "from", "have", "how", "i", "if", "in",
        "into", "is", "it", "its", "just", "let", "like", "more", "most",
        "not", "now", "of", "on", "one", "or", "our", "out", "so", "some",
        "such", "than", "that", "the", "their", "them", "then", "there",
        "these", "they", "this", "to", "up", "us", "very", "was", "we",
        "what", "when", "where", "which", "who", "why", "will", "with", "you",
        "your",
    }

    @staticmethod
    def split_sentences(text: str) -> list[str]:
        cleaned = re.sub(r"\s+", " ", text.strip())
        if not cleaned:
            return []
        parts = re.split(r"(?<=[.!?])\s+", cleaned)
        return [p.strip() for p in parts if p.strip()]

    @classmethod
    def _classify_sentence(
        cls, sentence: str, idx: int, total: int
    ) -> tuple[
        Literal["question", "explanation", "example", "conclusion", "statement"],
        Literal["curious", "enthusiastic", "serious", "calm", "neutral"],
    ]:
        lower = sentence.lower()
        if sentence.endswith("?") or lower.startswith(
            ("why ", "how ", "what ", "have you", "did you", "can we", "imagine ")
        ):
            return "question", "curious"

        if any(
            k in lower
            for k in (
                "for example",
                "for instance",
                "imagine",
                "consider ",
                "let's say",
                "suppose",
                "such as",
            )
        ):
            return "example", "enthusiastic"

        if idx >= max(1, total - 2) and any(
            k in lower
            for k in (
                "in summary",
                "to summarize",
                "finally",
                "in conclusion",
                "ultimately",
                "remember",
                "takeaway",
                "subscribe",
                "that's why",
            )
        ):
            return "conclusion", "enthusiastic"

        if any(
            k in lower
            for k in (
                "because",
                "therefore",
                "means that",
                "works by",
                "this happens",
                "the reason",
                "notice that",
                "important",
                "critical",
            )
        ):
            return "explanation", "serious"

        if idx == 0:
            return "statement", "enthusiastic"

        return "statement", "calm"

    @staticmethod
    def _map_directives(
        sentence_type: str, emotion: str
    ) -> tuple[str, str, str]:
        mapping = {
            ("question", "curious"): (
                "raised_eyebrows_inquisitive_smile",
                "open_palm_question_gesture",
                "slight_head_tilt_right",
            ),
            ("example", "enthusiastic"): (
                "warm_smile_engaged_eyes",
                "illustrative_two_hand_framing",
                "gentle_nod_forward",
            ),
            ("conclusion", "enthusiastic"): (
                "confident_smile_bright_eyes",
                "decisive_summary_sweep",
                "affirmative_nod",
            ),
            ("explanation", "serious"): (
                "focused_brow_steady_gaze",
                "precision_finger_point_or_beat",
                "measured_nod",
            ),
        }
        return mapping.get(
            (sentence_type, emotion),
            ("natural_attentive_expression", "subtle_conversational_gesture", "natural_micro_nod"),
        )

    @classmethod
    def _extract_highlights(cls, sentence: str) -> list[str]:
        tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-']*", sentence)
        highlights: list[str] = []
        for idx, tok in enumerate(tokens):
            lower = tok.lower()
            if lower in cls.STOPWORDS or len(tok) < 4:
                continue
            is_metric = any(ch.isdigit() for ch in tok)
            is_proper_mid = idx > 0 and tok[0].isupper()
            is_long_concept = len(tok) >= 7
            if is_metric or is_proper_mid or is_long_concept:
                if tok not in highlights:
                    highlights.append(tok)
            if len(highlights) >= 4:
                break
        return highlights

    @classmethod
    def analyze(
        cls, script_text: str, speaking_rate_wpm: float = 150.0
    ) -> ScriptIntelligenceResult:
        raw_sentences = cls.split_sentences(script_text)
        total = len(raw_sentences)
        instructions: list[SentenceInstruction] = []

        for idx, sent in enumerate(raw_sentences):
            stype, emotion = cls._classify_sentence(sent, idx, total)
            facial, hand, head = cls._map_directives(stype, emotion)
            highlights = cls._extract_highlights(sent)
            instructions.append(
                SentenceInstruction(
                    index=idx,
                    text=sent,
                    sentence_type=stype,
                    emotion=emotion,
                    facial_expression=facial,
                    hand_gesture=hand,
                    head_movement=head,
                    highlight_words=highlights,
                )
            )

        return ScriptIntelligenceResult(
            original_script=script_text,
            total_sentences=total,
            estimated_speaking_rate_wpm=speaking_rate_wpm,
            sentences=instructions,
        )
