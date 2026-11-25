from pathlib import Path
import httpx
import pytest

from app.core.storage import StorageManager
from app.engines.audio.emotion_planner import EmotionPlanner
from app.engines.audio.tts_engine import KokoroONNXTTSEngine
from app.engines.audio.voice_manager import VoiceManager
from app.main import app


SHORT_SCRIPT = (
    "Welcome to OpenSource AI Video Studio! "
    "How do neural networks learn from data? "
    "For example, imagine adjusting a dial until your prediction matches the target. "
    "This works because gradient descent minimizes the error step by step. "
    "In summary, small updates lead to accurate models."
)

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


def test_voice_manager_and_chunking():
    presets = VoiceManager.list_presets()
    assert len(presets) >= 6
    assert VoiceManager.validate_voice_id("af_heart") == "af_heart"
    with pytest.raises(ValueError):
        VoiceManager.validate_voice_id("nonexistent_voice")

    # Verify long script chunking loses zero words
    chunks = KokoroONNXTTSEngine.chunk_text(TWO_MINUTE_SCRIPT)
    assert len(chunks) >= 8
    assert all(len(c) <= KokoroONNXTTSEngine.MAX_CHUNK_CHARS for c in chunks)
    original_words = len(TWO_MINUTE_SCRIPT.split())
    chunked_words = sum(len(c.split()) for c in chunks)
    assert chunked_words == original_words


def test_emotion_planner_preserves_script():
    intel = EmotionPlanner.analyze(SHORT_SCRIPT)
    assert intel.original_script == SHORT_SCRIPT
    assert intel.total_sentences == 5
    types = [s.sentence_type for s in intel.sentences]
    assert "question" in types
    assert "example" in types
    assert "explanation" in types
    assert "conclusion" in types
    assert all(s.facial_expression and s.hand_gesture and s.head_movement for s in intel.sentences)


async def test_short_script_audio_api_and_recovery(client: httpx.AsyncClient):
    res = await client.get("/api/v1/audio/voices")
    assert res.status_code == 200
    assert any(v["id"] == "af_heart" for v in res.json())

    proj = (await client.post("/api/v1/projects", json={"title": "Audio Phase 2 Short"})).json()
    pid = proj["id"]

    # Invalid voice rejected
    bad = await client.post(
        f"/api/v1/projects/{pid}/audio/generate?sync=true",
        json={"script_text": SHORT_SCRIPT, "voice_id": "bad_voice"},
    )
    assert bad.status_code == 400

    # Generate short narration synchronously with speed & volume
    gen = await client.post(
        f"/api/v1/projects/{pid}/audio/generate?sync=true",
        json={
            "script_text": SHORT_SCRIPT,
            "voice_id": "af_bella",
            "speed": 1.05,
            "volume": 0.95,
            "auto_align": True,
        },
    )
    assert gen.status_code == 201
    track = gen.json()
    aid = track["id"]
    assert track["status"] == "completed"
    assert track["progress_pct"] == 100
    assert track["duration_sec"] > 5.0
    assert track["original_script_text"] == SHORT_SCRIPT

    # Verify WAV file saved & previewable
    storage = StorageManager()
    wav_path = storage.root / track["audio_file_path"]
    assert wav_path.exists()
    preview = await client.get(f"/api/v1/audio/{aid}/preview")
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("audio/wav")

    # Verify alignment & pause detection
    align_res = await client.get(f"/api/v1/audio/{aid}/alignment")
    assert align_res.status_code == 200
    align_data = align_res.json()["alignment"]
    assert align_data["validation"]["passed"] is True
    assert len(align_data["words"]) >= 35
    assert len(align_data["sentences"]) >= 4
    assert len(align_data["pauses"]) >= 1

    # Verify list & re-align endpoints
    assert len((await client.get(f"/api/v1/projects/{pid}/audio")).json()) == 1
    realign = await client.post(f"/api/v1/audio/{aid}/align", json={"language": "en"})
    assert realign.status_code == 200
    assert realign.json()["status"] == "completed"

    # Failed generation recovery check: missing WAV on re-align returns 404 without crashing
    wav_path.unlink()
    missing_align = await client.post(f"/api/v1/audio/{aid}/align", json={"language": "en"})
    assert missing_align.status_code == 404


async def test_30_second_and_2_minute_narrations(client: httpx.AsyncClient):
    proj = (await client.post("/api/v1/projects", json={"title": "Long Narration Tests"})).json()
    pid = proj["id"]

    # 1. Actual ~30-second narration
    res_30 = await client.post(
        f"/api/v1/projects/{pid}/audio/generate?sync=true",
        json={"script_text": THIRTY_SEC_SCRIPT, "voice_id": "am_adam", "speed": 1.0, "auto_align": True},
    )
    assert res_30.status_code == 201
    t30 = res_30.json()
    assert t30["status"] == "completed"
    assert 20.0 <= t30["duration_sec"] <= 48.0
    v30 = t30["alignment_json"]["validation"]
    assert v30["passed"] is True
    assert v30["monotonic_ok"] is True
    assert v30["within_duration_ok"] is True
    assert v30["coverage_ratio"] >= 0.85

    # 2. Actual ~2-minute narration
    res_120 = await client.post(
        f"/api/v1/projects/{pid}/audio/generate?sync=true",
        json={"script_text": TWO_MINUTE_SCRIPT, "voice_id": "af_heart", "speed": 1.0, "auto_align": True},
    )
    assert res_120.status_code == 201
    t120 = res_120.json()
    assert t120["status"] == "completed"
    assert 90.0 <= t120["duration_sec"] <= 160.0
    v120 = t120["alignment_json"]["validation"]
    assert v120["passed"] is True
    assert v120["monotonic_ok"] is True
    assert v120["within_duration_ok"] is True
    assert v120["coverage_ratio"] >= 0.85
    assert len(t120["alignment_json"]["pauses"]) >= 5
