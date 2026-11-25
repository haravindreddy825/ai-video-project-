# OpenSource AI Video Studio

A self-hosted, modular AI video production studio that transforms a **written script**, a **character reference image**, and a **voice selection or sample** into a synchronized **2-minute (or longer) educational video** featuring a **50% educational visuals / 50% animated avatar** split-screen layout and a single continuous MP4 export.

---

## Core Capabilities

- **50/50 Split-Screen Educational Format**: Dedicated half-screen for synchronized educational visuals (diagrams, slides, code/charts, and AI-generated illustrations) and half-screen for an expressive animated presenter.
- **Script-to-Timeline Synchronization**: Uses `faster-whisper` word-level forced alignment to lock visual transitions, emphasis overlays, and subtitles to exact spoken timestamps.
- **Expressive Avatar Animation**: Supports lip synchronization, emotion-aware facial expressions, natural blinking, eye gaze, head motion, and (via cloud GPU mode) upper-body & hand gestures.
- **Hardware-Aware Execution (6 GB VRAM Safe)**: Built around a **Sequential GPU Mutex** that loads one model at a time on local 6 GB VRAM GPUs (e.g., NVIDIA RTX 3050 Laptop), with an interchangeable **Cloud GPU Backend** for heavy full-body diffusion models (`LongCat-Video-Avatar`, `EchoMimicV2`, `InfiniteTalk`).
- **Interchangeable AI Engines**: Clean abstract interfaces for TTS, ASR, Visual Generation, and Avatar Animation — no vendor lock-in.

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

## Status

**Phase 0 (Architecture & Foundation)**: Completed and awaiting architecture approval before Phase 1 implementation begins.
