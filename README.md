# OpenSource AI Video Studio

A self-hosted, modular AI video production studio that transforms a **written script**, a **character reference image**, and a **voice selection or sample** into a synchronized **2-minute (or longer) vertical 9:16 (1080x1920) educational video** featuring a **top/bottom 50/50 split-screen layout** (top `1080x960` educational visuals, bottom `1080x960` animated avatar) and a single continuous MP4 export.

---

## Core Capabilities

- **Vertical 9:16 Top/Bottom 50/50 Layout (`1080x1920`)**: Top `1080x960` for synchronized educational visuals (diagrams, slides, code/charts, and AI-generated illustrations) and bottom `1080x960` for an expressive animated presenter.
- **Voice-First Timeline Source of Truth**: Complete voice narration is generated first, then `faster-whisper` word-level forced alignment establishes the authoritative timeline for all visual transitions, avatar chunks, and captions.
- **Expressive & Identity-Consistent Avatar**: Maintains character identity across every chunked segment with frame/audio continuity checks, lip sync, emotion-aware expressions, blinking, and head motion (plus upper-body & hand gestures via optional Cloud GPU).
- **Cross-Process GPU Locking & VRAM Guard**: Uses a cross-process Redis + file lock, real-time VRAM monitoring, automatic model unloading, and local/cloud fallback for 6 GB VRAM GPUs (RTX 3050 Laptop).
- **Resilient Job Recovery**: Per-stage checkpointing with automatic retry and recovery on transient failures or CUDA OOM.

---

## Target Hardware Baseline

| Component | Development Spec | Architectural Design Implication |
| :--- | :--- | :--- |
| **CPU** | Intel Core i7-13620H | Fast CPU preprocessing, FFmpeg encoding (`libx264`), OpenCV/PySceneDetect |
| **GPU** | NVIDIA RTX 3050 Laptop (6 GB VRAM) | Strict sequential model loading + FP16/INT8 quantization |
| **System RAM** | 16 GB | Avoid keeping multiple models pinned in CPU RAM; explicit `gc.collect()` |
| **Storage** | ~266 GB free | Disk-budget guard before downloading any weights; max ~120 GB model cache |
| **OS** | Windows 11 | Native Windows + optional Docker/WSL2 for Redis/Postgres/ComfyUI |

---

## Technology Stack

- **Frontend**: Next.js (App Router), React, TypeScript, Tailwind CSS
- **Backend**: Python, FastAPI, Pydantic
- **Background Jobs**: Redis + Celery (single GPU worker queue + CPU post-processing queue)
- **Database**: PostgreSQL (or Supabase)
- **AI Orchestration**: ComfyUI (headless API) + Python Engine Adapters
- **Media & Analysis**: FFmpeg, OpenCV, PySceneDetect, `faster-whisper`

---

## Project Structure

```text
ai-video-studio/
├── frontend/                  # Next.js + React + TypeScript + Tailwind CSS
│   └── src/
│       ├── app/               # App Router pages (studio, projects, jobs, settings)
│       ├── components/        # Script editor, avatar/voice picker, timeline preview
│       └── lib/               # Typed API client & WebSocket/SSE job status hooks
├── backend/                   # FastAPI application & Celery workers
│   └── app/
│       ├── api/               # REST & SSE endpoints (projects, assets, render jobs)
│       ├── core/              # Config, VRAM lock/scheduler, disk budget checker
│       ├── models/            # SQLAlchemy ORM models
│       ├── schemas/           # Pydantic request/response schemas
│       ├── services/          # Script segmenter, timeline planner, cloud router
│       ├── workers/           # Celery tasks (TTS -> ASR -> Visuals -> Avatar -> Render)
│       └── engines/           # Interchangeable AI engine adapters
│           ├── tts/           # Kokoro-82M, Chatterbox-Turbo
│           ├── asr/           # faster-whisper word alignment
│           ├── visuals/       # Hybrid programmatic slide/diagram + ComfyUI SDXL-Turbo/FLUX
│           ├── avatar/        # Local (Ditto, MuseTalk, LivePortrait) & Cloud (EchoMimicV2, InfiniteTalk, LongCat)
│           └── compositor/    # FFmpeg + OpenCV 50/50 split-screen & MP4 exporter
├── comfyui_workflows/         # Versioned ComfyUI API workflow JSON templates
├── docs/                      # Detailed architecture, model audit, roadmap, setup guide
├── scripts/                   # Environment check, model downloader, dev startup scripts
└── storage/                   # Local workspace for inputs, intermediate clips, outputs, models
```

---

## Documentation

- [**System Architecture & Rendering Pipeline**](docs/ARCHITECTURE.md)
- [**Model Research, Licenses & Hardware Compatibility**](docs/MODELS_AND_LICENSES.md)
- [**Phased Implementation Plan**](docs/IMPLEMENTATION_PLAN.md)
- [**Setup & Troubleshooting Guide**](docs/SETUP_AND_TROUBLESHOOTING.md)

---

## Quick Start (Windows 11 — First Local Release)

1. **First-time setup** (if not already installed):
   - Copy `.env.example` to `.env` (defaults to local SQLite; zero Docker/Postgres required).
   - Install backend dependencies in `backend\.venv` (Python 3.12) and frontend dependencies in `frontend\node_modules`.
   - Download local CPU audio/alignment models (~480 MB):
     ```powershell
     backend\.venv\Scripts\python.exe scripts\download_audio_models.py
     ```
2. **Launch the complete studio** (one click or one command):
   - Double-click `start.bat` or run:
     ```powershell
     .\scripts\start_studio.ps1
     ```
3. **Open in Browser**:
   - **Studio UI**: `http://127.0.0.1:3000`
   - **Backend API & Docs**: `http://127.0.0.1:8000/docs`
   - **Default Sign-In** (optional unless `AUTH_REQUIRED=true` in `.env`): `admin` / `studio-local`

## Status

- **First Local Release (v0.1.0)**: Ready and end-to-end verified on Windows 11 (Dashboard, Script & Kokoro-82M TTS + faster-whisper Alignment, Character Identity & Expressive Avatar, Educational Visuals, 1080×1920 Vertical MP4 Export & Download).
