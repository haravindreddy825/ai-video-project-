from pathlib import Path
from typing import Any


class SubtitleRenderer:
    """
    Generates styled ASS (Advanced SubStation Alpha) captions from Phase 2
    word-level timestamps, positioned cleanly in the 1080x1920 safe margin.
    """

    ASS_HEADER = """[Script Info]
Title: OpenSource AI Video Studio Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,42,&H00FFFFFF,&H000000FF,&H000F172A,&H960F172A,-1,0,0,0,100,100,0,0,3,2,0,2,60,60,72,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    @staticmethod
    def _format_ass_time(ms: int) -> str:
        ms = max(0, int(ms))
        total_cs = ms // 10
        cs = total_cs % 100
        total_sec = total_cs // 100
        sec = total_sec % 60
        total_min = total_sec // 60
        minute = total_min % 60
        hour = total_min // 60
        return f"{hour}:{minute:02d}:{sec:02d}.{cs:02d}"

    @classmethod
    def generate_ass(
        cls, alignment_json: dict[str, Any] | None, output_ass: Path, words_per_cue: int = 6
    ) -> Path:
        output_ass.parent.mkdir(parents=True, exist_ok=True)
        words = (alignment_json or {}).get("words") or []
        lines: list[str] = [cls.ASS_HEADER]

        for i in range(0, len(words), words_per_cue):
            chunk = words[i : i + words_per_cue]
            if not chunk:
                continue
            start_str = cls._format_ass_time(int(chunk[0]["start_ms"]))
            end_ms = max(int(chunk[0]["start_ms"]) + 200, int(chunk[-1]["end_ms"]))
            end_str = cls._format_ass_time(end_ms)
            text = " ".join(str(w["word"]).strip() for w in chunk).replace("\n", " ")
            lines.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}\n")

        output_ass.write_text("".join(lines), encoding="utf-8")
        return output_ass
