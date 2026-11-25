# Phased Implementation Plan

Each phase ends with a runnable verification check and a dedicated Git milestone commit.

---

## Phase 0: Architecture & Project Foundation (Current)
- **Deliverables**: Workspace inspection, model/license audit, system architecture, folder structure, `README.md`, `docs/*`, `.env.example`, `.gitignore`, Git initialization.
- **Gate**: User approval of architecture before Phase 1 begins.

---

## Phase 1: Backend Core, Database & Job Queue
- **Deliverables**:
  - FastAPI application skeleton (`backend/app/main.py`) with healthcheck, CORS, and project/asset/job endpoints.
  - PostgreSQL / SQLAlchemy async models + Alembic migrations.
  - Redis + Celery worker setup (`concurrency=1` GPU queue + CPU queue).
  - `GPUMutex` / sequential VRAM manager and `DiskBudgetGuard` (enforces `MIN_FREE_DISK_GB`).
- **Verification**: Create a project via REST API, enqueue a test Celery task, verify state updates in PostgreSQL and SSE stream.

---

## Phase 2: Audio & Alignment Pipeline (TTS + Whisper)
- **Deliverables**:
  - `TTSEngine` interface + `KokoroTTS` adapter (preset voices) + `ChatterboxTTS` adapter (voice sample cloning).
  - `ASREngine` interface + `FasterWhisperAligner` producing word-level timestamps & `.ass`/`.srt` captions.
  - Script beat planner mapping sentences to exact audio timestamps.
- **Verification**: Submit a 2-minute (~300-word) script, generate full WAV audio + word-level JSON timeline, verify VRAM returns to baseline after each step.

---

## Phase 3: Hybrid Visual Engine & ComfyUI Integration
- **Deliverables**:
  - Programmatic 960x1080 educational slide/diagram renderer (headings, bullet reveals, code/charts, progress bar).
  - ComfyUI headless API client + versioned workflow JSONs (`SDXL-Turbo` / `SD 1.5` / `FLUX.1-schnell-GGUF`).
  - `PySceneDetect` integration for optional user B-roll clips.
- **Verification**: Generate synchronized 960x1080 visual segments matching the Phase 2 word-level timeline.

---

## Phase 4: Avatar Animation Engine (Local 6 GB + Cloud Adapter)
- **Deliverables**:
  - `AvatarEngine` abstract interface.
  - Local 6 GB adapter: `DittoAvatarEngine` (and `MuseTalkEngine` fallback) with chunked 10–15s audio processing to stay safely under 6 GB VRAM.
  - Cloud GPU adapter: `CloudAvatarEngine` supporting RunPod/Modal/Remote ComfyUI for `EchoMimicV2` (upper-body + hand gestures), `InfiniteTalk`, and `LongCat-Video-Avatar`.
- **Verification**: Animate a character reference image against a 2-minute narration track without CUDA OOM; verify lip-sync, blinking, and head motion.

---

## Phase 5: 50/50 Split-Screen Compositor & Continuous MP4 Export
- **Deliverables**:
  - FFmpeg + OpenCV compositor stitching the 50% visual stream (`960x1080`) and 50% avatar stream (`960x1080`) onto a `1920x1080` canvas with clean divider, synchronized captions, and `-16 LUFS` audio normalization.
  - Single continuous MP4 export (`libx264`, `yuv420p`, `+faststart`).
- **Verification**: End-to-end CLI/API test producing a complete, synchronized 2-minute 1080p MP4 from a script, character image, and voice.

---

## Phase 6: Next.js Studio UI & End-to-End Polish
- **Deliverables**:
  - Next.js + TypeScript + Tailwind CSS Studio UI:
    - Script editor + duration estimator
    - Character image uploader & face-framing preview
    - Voice preset / sample uploader
    - Compute mode selector (Local 6 GB vs Cloud GPU)
    - Live SSE progress bar + stage logs
    - Built-in MP4 preview player & export download
  - Final integration tests & documentation updates.
- **Verification**: Complete 2-minute video produced entirely through the web UI.
