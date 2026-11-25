from dataclasses import dataclass
import gc
import subprocess
from typing import Literal, Optional

import httpx
import psutil

from app.core.config import settings
from app.core.logging import logger


@dataclass
class VRAMStatus:
    available: bool
    gpu_name: str
    total_mb: int
    used_mb: int
    free_mb: int
    source: str


class VRAMMonitor:
    """Monitors NVIDIA GPU VRAM via NVML with nvidia-smi fallback."""

    @staticmethod
    def get_status() -> VRAMStatus:
        try:
            import pynvml

            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="ignore")
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            pynvml.nvmlShutdown()
            return VRAMStatus(
                available=True,
                gpu_name=str(name),
                total_mb=int(mem.total // (1024 * 1024)),
                used_mb=int(mem.used // (1024 * 1024)),
                free_mb=int(mem.free // (1024 * 1024)),
                source="nvml",
            )
        except Exception:
            pass

        try:
            proc = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,memory.used,memory.free",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=3,
                check=True,
            )
            line = proc.stdout.strip().splitlines()[0]
            name, total, used, free = [part.strip() for part in line.split(",")]
            return VRAMStatus(
                available=True,
                gpu_name=name,
                total_mb=int(total),
                used_mb=int(used),
                free_mb=int(free),
                source="nvidia-smi",
            )
        except Exception as exc:
            logger.warning("GPU VRAM telemetry unavailable: %s", exc)
            return VRAMStatus(
                available=False,
                gpu_name="unavailable",
                total_mb=0,
                used_mb=0,
                free_mb=0,
                source="none",
            )

    @staticmethod
    def unload_models(comfyui_url: Optional[str] = None) -> VRAMStatus:
        """Deterministically unload Python/PyTorch/ComfyUI models and reclaim VRAM."""
        gc.collect()
        try:
            import sys

            if "torch" in sys.modules:
                torch = sys.modules["torch"]
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.ipc_collect()
        except Exception as exc:
            logger.warning("torch.cuda.empty_cache() failed: %s", exc)

        target_comfy = comfyui_url or settings.COMFYUI_URL
        if target_comfy:
            try:
                httpx.post(
                    f"{target_comfy.rstrip('/')}/free",
                    json={"unload_models": True, "free_memory": True},
                    timeout=2.0,
                )
            except Exception:
                pass

        return VRAMMonitor.get_status()

    @staticmethod
    def get_ram_stats() -> dict[str, float]:
        vm = psutil.virtual_memory()
        gb = 1024 ** 3
        return {
            "total_gb": round(vm.total / gb, 2),
            "available_gb": round(vm.available / gb, 2),
            "used_gb": round(vm.used / gb, 2),
            "percent": float(vm.percent),
        }


class ComputeRouter:
    """Decides local RTX 3050 6GB vs Cloud GPU execution with automatic fallback."""

    MODEL_VRAM_ESTIMATES_MB = {
        "kokoro": 1500,
        "chatterbox": 4800,
        "faster-whisper": 2500,
        "sdxl-turbo": 5000,
        "sd15": 3500,
        "ditto": 4200,
        "musetalk": 4000,
        "echomimic_v2": 16000,
        "infinitetalk": 16000,
        "longcat": 22000,
    }

    @classmethod
    def select_target(
        cls,
        engine_name: str,
        compute_mode: Optional[str] = None,
    ) -> Literal["local_gpu", "cloud_gpu", "cpu"]:
        mode = compute_mode or settings.COMPUTE_MODE
        required_mb = cls.MODEL_VRAM_ESTIMATES_MB.get(engine_name.lower(), 4500)
        cloud_configured = (
            settings.CLOUD_GPU_PROVIDER != "none" and bool(settings.CLOUD_GPU_ENDPOINT)
        )

        if mode == "cloud_preferred" and cloud_configured:
            return "cloud_gpu"

        if required_mb > settings.LOCAL_VRAM_LIMIT_MB:
            if cloud_configured and mode != "local_only":
                logger.info(
                    "Engine %s requires ~%d MB (> %d MB limit); routing to cloud_gpu.",
                    engine_name,
                    required_mb,
                    settings.LOCAL_VRAM_LIMIT_MB,
                )
                return "cloud_gpu"
            logger.warning(
                "Engine %s requires ~%d MB (> %d MB limit) and cloud is unconfigured.",
                engine_name,
                required_mb,
                settings.LOCAL_VRAM_LIMIT_MB,
            )

        vram = VRAMMonitor.get_status()
        if not vram.available:
            return "cloud_gpu" if cloud_configured and mode != "local_only" else "cpu"

        if vram.free_mb < required_mb:
            vram = VRAMMonitor.unload_models()
            if vram.free_mb < required_mb and cloud_configured and mode != "local_only":
                logger.warning(
                    "Insufficient free VRAM (%d MB < %d MB) for %s; falling back to cloud_gpu.",
                    vram.free_mb,
                    required_mb,
                    engine_name,
                )
                return "cloud_gpu"

        return "local_gpu"
