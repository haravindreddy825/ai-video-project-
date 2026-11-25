import json
from pathlib import Path
import time
import uuid

import httpx

from app.core.config import settings
from app.core.gpu_lock import CrossProcessGPULock
from app.core.logging import logger
from app.core.vram import VRAMMonitor


class ComfyUIUnavailableError(RuntimeError):
    """Raised when ComfyUI server is offline or cannot generate an image."""


class ComfyUIImageAdapter:
    """
    Headless ComfyUI API client for script-driven educational illustrations
    (SDXL-Turbo / SD 1.5). Acquires CrossProcessGPULock and calls /free after
    generation to keep 6GB VRAM clean.
    """

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.COMFYUI_URL).rstrip("/")

    def is_available(self) -> bool:
        try:
            res = httpx.get(f"{self.base_url}/system_stats", timeout=1.5)
            return res.status_code == 200
        except Exception:
            return False

    def generate_illustration(
        self, prompt: str, output_png: Path, timeout_sec: int = 60
    ) -> Path:
        if not self.is_available():
            raise ComfyUIUnavailableError(
                f"ComfyUI server is not reachable at {self.base_url}."
            )

        workflow_path = (
            Path(__file__).resolve().parents[4]
            / "comfyui_workflows"
            / "sdxl_turbo_educational_illustration.json"
        )
        if not workflow_path.exists():
            raise ComfyUIUnavailableError(f"Workflow template missing: {workflow_path}")

        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
        # Inject positive prompt into node "6"
        if "6" in workflow and "inputs" in workflow["6"]:
            workflow["6"]["inputs"]["text"] = (
                f"clean flat vector educational illustration on white background, {prompt}, minimalist, high clarity, no text"
            )

        client_id = uuid.uuid4().hex
        gpu_lock = CrossProcessGPULock()
        with gpu_lock.acquire(owner=f"comfyui-{client_id[:8]}"):
            try:
                resp = httpx.post(
                    f"{self.base_url}/prompt",
                    json={"prompt": workflow, "client_id": client_id},
                    timeout=10.0,
                )
                resp.raise_for_status()
                prompt_id = resp.json()["prompt_id"]

                deadline = time.monotonic() + timeout_sec
                while time.monotonic() < deadline:
                    hist = httpx.get(f"{self.base_url}/history/{prompt_id}", timeout=5.0)
                    data = hist.json()
                    if prompt_id in data:
                        outputs = data[prompt_id].get("outputs", {})
                        for node_out in outputs.values():
                            images = node_out.get("images") or []
                            if images:
                                img_info = images[0]
                                view = httpx.get(
                                    f"{self.base_url}/view",
                                    params={
                                        "filename": img_info["filename"],
                                        "subfolder": img_info.get("subfolder", ""),
                                        "type": img_info.get("type", "output"),
                                    },
                                    timeout=10.0,
                                )
                                view.raise_for_status()
                                output_png.parent.mkdir(parents=True, exist_ok=True)
                                output_png.write_bytes(view.content)
                                return output_png
                    time.sleep(0.5)
                raise ComfyUIUnavailableError("ComfyUI generation timed out.")
            except ComfyUIUnavailableError:
                raise
            except Exception as exc:
                logger.warning("ComfyUI generation failed: %s", exc)
                raise ComfyUIUnavailableError(str(exc)) from exc
            finally:
                VRAMMonitor.unload_models(self.base_url)
