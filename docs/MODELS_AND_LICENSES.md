# Model Research, License Audit & Hardware Compatibility

All models were evaluated against the development hardware (**NVIDIA RTX 3050 Laptop GPU, 6 GB VRAM, 16 GB RAM, ~266 GB free disk**) and strict **open-source / commercial-safe licensing** requirements.

---

## 1. Requested Avatar Models Investigation

| Model | GitHub Repository | License | Commercial Use? | VRAM Requirement | Verdict for 6 GB VRAM |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **LongCat-Video-Avatar** | `meituan-longcat/LongCat-Video` | **MIT** | Yes | ~42.7 GB (BF16), ~21.3 GB (INT8), ~10.7 GB (INT4) | **Cloud GPU Only.** 13.6B DiT cannot fit in 6 GB VRAM. |
| **EchoMimicV2** | `antgroup/echomimic_v2` | **Apache-2.0** | Yes | ~16–24 GB recommended (A100/4090D/V100); OOMs on 6 GB without extreme sharding | **Cloud GPU Recommended.** Best open-license option for upper-body + hand gestures. |
| **InfiniteTalk** | `MeiGen-AI/InfiniteTalk` | **Apache-2.0** | Yes | ~16 GB+ (quantized Q4/Q6 via WanVideoWrapper) to 80 GB native | **Cloud GPU Only.** Built on Wan 2.1 video backbone; exceeds 6 GB VRAM. |

---

## 2. Local 6 GB VRAM-Capable Avatar Engines

| Model | GitHub Repository | License | Commercial Caveats | VRAM Footprint | Role in Studio |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ditto** | `antgroup/ditto-talkinghead` | **Apache-2.0** | None (permissive) | **~3–5 GB** | **Primary Local Avatar Engine.** Motion-space diffusion with natural head movement, blinking, and expressions. |
| **MuseTalk** | `TMElyralab/MuseTalk` | **MIT** | Relies on Whisper/DWPose/SD-VAE (MIT/Apache) | **~4 GB (FP16)** | **Secondary Local Lip-Sync Engine.** Very reliable on 4–6 GB GPUs. |
| **LivePortrait** | `KwaiVGI/LivePortrait` | **MIT (code)** | InsightFace weights are **non-commercial**; must swap detector for MediaPipe/BlazeFace for commercial use | **~4–6 GB (FP16)** | **Expression & Gaze Enhancer.** Great for blinking, eye movement, and head pose control. |
| **SadTalker** | `OpenTalker/SadTalker` | **Apache-2.0 (code)** | Some 3DMM / GFPGAN checkpoints have non-commercial clauses | **~4–6 GB (256px)** | **Fallback Only** (lower visual fidelity than Ditto/MuseTalk). |

---

## 3. Text-to-Speech (TTS) & Voice Cloning

| Model | GitHub Repository | License | Commercial Use? | VRAM Footprint | Role in Studio |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Kokoro-82M** | `hexgrad/kokoro` | **Apache-2.0** | Yes | **~1–2 GB** (or CPU) | **Default Preset Voice Engine.** Fast, crisp, multi-voice narration. |
| **Chatterbox-Turbo (350M)** | `resemble-ai/chatterbox` | **MIT** | Yes | **~4–6 GB** | **Default Voice Cloning Engine.** Zero-shot cloning from user voice sample. |
| **F5-TTS** | `SWivid/F5-TTS` | MIT (code) / **CC-BY-NC-4.0** (weights) | **No** (weights are non-commercial) | ~4–6 GB | **Excluded from default** due to NC weight license. |

---

## 4. Speech Recognition, Visual Generation & Scene Analysis

| Component | Tool / Model | License | VRAM Footprint | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **ASR / Forced Alignment** | `faster-whisper` (`small`/`medium` INT8) | **MIT** | **~1.5–3.0 GB** | Word-level timestamps for exact visual sync. |
| **Scene Analysis** | `PySceneDetect` | **BSD-3-Clause** | **0 GB (CPU)** | Shot boundary detection for user-supplied B-roll. |
| **Visuals (Text/Diagrams)** | Pillow / CairoSVG / Matplotlib / OpenCV | **MIT / BSD / HPND** | **0 GB (CPU)** | Renders crisp 960x1080 slides, diagrams, and kinetic text. |
| **Visuals (AI Images)** | **SDXL-Turbo** (via ComfyUI) | **Stability AI Community License** | **~4.5–5.5 GB (FP16)** | Commercial allowed under $1M annual revenue. Fast 1–4 step generation. |
| **Visuals (AI Images Alt)** | **SD 1.5** (via ComfyUI) | **CreativeML Open RAIL-M** | **~3–4 GB (FP16)** | Ultra-safe 6 GB fallback. |
| **Visuals (AI Images HQ)** | **FLUX.1-schnell (GGUF Q4)** | **Apache-2.0** | **~6 GB (tight, CPU offload)** | Best quality & Apache-2.0, but slower on 6 GB due to T5-XXL CPU offload. |
| **Orchestration** | **ComfyUI** | **GPLv3** | Dynamic | Runs as a separate local headless service via HTTP API (process-isolated). |
| **Video Processing** | **FFmpeg** + **OpenCV** | LGPL/GPL (FFmpeg) / Apache-2.0 (OpenCV) | **0 GB (CPU)** | 50/50 split-screen compositing and final MP4 export. |

---

## 5. Storage Budget (~266 GB Available)

To protect the host machine from disk exhaustion, the backend enforces a **120 GB model cache cap** and **40 GB minimum free disk guard** before any model download:

| Component | Estimated Disk Size |
| :--- | :--- |
| Kokoro-82M weights | ~0.4 GB |
| Chatterbox-Turbo weights | ~1.5 GB |
| faster-whisper (`small` + `medium`) | ~2.0 GB |
| Ditto / MuseTalk weights | ~6.0 GB |
| ComfyUI + SDXL-Turbo / SD 1.5 | ~10.0 GB |
| Python venv + Node modules + Docker | ~12.0 GB |
| **Total Baseline Footprint** | **~32 GB** (leaves >230 GB free for projects & exports) |
