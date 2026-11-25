# Setup & Troubleshooting Guide (Windows 11)

## 1. Prerequisites

1. **NVIDIA Driver & CUDA**:
   - Ensure NVIDIA driver supports CUDA 12.1+ (`nvidia-smi` confirmed RTX 3050 6 GB).
2. **FFmpeg (Required — currently missing from PATH)**:
   - Install via winget:
     ```powershell
     winget install Gyan.FFmpeg
     ```
   - Restart terminal and verify `ffmpeg -version`.
3. **Python 3.11 or 3.12 (Recommended for AI Dependencies)**:
   - *Important*: The system currently has **Python 3.14.0**. Many PyTorch/CUDA/ONNX/ComfyUI packages do not yet publish prebuilt wheels for Python 3.14. Install Python 3.11 or 3.12 (or use `uv` / `pyenv-win`) for the `backend/.venv` virtual environment.
4. **Node.js 20+**:
   - Installed (`v24.14.0` verified).
5. **Redis & PostgreSQL**:
   - Recommended via Docker Desktop (or Memurai/WSL2 Redis + local PostgreSQL / Supabase).

---

## 2. Troubleshooting 6 GB VRAM Constraints

- **CUDA Out-of-Memory (OOM)**:
  - Ensure `SEQUENTIAL_GPU_LOCK=true` in `.env` so Celery runs with `--concurrency=1` on the GPU queue.
  - Ensure ComfyUI is launched with `--lowvram` (or `--novram` if sharing with another process) and call `/free` after visual generation.
  - Keep avatar chunk duration at `10–15` seconds and resolution at `512x512` or `576x1024` before upscaling/compositing to `960x1080` via FFmpeg.
## 3. Optional Audio & Alignment Model Download (Phase 2)

Kokoro-82M ONNX (`~337 MB`) and `faster-whisper` `base.en` (`~145 MB`) run on **CPU by default** (`AUDIO_EXECUTION_DEVICE=cpu`) to preserve all 6 GB VRAM for visual/avatar stages:

```powershell
backend\.venv\Scripts\python.exe scripts\download_audio_models.py
```

## 4. Bundled FFmpeg & Final 1080x1920 Export (Phase 5)

The backend uses `imageio-ffmpeg` (`ffmpeg-win-x86_64` with `vstack`, `ass`, `loudnorm`, `libx264`, and `aac`) so Phase 3–5 video rendering and composition work out of the box on Windows 11 even if system `ffmpeg` is not on `PATH`. CPU `libx264` is the reliable default; `prefer_nvenc=true` is optional and auto-falls back to `libx264` if NVENC is unavailable.
