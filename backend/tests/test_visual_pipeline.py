import io
from pathlib import Path
import httpx
from PIL import Image
import psutil
import pytest

from app.core.storage import StorageManager
from app.engines.visuals.comfyui_adapter import ComfyUIImageAdapter
from app.engines.visuals.programmatic_renderer import ProgrammaticVisualRenderer
from app.main import app


THIRTY_SEC_SCRIPT = (
    "Have you ever wondered how computers understand human language? "
    "Modern language models break sentences into small pieces called tokens. "
    "For example, a single word might become one or two tokens depending on how common it is. "
    "Next, each token is converted into a list of numbers known as an embedding vector. "
    "Because similar words have similar vectors, the model can measure meaning mathematically. "
    "In summary, embeddings turn text into geometry so machines can reason."
)

TWO_MINUTE_SCRIPT = (
    "Welcome back to our deep dive into how artificial intelligence learns to see, listen, and speak. "
    "Have you ever wondered how a computer turns raw numbers into a clear, natural human voice? "
    "In this two-minute lesson, we will walk through the three core stages of modern neural speech synthesis. "
    "First, let's look at text normalization and phonetic encoding. "
    "When you write a sentence containing numbers, abbreviations, or punctuation, the model cannot read letters directly. "
    "Instead, a phonemizer converts words into precise pronunciation symbols that capture stress, rhythm, and intonation. "
    "For example, the word read sounds completely different depending on whether it is in the present or past tense. "
    "Second, an acoustic neural network predicts how each phoneme should sound over time. "
    "Because neural networks learn patterns from thousands of hours of real human recordings, they capture natural breathing, pitch contours, and emotional emphasis. "
    "Notice that when you ask a question, your pitch naturally rises at the end of the sentence. "
    "When you explain a serious technical concept, your pacing becomes steadier and more deliberate. "
    "Third, a neural vocoder or flow-matching decoder converts those acoustic features into an actual audio waveform at twenty-four thousand samples per second. "
    "Consider what happens when we combine this with forced speech alignment. "
    "By running an automatic speech recognition model over the generated narration, we obtain exact millisecond timestamps for every single word and pause. "
    "This means our visual slides, highlighted keywords, and animated presenter stay perfectly synchronized from the very first frame to the final second. "
    "For instance, whenever you introduce a new diagram, it appears on the exact word you say it. "
    "In summary, voice-first timeline generation guarantees smooth pacing, accurate lip synchronization, and crisp educational storytelling. "
    "Remember these three steps: phonetic encoding, acoustic modeling, and millisecond alignment."
)


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _make_custom_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), color=(37, 99, 235)).save(buf, format="PNG")
    return buf.getvalue()


def test_programmatic_formats_and_comfyui_honest_check(tmp_path: Path):
    renderer = ProgrammaticVisualRenderer()
    formats = [
        ("chart", {"chart_type": "bar", "labels": ["Tokens", "Vectors", "Layers"], "values": [40, 75, 92]}),
        ("comparison", {"left_title": "CPU", "right_title": "GPU", "left_points": ["Sequential"], "right_points": ["Parallel"]}),
        ("flowchart", {"nodes": ["Text", "Phonemes", "Audio"]}),
        ("text_animation", {"highlight_badge": "KEY"}),
    ]
    for idx, (fmt, spec) in enumerate(formats):
        out_png = tmp_path / f"{fmt}_{idx}.png"
        svg_path = tmp_path / f"{fmt}_{idx}.svg" if fmt == "flowchart" else None
        renderer.render_scene_png(
            {
                "visual_format": fmt,
                "title_text": f"Test {fmt.title()}",
                "sentence_text": "Clean educational visual test.",
                "body_bullets": ["Readable typography and spacing."],
                "keywords": ["AI", "Education"],
                "diagram_spec": spec,
            },
            out_png,
            svg_out_path=svg_path,
        )
        assert out_png.exists()
        with Image.open(out_png) as im:
            assert im.size == (1080, 960)
        if svg_path:
            assert svg_path.exists()

    # Honest ComfyUI check (does not fake generation if ComfyUI server is offline)
    comfy = ComfyUIImageAdapter()
    assert isinstance(comfy.is_available(), bool)


