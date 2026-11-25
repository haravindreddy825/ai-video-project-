import io
from pathlib import Path
import subprocess

import httpx
import imageio_ffmpeg
from PIL import Image
import pytest

from app.engines.video_gen.timeline_assembler import FlowTimelineAssembler
from app.main import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (256, 256), color=(30, 60, 120)).save(buf, format="PNG")
    return buf.getvalue()


async def test_flow_providers_characters_storyboard_and_honest_guard(client: httpx.AsyncClient):
    # 1. Providers metadata
    provs = (await client.get("/api/v1/flow/providers")).json()
    assert len(provs) >= 2
    ids = {p["id"] for p in provs}
    assert {"veo_3_1", "comfyui_wan2_1"}.issubset(ids)

    # 2. Reusable Flow character
    char_res = await client.post(
        "/api/v1/flow/characters",
        data={
            "name": "Captain Aria",
            "description": "Astronaut explorer",
            "appearance_prompt": "woman in silver-blue flight suit with dark curly hair",
        },
        files={"image": ("aria.png", _png_bytes(), "image/png")},
    )
    assert char_res.status_code == 201
    cid = char_res.json()["id"]
    assert (await client.get(f"/api/v1/flow/characters/{cid}/image")).status_code == 200

    # 3. 120-second storyboard creation
    proj_res = await client.post(
        "/api/v1/flow/projects",
        json={
            "title": "Europa Ice Library",
            "prompt": "An astronaut discovers a glowing library beneath Europa's ice. Holographic star maps awaken.",
            "aspect_ratio": "16:9",
            "target_duration_sec": 120,
            "visual_style": "cinematic",
            "quality": "lite",
            "provider": "veo_3_1",
            "voice_id": "af_heart",
            "character_ids": [cid],
        },
    )
    assert proj_res.status_code == 201
    proj = proj_res.json()
    scenes = proj["scenes"]
    assert len(scenes) == 15  # 15 x 8s = 120s
    assert sum(s["duration_sec"] for s in scenes) == 120
    assert "Captain Aria" in scenes[0]["scene_prompt"]

    # 4. Edit prompt, attach I2V first frame, create variations
    sid = scenes[0]["id"]
    upd = await client.patch(f"/api/v1/flow/scenes/{sid}", json={"scene_prompt": "Updated cinematic shot"})
    assert upd.status_code == 200
    assert upd.json()["scene_prompt"] == "Updated cinematic shot"

    frame_up = await client.post(
        f"/api/v1/flow/scenes/{sid}/upload-frame?kind=first",
        files={"image": ("first.png", _png_bytes(), "image/png")},
    )
    assert frame_up.status_code == 200
    assert frame_up.json()["first_frame_path"] is not None

    vars_res = await client.post(f"/api/v1/flow/scenes/{sid}/variations?count=2")
    assert vars_res.status_code == 200
    assert len(vars_res.json()) == 2

    # 5. Honest provider guard (never fakes video when GEMINI_API_KEY is unset)
    gen_res = await client.post(f"/api/v1/flow/scenes/{sid}/generate")
    assert gen_res.status_code in (200, 424)

    # Cleanup test character
    assert (await client.delete(f"/api/v1/flow/characters/{cid}")).status_code == 204


def test_flow_timeline_assembler_with_clips(tmp_path: Path):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    clip1 = tmp_path / "c1.mp4"
    clip2 = tmp_path / "c2.mp4"
    for c in (clip1, clip2):
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc=duration=3:size=640x360:rate=25",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(c),
            ],
            check=True,
            capture_output=True,
        )

    out_mp4 = tmp_path / "assembled.mp4"
    stats = FlowTimelineAssembler().assemble(
        project_id="pytest_flow",
        clip_paths=[clip1, clip2],
        narration_script="Testing multi-clip timeline assembly with Kokoro narration.",
        aspect_ratio="16:9",
        voice_id="af_heart",
        output_mp4=out_mp4,
        include_subtitles=True,
    )
    assert out_mp4.exists() and out_mp4.stat().st_size > 20000
    assert stats["width"] == 1920
    assert stats["height"] == 1080
    assert stats["clips_count"] == 2
