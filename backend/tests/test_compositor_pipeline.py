import io
import httpx
from PIL import Image, ImageDraw
import psutil
import pytest

from app.core.storage import StorageManager
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


def _make_portrait_png() -> bytes:
    img = Image.new("RGB", (720, 960), color=(32, 42, 62))
    draw = ImageDraw.Draw(img)
    draw.ellipse([160, 560, 560, 1020], fill=(45, 95, 160))
    draw.rectangle([320, 470, 400, 600], fill=(228, 185, 155))
    draw.ellipse([235, 200, 485, 500], fill=(235, 192, 162))
    draw.pieslice([225, 175, 495, 360], start=180, end=360, fill=(45, 35, 30))
    draw.ellipse([295, 315, 330, 340], fill=(255, 255, 255))
    draw.ellipse([390, 315, 425, 340], fill=(255, 255, 255))
    draw.ellipse([307, 321, 320, 334], fill=(35, 30, 30))
    draw.ellipse([402, 321, 415, 334], fill=(35, 30, 30))
    draw.arc([325, 405, 395, 440], start=10, end=170, fill=(165, 65, 70), width=5)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _run_full_e2e(
    client: httpx.AsyncClient, title: str, script_text: str, voice_id: str
) -> dict:
    proj = (await client.post("/api/v1/projects", json={"title": title})).json()
    pid = proj["id"]

    char = (
        await client.post(
            f"/api/v1/projects/{pid}/characters",
            data={"name": "Instructor"},
            files={"image": ("char.png", _make_portrait_png(), "image/png")},
        )
    ).json()
    await client.post(f"/api/v1/characters/{char['id']}/approve")

    audio = (
        await client.post(
            f"/api/v1/projects/{pid}/audio/generate?sync=true",
            json={"script_text": script_text, "voice_id": voice_id, "auto_align": True},
        )
    ).json()
    assert audio["status"] == "completed"

    visuals = (
        await client.post(
            f"/api/v1/projects/{pid}/visuals/generate",
            json={"audio_id": audio["id"], "use_comfyui": False, "render_video": False},
        )
    ).json()
    assert len(visuals) >= 5

    avatar = (
        await client.post(
            f"/api/v1/projects/{pid}/avatar/generate?sync=true",
            json={
                "character_id": char["id"],
                "audio_id": audio["id"],
                "adapter": "local_expressive",
                "fps": 25,
                "chunk_duration_sec": 15.0,
            },
        )
    ).json()
    assert avatar["status"] == "completed"

    exp_res = await client.post(
        f"/api/v1/projects/{pid}/exports?sync=true",
        json={
            "audio_id": audio["id"],
            "avatar_job_id": avatar["id"],
            "include_subtitles": True,
            "prefer_nvenc": False,
            "fps": 30,
        },
    )
    assert exp_res.status_code == 201
    exp = exp_res.json()
    assert exp["status"] == "completed"
    val = exp["validation_report_json"]
    assert val["passed"] is True
    assert val["width"] == 1080
    assert val["height"] == 1920
    assert val["aspect_ratio"] == "9:16"
    assert abs(val["fps"] - 30.0) <= 0.5
    assert "h264" in val["video_codec"].lower()
    assert "aac" in val["audio_codec"].lower()
    assert val["pixel_format"] == "yuv420p"
    assert val["black_frame_count"] == 0
    assert val["av_drift_ms"] < 120.0

    storage = StorageManager()
    mp4_path = storage.root / exp["output_mp4_path"]
    assert mp4_path.exists() and mp4_path.stat().st_size > 50000

    # Verify preview, download, logs, cancel, re-export APIs
    assert (await client.get(f"/api/v1/exports/{exp['id']}/preview")).status_code == 200
    dl = await client.get(f"/api/v1/exports/{exp['id']}/download")
    assert dl.status_code == 200
    assert "attachment" in dl.headers.get("content-disposition", "").lower()

    status_obj = (await client.get(f"/api/v1/exports/{exp['id']}")).json()
    assert len(status_obj["logs_json"]) >= 4

    print(
        f"[E2E {title}] path={mp4_path} dur={val['duration_sec']}s "
        f"res={val['width']}x{val['height']} fps={val['fps']} "
        f"codecs={val['video_codec']}/{val['audio_codec']} drift={val['av_drift_ms']}ms"
    )
    return {"pid": pid, "export": exp}


async def test_30s_and_2min_full_vertical_mp4_exports(client: httpx.AsyncClient):
    res_30 = await _run_full_e2e(
        client, "E2E 30s Vertical", THIRTY_SEC_SCRIPT, "am_adam"
    )
    assert 20.0 <= res_30["export"]["duration_sec"] <= 48.0

    # Test cancel & re-export API on 30s project
    eid = res_30["export"]["id"]
    reexp = await client.post(f"/api/v1/exports/{eid}/re-export?sync=false")
    assert reexp.status_code == 200
    cancelled = await client.post(f"/api/v1/exports/{reexp.json()['id']}/cancel")
    assert cancelled.status_code == 200

    res_120 = await _run_full_e2e(
        client, "E2E 2-Min Vertical", TWO_MINUTE_SCRIPT, "af_heart"
    )
    assert 90.0 <= res_120["export"]["duration_sec"] <= 160.0
    assert psutil.virtual_memory().percent < 95.0
