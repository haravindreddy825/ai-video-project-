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
- **Disk Space Warnings**:
  - Before downloading weights, run `scripts/check_disk.py` (to be added in Phase 1). Never exceed `MAX_MODEL_STORAGE_GB=120`.