async def test_30s_and_2min_visual_generation_and_editing(client: httpx.AsyncClient):
    proj = (await client.post("/api/v1/projects", json={"title": "Visuals Phase 4"})).json()
    pid = proj["id"]
    storage = StorageManager()

    # 1. Generate 30-second Phase 2 audio & aligned visuals (with MP4 clips + stitch)
    audio_30 = (
        await client.post(
            f"/api/v1/projects/{pid}/audio/generate?sync=true",
            json={"script_text": THIRTY_SEC_SCRIPT, "voice_id": "af_heart", "auto_align": True},
        )
    ).json()
    assert audio_30["status"] == "completed"

    vis_30_res = await client.post(
        f"/api/v1/projects/{pid}/visuals/generate",
        json={"audio_id": audio_30["id"], "use_comfyui": False, "render_video": True, "fps": 25},
    )
    assert vis_30_res.status_code == 201
    scenes_30 = vis_30_res.json()
    assert len(scenes_30) >= 5
    assert scenes_30[0]["start_ms"] == 0
    assert scenes_30[-1]["end_ms"] >= int(audio_30["duration_sec"] * 1000) - 200

    # Stitch all 30s scene MP4s into one continuous 1080x960 visual stream
    scene_mp4s = [storage.root / s["video_path"] for s in scenes_30]
    assert all(p.exists() for p in scene_mp4s)
    stitched_30 = storage.outputs_dir / pid / "visuals" / "stitched_30s.mp4"
    ProgrammaticVisualRenderer().stitch_scenes_mp4(scene_mp4s, stitched_30)
    assert stitched_30.exists() and stitched_30.stat().st_size > 10000

    # 2. Test Visual Editing APIs on scene 0
    sid = scenes_30[0]["id"]
    assert (await client.get(f"/api/v1/visuals/scenes/{sid}/preview?kind=image")).status_code == 200
    assert (await client.get(f"/api/v1/visuals/scenes/{sid}/preview?kind=video")).status_code == 200

    edited = await client.patch(
        f"/api/v1/visuals/scenes/{sid}",
        json={"title_text": "Edited Concept Title", "end_ms": scenes_30[0]["end_ms"] + 300},
    )
    assert edited.status_code == 200
    assert edited.json()["title_text"] == "Edited Concept Title"

    regen = await client.post(f"/api/v1/visuals/scenes/{sid}/regenerate?use_comfyui=false")
    assert regen.status_code == 200

    replaced = await client.post(
        f"/api/v1/visuals/scenes/{sid}/replace-image",
        files={"image": ("custom.png", _make_custom_png(), "image/png")},
    )
    assert replaced.status_code == 200
    assert replaced.json()["generator_used"] == "custom_upload"

    approved = await client.post(f"/api/v1/visuals/scenes/{sid}/approve")
    assert approved.status_code == 200
    assert approved.json()["approved"] is True

    # Reorder scenes
    reversed_ids = [s["id"] for s in reversed(scenes_30)]
    reordered = await client.post(
        f"/api/v1/projects/{pid}/visuals/scenes/reorder",
        json={"scene_ids": reversed_ids},
    )
    assert reordered.status_code == 200
    assert reordered.json()[0]["id"] == reversed_ids[0]

    # Create custom scene & check persisted assets
    created = await client.post(
        f"/api/v1/projects/{pid}/visuals/scenes",
        json={
            "audio_id": audio_30["id"],
            "order_index": 99,
            "start_ms": 0,
            "end_ms": 2000,
            "sentence_text": "Custom callout scene.",
            "main_concept": "Custom",
            "visual_format": "icon_callout",
        },
    )
    assert created.status_code == 201
    assets = await client.get(f"/api/v1/projects/{pid}/visuals/assets")
    assert assets.status_code == 200
    assert len(assets.json()) >= len(scenes_30)

    # 3. Full 2-minute educational script visual planning & PNG rendering + RAM check
    proj2 = (await client.post("/api/v1/projects", json={"title": "Visuals 2-Min"})).json()
    pid2 = proj2["id"]
    audio_120 = (
        await client.post(
            f"/api/v1/projects/{pid2}/audio/generate?sync=true",
            json={"script_text": TWO_MINUTE_SCRIPT, "voice_id": "af_bella", "auto_align": True},
        )
    ).json()
    assert audio_120["status"] == "completed"

    vis_120_res = await client.post(
        f"/api/v1/projects/{pid2}/visuals/generate",
        json={"audio_id": audio_120["id"], "use_comfyui": False, "render_video": False},
    )
    assert vis_120_res.status_code == 201
    scenes_120 = vis_120_res.json()
    assert len(scenes_120) >= 15
    assert all((storage.root / s["image_path"]).exists() for s in scenes_120)

    # Verify memory stays well within 16 GB system RAM
    ram_pct = psutil.virtual_memory().percent
    assert ram_pct < 95.0
