import re
from typing import Any

from app.engines.visuals.schemas import AnimationStyle, TransitionStyle, VisualFormat


class ScriptToVisualPlanner:
    """
    Converts Phase 2 alignment_json + script_intelligence_json into a
    synchronized sequence of 1080x960 educational visual scenes.
    Supports multiple visual changes within a single long sentence.
    """

    @staticmethod
    def _classify_format(text: str, sentence_type: str) -> VisualFormat:
        lower = text.lower()
        if any(k in lower for k in ("versus", " vs ", "compared to", "difference between", "unlike")):
            return "comparison"
        if any(k in lower for k in ("step", "first,", "second,", "third,", "stages", "three core")):
            return "step_by_step"
        if any(k in lower for k in ("percent", "rate", "measure", "vector", "numbers", "thousand", "samples per second")):
            return "chart"
        if any(k in lower for k in ("flow", "pipeline", "turns ", "converts", "into ", "next,")):
            return "flowchart"
        if any(k in lower for k in ("network", "layer", "architecture", "model", "system", "structure")):
            return "diagram"
        if sentence_type == "example":
            return "example"
        if sentence_type == "question":
            return "icon_callout"
        if sentence_type == "conclusion":
            return "infographic"
        return "text_animation"

    @staticmethod
    def _build_diagram_spec(
        fmt: VisualFormat, title: str, keywords: list[str], text: str
    ) -> dict[str, Any]:
        kw = keywords[:4] if keywords else ["Input", "Process", "Output"]
        if fmt == "chart":
            labels = kw[:4] if len(kw) >= 2 else ["Stage 1", "Stage 2", "Stage 3"]
            values = [42 + (i * 19) % 55 for i in range(len(labels))]
            return {"chart_type": "bar", "labels": labels, "values": values, "unit": "Score"}
        if fmt == "comparison":
            left = kw[0] if len(kw) > 0 else "Approach A"
            right = kw[1] if len(kw) > 1 else "Approach B"
            return {
                "left_title": left.title(),
                "right_title": right.title(),
                "left_points": ["Direct representation", "Baseline speed"],
                "right_points": ["Learned structure", "Higher accuracy"],
            }
        if fmt in ("flowchart", "diagram", "step_by_step"):
            nodes = [k.title() for k in kw[:3]]
            if len(nodes) < 3:
                nodes = ["Input", title[:18] or "Processing", "Output"]
            return {"nodes": nodes}
        return {"highlight_badge": kw[0].upper() if kw else "KEY IDEA"}

    @staticmethod
    def _extract_title(text: str, keywords: list[str]) -> str:
        if keywords:
            return " ".join(k.title() for k in keywords[:3])
        words = [w.strip(".,!?;:") for w in text.split()[:5]]
        return " ".join(words).title() or "Key Concept"

    @staticmethod
    def _split_long_sentence_if_needed(sent: dict[str, Any]) -> list[dict[str, Any]]:
        words = sent.get("words") or []
        text = str(sent.get("text", "")).strip()
        if len(words) < 20:
            return [{"text": text, "start_ms": int(sent["start_ms"]), "end_ms": int(sent["end_ms"])}]

        mid = len(words) // 2
        # Prefer splitting near a comma if one exists in the middle third
        for idx in range(len(words) // 3, (2 * len(words)) // 3):
            if words[idx]["word"].endswith((",", ";")):
                mid = idx + 1
                break

        first_words = words[:mid]
        second_words = words[mid:]
        if not first_words or not second_words:
            return [{"text": text, "start_ms": int(sent["start_ms"]), "end_ms": int(sent["end_ms"])}]

        return [
            {
                "text": " ".join(w["word"] for w in first_words).strip(),
                "start_ms": int(first_words[0]["start_ms"]),
                "end_ms": int(first_words[-1]["end_ms"]),
            },
            {
                "text": " ".join(w["word"] for w in second_words).strip(),
                "start_ms": int(second_words[0]["start_ms"]),
                "end_ms": int(second_words[-1]["end_ms"]),
            },
        ]

    @classmethod
    def plan_scenes(
        cls,
        alignment_json: dict[str, Any] | None,
        script_intelligence_json: dict[str, Any] | None,
        duration_sec: float,
    ) -> list[dict[str, Any]]:
        total_ms = max(1000, int(round(duration_sec * 1000)))
        sentences = (alignment_json or {}).get("sentences") or []
        intel_sents = (script_intelligence_json or {}).get("sentences") or []

        if not sentences:
            return [
                {
                    "order_index": 0,
                    "start_ms": 0,
                    "end_ms": total_ms,
                    "sentence_text": "Educational Presentation",
                    "main_concept": "Overview",
                    "keywords": ["Overview"],
                    "visual_format": "infographic",
                    "visual_description": "Clean educational overview card.",
                    "title_text": "Overview",
                    "body_bullets": ["Synchronized educational explanation"],
                    "diagram_spec": {"highlight_badge": "OVERVIEW"},
                    "animation_style": "fade_in",
                    "transition_style": "crossfade",
                }
            ]

        planned: list[dict[str, Any]] = []
        for s_idx, sent in enumerate(sentences):
            intel = intel_sents[s_idx] if s_idx < len(intel_sents) else {}
            stype = str(intel.get("sentence_type", "statement"))
            keywords = list(intel.get("highlight_words") or [])
            sub_beats = cls._split_long_sentence_if_needed(sent)

            for b_idx, beat in enumerate(sub_beats):
                b_text = beat["text"]
                fmt = cls._classify_format(b_text, stype)
                title = cls._extract_title(b_text, keywords[b_idx : b_idx + 3] or keywords)
                anim: AnimationStyle = (
                    "step_reveal"
                    if fmt in ("step_by_step", "flowchart", "diagram")
                    else "kinetic_highlight"
                    if fmt == "text_animation"
                    else "slide_up"
                )
                trans: TransitionStyle = "slide_left" if b_idx > 0 else "crossfade"

                # Clean concise bullets (max 2 short lines) without truncation artifacts
                clean_sentence = re.sub(r"\s+", " ", b_text).strip()
                planned.append(
                    {
                        "order_index": len(planned),
                        "start_ms": int(beat["start_ms"]),
                        "end_ms": int(beat["end_ms"]),
                        "sentence_text": clean_sentence,
                        "main_concept": title,
                        "keywords": keywords,
                        "visual_format": fmt,
                        "visual_description": f"{fmt.replace('_', ' ').title()} illustrating: {title}",
                        "title_text": title,
                        "body_bullets": [clean_sentence],
                        "diagram_spec": cls._build_diagram_spec(fmt, title, keywords, clean_sentence),
                        "animation_style": anim,
                        "transition_style": trans,
                    }
                )

        # Make timeline contiguous from 0 to total_ms so top half never blanks out
        planned[0]["start_ms"] = 0
        for i in range(len(planned) - 1):
            planned[i]["end_ms"] = max(planned[i]["start_ms"] + 200, planned[i + 1]["start_ms"])
        planned[-1]["end_ms"] = max(planned[-1]["start_ms"] + 200, total_ms)
        return planned
