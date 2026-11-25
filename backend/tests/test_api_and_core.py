import io
from pathlib import Path
import httpx
from PIL import Image
import pytest

from app.core.gpu_lock import CrossProcessGPULock
from app.core.vram import ComputeRouter, VRAMMonitor
from app.main import app
from app.workers.tasks import run_video_generation_job


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _make_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (512, 512), color=(40, 120, 200)).save(buf, format="PNG")
    return buf.getvalue()


async def test_health_and_docs(client: httpx.AsyncClient):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    detailed = await client.get("/health/detailed")
    assert detailed.status_code == 200
    body = detailed.json()
    assert body["database"] == "connected"
    assert body["video_spec"]["resolution"] == "1080x1920"
    assert body["video_spec"]["layout"] == "top_bottom_50_50"

    docs = await client.get("/docs")
    assert docs.status_code == 200


async def test_storage_stats(client: httpx.AsyncClient):
    res = await client.get("/api/v1/storage/stats")
    assert res.status_code == 200
    assert res.json()["free_gb"] > 0


async def test_project_crud_lifecycle(client: httpx.AsyncClient):
    create_res = await client.post(
        "/api/v1/projects",
        json={
            "title": "Intro to Neural Networks",
            "description": "2-minute vertical educational video",
            "target_duration_sec": 120,
            "compute_mode": "local_hybrid",
        },
    )
    assert create_res.status_code == 201
    proj = create_res.json()
    project_id = proj["id"]
    assert proj["resolution"] == "1080x1920"
    assert proj["layout_mode"] == "top_bottom_50_50"

    list_res = await client.get("/api/v1/projects")
    assert list_res.status_code == 200
    assert any(p["id"] == project_id for p in list_res.json())

    get_res = await client.get(f"/api/v1/projects/{project_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Intro to Neural Networks"

    patch_res = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"title": "Intro to Neural Networks v2"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Intro to Neural Networks v2"

    del_res = await client.delete(f"/api/v1/projects/{project_id}")
    assert del_res.status_code == 204
    assert (await client.get(f"/api/v1/projects/{project_id}")).status_code == 404


async def test_script_character_voice_and_job_flow(client: httpx.AsyncClient):
    proj_res = await client.post(
        "/api/v1/projects",
        json={"title": "Gradient Descent Explained", "target_duration_sec": 120},
    )
    pid = proj_res.json()["id"]

    # 1. Script creation & retrieval
    script_res = await client.post(
        f"/api/v1/projects/{pid}/scripts",
        json={"raw_text": " ".join(["word"] * 150)},
    )
    assert script_res.status_code == 201
    script = script_res.json()
    assert script["version"] == 1
    assert script["estimated_duration_sec"] == 60.0

    scripts_list = await client.get(f"/api/v1/projects/{pid}/scripts")
    assert scripts_list.status_code == 200
    assert len(scripts_list.json()) == 1

    # 2. Character reference upload
    char_res = await client.post(
        f"/api/v1/projects/{pid}/characters",
        data={"name": "Professor Ada"},
        files={"image": ("ada.png", _make_png_bytes(), "image/png")},
    )
    assert char_res.status_code == 201
    char = char_res.json()
    assert char["width"] == 512
    assert char["height"] == 512
    assert char["identity_pack_json"]["locked"] is True

    bad_char = await client.post(
        f"/api/v1/projects/{pid}/characters",
        data={"name": "Bad"},
        files={"image": ("bad.txt", b"not an image", "text/plain")},
    )
    assert bad_char.status_code == 400

    assert len((await client.get(f"/api/v1/projects/{pid}/characters")).json()) == 1

    # 3. Voice config + sample audio upload
    voice_res = await client.post(
        f"/api/v1/projects/{pid}/voices",
        data={"engine": "chatterbox", "preset_voice_id": "custom", "speaking_rate": "1.05"},
        files={"sample_audio": ("voice.wav", b"RIFF0000WAVEfmt ", "audio/wav")},
    )
    assert voice_res.status_code == 201
    voice = voice_res.json()
    assert voice["engine"] == "chatterbox"
    assert voice["sample_audio_path"].endswith(".wav")
    assert len((await client.get(f"/api/v1/projects/{pid}/voices")).json()) == 1

    # 4. Job creation & status update
    job_res = await client.post(
        f"/api/v1/projects/{pid}/jobs?dispatch=false",
        json={
            "script_id": script["id"],
            "character_id": char["id"],
            "voice_config_id": voice["id"],
        },
    )
    assert job_res.status_code == 201
    job = job_res.json()
    jid = job["id"]
    assert job["status"] == "queued"

    patch_job = await client.patch(
        f"/api/v1/jobs/{jid}",
        json={"status": "running", "current_stage": "voice_generation", "progress_pct": 25},
    )
    assert patch_job.status_code == 200
    assert patch_job.json()["progress_pct"] == 25

    # 5. Execute pipeline task synchronously to verify checkpointing, GPU lock & logs
    result = run_video_generation_job(jid)
    assert result["status"] == "completed"

    final_job = (await client.get(f"/api/v1/jobs/{jid}")).json()
    assert final_job["status"] == "completed"
    assert final_job["progress_pct"] == 100
    assert len(final_job["checkpoint_json"]["completed_stages"]) == 6

    logs = (await client.get(f"/api/v1/jobs/{jid}/logs")).json()
    assert len(logs) >= 6


def test_gpu_lock_and_vram_router(tmp_path: Path):
    vram = VRAMMonitor.get_status()
    assert vram.available is True
    assert "3050" in vram.gpu_name or vram.total_mb > 0

    assert ComputeRouter.select_target("kokoro", "local_hybrid") == "local_gpu"
    target = ComputeRouter.select_target("echomimic_v2", "local_hybrid")
    assert target in {"local_gpu", "cloud_gpu"}

    lock = CrossProcessGPULock(lock_file=tmp_path / "test.gpu.lock")
    with lock.acquire(owner="pytest"):
        assert (tmp_path / "test.gpu.lock").exists()
