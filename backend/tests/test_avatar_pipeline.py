import io
import cv2
import httpx
import numpy as np
from PIL import Image, ImageDraw
import pytest

from app.core.storage import StorageManager
from app.engines.avatar.adapters.local_expressive import LocalExpressiveAvatarAdapter
from app.engines.avatar.timeline_driver import AvatarTimelineDriver
from app.main import app


SHORT_EXPLAINER = (
    "Welcome to our neural network lesson! "
    "How do layers learn features from images? "
    "This works because backpropagation updates every weight carefully."
)

THIRTY_SEC_EXPLAINER = (
    "Have you ever wondered how computers understand human language? "
    "Modern language models break sentences into small pieces called tokens. "
    "For example, a single word might become one or two tokens depending on how common it is. "
    "Next, each token is converted into a list of numbers known as an embedding vector. "
    "Because similar words have similar vectors, the model can measure meaning mathematically. "
    "In summary, embeddings turn text into geometry so machines can reason."
)


def _make_portrait_png() -> bytes:
    """Create a synthetic portrait with clear face/eyes/mouth features for OpenCV."""
    img = Image.new("RGB", (720, 960), color=(32, 42, 62))
    draw = ImageDraw.Draw(img)
    # Torso / shoulders
    draw.ellipse([160, 560, 560, 1020], fill=(45, 95, 160))
    # Neck & head
    draw.rectangle([320, 470, 400, 600], fill=(228, 185, 155))
    draw.ellipse([235, 200, 485, 500], fill=(235, 192, 162))
    # Hair
    draw.pieslice([225, 175, 495, 360], start=180, end=360, fill=(45, 35, 30))
    # Eyes & eyebrows
    draw.ellipse([295, 315, 330, 340], fill=(255, 255, 255))
    draw.ellipse([390, 315, 425, 340], fill=(255, 255, 255))
    draw.ellipse([307, 321, 320, 334], fill=(35, 30, 30))
    draw.ellipse([402, 321, 415, 334], fill=(35, 30, 30))
    draw.line([290, 300, 335, 297], fill=(45, 35, 30), width=5)
    draw.line([385, 297, 430, 300], fill=(45, 35, 30), width=5)
    # Mouth
    draw.arc([325, 405, 395, 440], start=10, end=170, fill=(165, 65, 70), width=5)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def test_all_9_emotions_supported():
    required = {
        "happy",
        "serious",
        "curious",
        "surprised",
        "thinking",
        "explaining",
        "confident",
        "concerned",
        "neutral",
    }
    assert required.issubset(set(LocalExpressiveAvatarAdapter.EMOTION_PARAMS.keys()))
    assert AvatarTimelineDriver.EMOTION_MAP["enthusiastic"] == "happy"


async def test_short_and_30s_synchronized_avatar_pipeline(client: httpx.AsyncClient):
    proj = (await client.post("/api/v1/projects", json={"title": "Avatar Phase 3"})).json()
    pid = proj["id"]

    # 1. Upload character & preview/approve canonical 1080x960 identity pack
    char_res = await client.post(
        f"/api/v1/projects/{pid}/characters",
        data={"name": "Instructor Nova"},
        files={"image": ("nova.png", _make_portrait_png(), "image/png")},
    )
    assert char_res.status_code == 201
    cid = char_res.json()["id"]

    prev_img = await client.get(f"/api/v1/characters/{cid}/preview")
    assert prev_img.status_code == 200
    assert prev_img.headers["content-type"] == "image/png"

    approved = await client.post(f"/api/v1/characters/{cid}/approve")
    assert approved.status_code == 200
    assert approved.json()["identity_pack_json"]["approved"] is True
    assert approved.json()["identity_pack_json"]["width"] == 1080
    assert approved.json()["identity_pack_json"]["height"] == 960

    # 2. Generate real Phase 2 short audio
    audio_short = (
        await client.post(
            f"/api/v1/projects/{pid}/audio/generate?sync=true",
            json={"script_text": SHORT_EXPLAINER, "voice_id": "af_heart", "auto_align": True},
        )
    ).json()
    assert audio_short["status"] == "completed"

    # 3. Render short synchronized avatar MP4 (auto adapter -> local_expressive fallback)
    av_short_res = await client.post(
        f"/api/v1/projects/{pid}/avatar/generate?sync=true",
        json={
            "character_id": cid,
            "audio_id": audio_short["id"],
            "adapter": "auto",
            "fps": 25,
            "chunk_duration_sec": 4.0,
        },
    )
    assert av_short_res.status_code == 201
    av_short = av_short_res.json()
    assert av_short["status"] == "completed"
    assert av_short["adapter_used"] == "local_expressive"
    assert av_short["width"] == 1080
    assert av_short["height"] == 960
    assert av_short["continuity_report_json"]["passed"] is True
    assert av_short["continuity_report_json"]["av_drift_ms"] < 120.0

    # Verify MP4 is non-static and has exact 1080x960 dimensions
    storage = StorageManager()
    mp4_path = storage.root / av_short["video_file_path"]
    assert mp4_path.exists()
    cap = cv2.VideoCapture(str(mp4_path))
    ok1, f1 = cap.read()
    cap.set(cv2.CAP_PROP_POS_FRAMES, 15)
    ok2, f2 = cap.read()
    cap.release()
    assert ok1 and ok2
    assert f1.shape == (960, 1080, 3)
    assert float(np.mean(np.abs(f1.astype(np.float32) - f2.astype(np.float32)))) > 0.2

    # Preview MP4 endpoint
    prev_mp4 = await client.get(f"/api/v1/avatar/{av_short['id']}/preview")
    assert prev_mp4.status_code == 200
    assert prev_mp4.headers["content-type"] == "video/mp4"

    # 4. Generate real Phase 2 30-second audio + 30-second chunked avatar MP4
    audio_30 = (
        await client.post(
            f"/api/v1/projects/{pid}/audio/generate?sync=true",
            json={"script_text": THIRTY_SEC_EXPLAINER, "voice_id": "am_adam", "auto_align": True},
        )
    ).json()
    assert audio_30["status"] == "completed"

    av_30_res = await client.post(
        f"/api/v1/projects/{pid}/avatar/generate?sync=true",
        json={
            "character_id": cid,
            "audio_id": audio_30["id"],
            "adapter": "local_expressive",
            "fps": 25,
            "chunk_duration_sec": 10.0,
        },
    )
    assert av_30_res.status_code == 201
    av_30 = av_30_res.json()
    assert av_30["status"] == "completed"
    report_30 = av_30["continuity_report_json"]
    assert report_30["passed"] is True
    assert report_30["segments_checked"] >= 2
    assert report_30["boundary_ssim_min"] >= 0.80
    assert report_30["av_drift_ms"] < 120.0
    assert av_30["duration_sec"] >= 20.0

    # 5. Error recovery: missing character/audio returns 404
    bad_av = await client.post(
        f"/api/v1/projects/{pid}/avatar/generate?sync=true",
        json={"character_id": "missing", "audio_id": audio_30["id"]},
    )
    assert bad_av.status_code == 404
