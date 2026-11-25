import math
import re
from typing import Any


class FlowStoryboardPlanner:
    """
    Breaks a natural-language story prompt into N continuous 5s-8s scenes
    totaling 30s, 60s, 90s, or 120s, injecting character appearance prompts
    for visual consistency and cinematic camera motion per scene.
    """

    CAMERA_MOTIONS = [
        "slow_dolly_in",
        "smooth_tracking_shot",
        "gentle_pan_right",
        "aerial_establishing_push",
        "close_up_shallow_depth",
        "steady_wide_shot",
    ]

    ARC_PHASES = [
        ("Opening Hook", "Establish the world, atmosphere, and main subject."),
        ("Rising Action", "Show the subject moving or interacting in the environment."),
        ("Discovery / Turning Point", "Reveal a striking detail, tension, or transformation."),
        ("Climax / Peak Moment", "Capture the most dynamic, dramatic, or inspiring beat."),
        ("Resolution", "Bring the sequence to a cohesive, memorable visual close."),
    ]

    @classmethod
    def generate_storyboard(
        cls,
        prompt: str,
        target_duration_sec: int = 120,
        clip_duration_sec: int = 8,
        visual_style: str = "cinematic",
        character_appearances: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        clip_len = max(4, min(8, int(clip_duration_sec)))
        num_scenes = max(1, math.ceil(target_duration_sec / clip_len))

        # Split user prompt into natural beats if user supplied multi-sentence story
        sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+", prompt.strip())
            if s.strip()
        ]
        char_clause = (
            f" Featuring consistent characters: {'; '.join(character_appearances)}."
            if character_appearances
            else ""
        )

        scenes: list[dict[str, Any]] = []
        remaining = int(target_duration_sec)
        for idx in range(num_scenes):
            dur = min(clip_len, remaining) if remaining > 0 else clip_len
            dur = max(4, dur)
            remaining -= dur

            phase_idx = min(
                len(cls.ARC_PHASES) - 1,
                int((idx / max(1, num_scenes - 1)) * (len(cls.ARC_PHASES) - 1)),
            )
            phase_name, phase_dir = cls.ARC_PHASES[phase_idx]
            cam = cls.CAMERA_MOTIONS[idx % len(cls.CAMERA_MOTIONS)]

            beat_source = sentences[idx % len(sentences)] if sentences else prompt.strip()
            continuity_note = (
                "Seamless visual continuation from the previous shot."
                if idx > 0
                else "Opening establishing shot."
            )

            scene_prompt = (
                f"[{visual_style} style, {cam.replace('_', ' ')}] "
                f"Scene {idx + 1}/{num_scenes} ({phase_name}): {beat_source}. "
                f"{phase_dir} {continuity_note}{char_clause}"
            )
            narration_text = (
                beat_source
                if idx < len(sentences)
                else f"{beat_source} — continuing the story in scene {idx + 1}."
            )

            scenes.append(
                {
                    "order_index": idx,
                    "duration_sec": dur,
                    "scene_prompt": scene_prompt,
                    "narration_text": narration_text,
                    "camera_motion": cam,
                }
            )

        return scenes
