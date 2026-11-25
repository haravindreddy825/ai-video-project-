from pathlib import Path
from typing import Any, Optional

from app.core.logging import logger
from app.core.storage import StorageManager
from app.engines.visuals.comfyui_adapter import (
    ComfyUIImageAdapter,
    ComfyUIUnavailableError,
)
from app.engines.visuals.programmatic_renderer import ProgrammaticVisualRenderer


class VisualSceneManager:
    """
    Coordinates programmatic 1080x960 rendering (Pillow + Matplotlib + SVG + FFmpeg)
    with optional ComfyUI AI illustration insets.
    """

    def __init__(self, storage: Optional[StorageManager] = None) -> None:
        self.storage = storage or StorageManager()
        self.renderer = ProgrammaticVisualRenderer()
        self.comfy = ComfyUIImageAdapter()

    def render_scene_assets(
        self,
        project_id: str,
        scene_id: str,
        scene_dict: dict[str, Any],
        use_comfyui: bool = False,
        render_video: bool = True,
        fps: int = 25,
        custom_inset_path: Optional[Path] = None,
    ) -> dict[str, Any]:
        scene_dir = self.storage.outputs_dir / project_id / "visuals" / scene_id
        scene_dir.mkdir(parents=True, exist_ok=True)

        inset_path: Path | None = custom_inset_path
        generator_used = "custom_upload" if custom_inset_path else "programmatic"

        if use_comfyui and not custom_inset_path:
            ai_png = scene_dir / "ai_illustration.png"
            try:
                inset_path = self.comfy.generate_illustration(
                    str(scene_dict.get("visual_description") or scene_dict.get("title_text")),
                    ai_png,
                )
                generator_used = "comfyui"
            except ComfyUIUnavailableError as exc:
                logger.info("ComfyUI skipped (%s); using programmatic renderer.", exc)
                inset_path = None

        png_path = scene_dir / "slide_1080x960.png"
        svg_path = (
            scene_dir / "diagram.svg"
            if scene_dict.get("visual_format") in ("diagram", "flowchart", "step_by_step")
            else None
        )
        self.renderer.render_scene_png(
            scene_dict, png_path, svg_out_path=svg_path, inset_image_path=inset_path
        )

        rel_png = str(png_path.relative_to(self.storage.root)).replace("\\", "/")
        rel_svg = (
            str(svg_path.relative_to(self.storage.root)).replace("\\", "/")
            if svg_path and svg_path.exists()
            else None
        )
        rel_mp4: str | None = None

        if render_video:
            dur_sec = max(
                0.25, (int(scene_dict["end_ms"]) - int(scene_dict["start_ms"])) / 1000.0
            )
            mp4_path = scene_dir / "scene_1080x960.mp4"
            self.renderer.render_scene_mp4(
                png_path,
                mp4_path,
                duration_sec=dur_sec,
                animation_style=str(scene_dict.get("animation_style", "slide_up")),
                fps=fps,
            )
            rel_mp4 = str(mp4_path.relative_to(self.storage.root)).replace("\\", "/")

        return {
            "generator_used": generator_used,
            "image_path": rel_png,
            "video_path": rel_mp4,
            "svg_path": rel_svg,
        }
