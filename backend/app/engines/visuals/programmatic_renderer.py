import io
from pathlib import Path
import subprocess
import textwrap
from typing import Any, Optional

import cv2
import imageio_ffmpeg
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont


class ProgrammaticVisualRenderer:
    """
    Renders crisp, clean light-theme 1080x960 educational visuals (slides,
    diagrams, flowcharts, Matplotlib charts, SVG companions, and comparisons)
    with zero VRAM usage and strict non-overlapping layout.
    """

    WIDTH = 1080
    HEIGHT = 960

    BG_COLOR = (248, 250, 252)       # #F8FAFC Slate-50
    CARD_COLOR = (255, 255, 255)     # #FFFFFF
    BORDER_COLOR = (226, 232, 240)   # #E2E8F0 Slate-200
    PRIMARY = (37, 99, 235)          # #2563EB Blue-600
    PRIMARY_SOFT = (239, 246, 255)   # #EFF6FF Blue-50
    ACCENT = (16, 185, 129)          # #10B981 Emerald-500
    TEXT_DARK = (15, 23, 42)         # #0F172A Slate-900
    TEXT_MUTED = (71, 85, 105)       # #475569 Slate-600

    def __init__(self) -> None:
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    @staticmethod
    def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = (
            ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"]
            if bold
            else ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]
        )
        for path in candidates:
            if Path(path).exists():
                try:
                    return ImageFont.truetype(path, size=size)
                except Exception:
                    pass
        return ImageFont.load_default()

    @classmethod
    def _draw_chart_image(cls, spec: dict[str, Any]) -> Image.Image:
        labels = list(spec.get("labels") or ["A", "B", "C"])
        values = list(spec.get("values") or [45, 72, 88])
        unit = str(spec.get("unit", "Value"))

        fig, ax = plt.subplots(figsize=(8.8, 3.6), dpi=100)
        fig.patch.set_facecolor("#FFFFFF")
        ax.set_facecolor("#F8FAFC")
        colors = ["#2563EB", "#3B82F6", "#10B981", "#6366F1"][: len(labels)]
        bars = ax.bar(labels, values, color=colors, width=0.52, edgecolor="none", zorder=3)
        ax.grid(axis="y", linestyle="--", alpha=0.4, color="#CBD5E1", zorder=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_ylabel(unit, fontsize=12, color="#334155", fontweight="bold")
        ax.tick_params(colors="#1E293B", labelsize=11)
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                bar.get_height() + 1.5,
                f"{val}",
                ha="center",
                va="bottom",
                fontsize=11,
                fontweight="bold",
                color="#0F172A",
            )
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor="#FFFFFF")
        plt.close(fig)
        buf.seek(0)
        return Image.open(buf).convert("RGB")

    @classmethod
    def generate_svg_diagram(cls, nodes: list[str], out_svg: Path) -> Path:
        out_svg.parent.mkdir(parents=True, exist_ok=True)
        boxes = []
        y = 40
        for i, label in enumerate(nodes[:4]):
            boxes.append(
                f'<rect x="140" y="{y}" width="600" height="72" rx="14" fill="#EFF6FF" stroke="#2563EB" stroke-width="3"/>'
                f'<text x="440" y="{y + 44}" font-family="Segoe UI, Arial" font-size="24" font-weight="bold" fill="#0F172A" text-anchor="middle">{label}</text>'
            )
            if i < len(nodes[:4]) - 1:
                boxes.append(
                    f'<line x1="440" y1="{y + 72}" x2="440" y2="{y + 106}" stroke="#2563EB" stroke-width="3"/>'
                )
            y += 108
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="880" height="{y + 20}" viewBox="0 0 880 {y + 20}">'
            + "".join(boxes)
            + "</svg>"
        )
        out_svg.write_text(svg, encoding="utf-8")
        return out_svg

    def render_scene_png(
        self,
        scene: dict[str, Any],
        output_png: Path,
        svg_out_path: Optional[Path] = None,
        inset_image_path: Optional[Path] = None,
    ) -> Path:
        output_png.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), self.BG_COLOR)
        draw = ImageDraw.Draw(img)

        f_badge = self._load_font(22, bold=True)
        f_title = self._load_font(44, bold=True)
        f_body = self._load_font(28, bold=False)
        f_card = self._load_font(26, bold=True)
        f_small = self._load_font(22, bold=False)

        # Top accent stripe
        draw.rectangle([0, 0, self.WIDTH, 12], fill=self.PRIMARY)

        # Format & Concept Badge
        fmt_label = str(scene.get("visual_format", "concept")).replace("_", " ").upper()
        badge_w = max(210, len(fmt_label) * 16 + 44)
        draw.rounded_rectangle([64, 44, 64 + badge_w, 92], radius=22, fill=self.PRIMARY_SOFT, outline=self.PRIMARY, width=2)
        draw.text((86, 55), fmt_label, font=f_badge, fill=self.PRIMARY)

        # Title
        title = str(scene.get("title_text") or scene.get("main_concept") or "Key Concept")
        wrapped_title = textwrap.wrap(title, width=34)[:2]
        y_cursor = 118
        for line in wrapped_title:
            draw.text((64, y_cursor), line, font=f_title, fill=self.TEXT_DARK)
            y_cursor += 54

        # Main visual card container
        card_top = y_cursor + 20
        card_bottom = 700
        draw.rounded_rectangle(
            [64, card_top, self.WIDTH - 64, card_bottom],
            radius=24,
            fill=self.CARD_COLOR,
            outline=self.BORDER_COLOR,
            width=3,
        )

        fmt = str(scene.get("visual_format", "text_animation"))
        spec = scene.get("diagram_spec") or {}

        if inset_image_path and inset_image_path.exists():
            with Image.open(inset_image_path) as inset:
                inset_rgb = inset.convert("RGB")
                inset_rgb.thumbnail((900, card_bottom - card_top - 40))
                ix = (self.WIDTH - inset_rgb.width) // 2
                iy = card_top + ((card_bottom - card_top - inset_rgb.height) // 2)
                img.paste(inset_rgb, (ix, iy))
        elif fmt == "chart":
            chart_img = self._draw_chart_image(spec)
            chart_img.thumbnail((900, card_bottom - card_top - 40))
            cx = (self.WIDTH - chart_img.width) // 2
            cy = card_top + ((card_bottom - card_top - chart_img.height) // 2)
            img.paste(chart_img, (cx, cy))
        elif fmt == "comparison":
            mid_x = self.WIDTH // 2
            draw.rounded_rectangle([92, card_top + 28, mid_x - 16, card_bottom - 28], radius=16, fill=self.PRIMARY_SOFT)
            draw.rounded_rectangle([mid_x + 16, card_top + 28, self.WIDTH - 92, card_bottom - 28], radius=16, fill=(236, 253, 245))
            draw.text((120, card_top + 52), str(spec.get("left_title", "Option A")), font=f_card, fill=self.PRIMARY)
            draw.text((mid_x + 44, card_top + 52), str(spec.get("right_title", "Option B")), font=f_card, fill=self.ACCENT)
            for idx, pt in enumerate(spec.get("left_points", [])[:3]):
                draw.text((120, card_top + 115 + idx * 46), f"• {pt}", font=f_small, fill=self.TEXT_DARK)
            for idx, pt in enumerate(spec.get("right_points", [])[:3]):
                draw.text((mid_x + 44, card_top + 115 + idx * 46), f"• {pt}", font=f_small, fill=self.TEXT_DARK)
        elif fmt in ("flowchart", "diagram", "step_by_step"):
            nodes = list(spec.get("nodes") or ["Step 1", "Step 2", "Step 3"])[:3]
            if svg_out_path:
                self.generate_svg_diagram(nodes, svg_out_path)
            ny = card_top + 36
            for i, node in enumerate(nodes):
                draw.rounded_rectangle([140, ny, self.WIDTH - 140, ny + 82], radius=16, fill=self.PRIMARY_SOFT, outline=self.PRIMARY, width=2)
                draw.text((176, ny + 25), f"{i + 1}. {node}", font=f_card, fill=self.TEXT_DARK)
                if i < len(nodes) - 1:
                    draw.line([(self.WIDTH // 2, ny + 82), (self.WIDTH // 2, ny + 112)], fill=self.PRIMARY, width=4)
                ny += 116
        else:
            # Clean narration highlight card
            bullets = list(scene.get("body_bullets") or [scene.get("sentence_text", "")])
            by = card_top + 48
            for b in bullets[:2]:
                for line in textwrap.wrap(str(b), width=52)[:5]:
                    draw.text((104, by), line, font=f_body, fill=self.TEXT_DARK)
                    by += 42
                by += 16

        # Bottom keyword pills (guaranteed below card_bottom, never overlapping)
        keywords = list(scene.get("keywords") or [])[:4]
        kx = 64
        ky = 742
        for kw in keywords:
            label = f"# {kw}"
            pw = max(130, len(label) * 14 + 34)
            if kx + pw > self.WIDTH - 64:
                break
            draw.rounded_rectangle([kx, ky, kx + pw, ky + 48], radius=24, fill=(241, 245, 249), outline=self.BORDER_COLOR, width=2)
            draw.text((kx + 18, ky + 10), label, font=f_small, fill=self.TEXT_MUTED)
            kx += pw + 14

        # Subtle bottom divider separating Top 50% (Visuals) from Bottom 50% (Avatar)
        draw.rectangle([0, self.HEIGHT - 6, self.WIDTH, self.HEIGHT], fill=self.PRIMARY)
        img.save(str(output_png), format="PNG")
        return output_png

    def render_scene_mp4(
        self,
        scene_png: Path,
        output_mp4: Path,
        duration_sec: float,
        animation_style: str = "slide_up",
        fps: int = 25,
    ) -> Path:
        base = cv2.imread(str(scene_png), cv2.IMREAD_COLOR)
        if base is None:
            raise FileNotFoundError(f"Scene PNG missing: {scene_png}")

        total_frames = max(2, int(round(max(0.2, duration_sec) * fps)))
        output_mp4.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.ffmpeg_exe,
            "-y",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{self.WIDTH}x{self.HEIGHT}",
            "-r",
            str(fps),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            str(output_mp4),
        ]
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        assert proc.stdin is not None

        bg_white = np.full_like(base, 248)
        intro_frames = min(total_frames, max(4, int(fps * 0.45)))
        for f_idx in range(total_frames):
            if f_idx < intro_frames:
                alpha = (f_idx + 1) / float(intro_frames)
                if animation_style == "slide_up":
                    shift_y = int(round((1.0 - alpha) * 40))
                    mat = np.float32([[1, 0, 0], [0, 1, shift_y]])
                    shifted = cv2.warpAffine(base, mat, (self.WIDTH, self.HEIGHT), borderValue=(248, 250, 252))
                    frame = cv2.addWeighted(shifted, alpha, bg_white, 1.0 - alpha, 0)
                else:
                    frame = cv2.addWeighted(base, alpha, bg_white, 1.0 - alpha, 0)
            else:
                frame = base
            proc.stdin.write(frame.tobytes())

        proc.stdin.close()
        stderr = proc.stderr.read().decode("utf-8", errors="ignore") if proc.stderr else ""
        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(f"FFmpeg visual scene encode failed ({ret}): {stderr[-400:]}")
        return output_mp4

    def stitch_scenes_mp4(
        self, scene_mp4s: list[Path], output_mp4: Path
    ) -> Path:
        if not scene_mp4s:
            raise ValueError("No scene MP4 files to stitch.")
        output_mp4.parent.mkdir(parents=True, exist_ok=True)
        concat_file = output_mp4.parent / f"_concat_{output_mp4.stem}.txt"
        concat_file.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in scene_mp4s),
            encoding="utf-8",
        )
        cmd = [
            self.ffmpeg_exe,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c:v",
            "copy",
            "-movflags",
            "+faststart",
            str(output_mp4),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        concat_file.unlink(missing_ok=True)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg visual stitch failed: {res.stderr[-400:]}")
        return output_mp4
