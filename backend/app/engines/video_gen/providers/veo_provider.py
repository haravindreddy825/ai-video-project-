import base64
from pathlib import Path
import time

import cv2
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.engines.video_gen.providers.base import (
    BaseVideoGenProvider,
    ProviderNotConfiguredError,
)
from app.engines.video_gen.schemas import (
    ProviderCapability,
    VideoGenRequest,
    VideoGenResult,
)


class GoogleVeoProvider(BaseVideoGenProvider):
    """
    Real Google Veo 3.1 Gemini API provider.
    Supports Text-to-Video, Image-to-Video (first/last frame & reference images),
    and video continuation/extension up to 8s per request.
    """

    id = "veo_3_1"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    MODEL_BY_QUALITY = {
        "lite": "veo-3.1-lite-generate-preview",
        "fast": "veo-3.1-fast-generate-preview",
        "standard": "veo-3.1-generate-preview",
    }

    def get_capabilities(self) -> ProviderCapability:
        has_key = bool(settings.GEMINI_API_KEY.strip())
        return ProviderCapability(
            id=self.id,
            name="Google Veo 3.1 (Gemini API)",
            kind="cloud_api",
            available=has_key,
            reason=(
                "Ready (GEMINI_API_KEY configured)"
                if has_key
                else "Set GEMINI_API_KEY in .env to enable real Veo 3.1 generation."
            ),
            max_clip_duration_sec=8,
            resolutions=["720p", "1080p"],
            supports_i2v=True,
            supports_first_last_frame=True,
            supports_extension=True,
            supports_reference_images=True,
            cost_per_sec_usd=0.05,
            estimated_120s_cost_usd=6.00,
            requirements="Server-side GEMINI_API_KEY; billed per second ($0.05/s Lite, $0.10/s Fast, $0.40/s Standard).",
        )

    @staticmethod
    def _encode_image(path: Path) -> dict[str, str]:
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        return {
            "bytesBase64Encoded": base64.b64encode(path.read_bytes()).decode("ascii"),
            "mimeType": mime,
        }

    def generate_clip(self, req: VideoGenRequest) -> VideoGenResult:
        api_key = settings.GEMINI_API_KEY.strip()
        if not api_key:
            raise ProviderNotConfiguredError(
                "GEMINI_API_KEY is not configured in .env. "
                "Add a valid Gemini API key to generate real Veo 3.1 clips."
            )

        model = self.MODEL_BY_QUALITY.get(req.quality, settings.VEO_DEFAULT_MODEL)
        instance: dict = {"prompt": req.prompt}

        if req.first_frame_path and req.first_frame_path.exists():
            instance["image"] = self._encode_image(req.first_frame_path)
        if req.last_frame_path and req.last_frame_path.exists():
            instance["lastFrame"] = self._encode_image(req.last_frame_path)
        if req.reference_image_paths:
            refs = [
                {"image": self._encode_image(p), "referenceType": "asset"}
                for p in req.reference_image_paths[:3]
                if p.exists()
            ]
            if refs:
                instance["referenceImages"] = refs
        if req.source_video_path and req.source_video_path.exists():
            instance["video"] = {
                "bytesBase64Encoded": base64.b64encode(
                    req.source_video_path.read_bytes()
                ).decode("ascii"),
                "mimeType": "video/mp4",
            }

        payload = {
            "instances": [instance],
            "parameters": {
                "aspectRatio": req.aspect_ratio,
                "durationSeconds": min(8, max(4, int(req.duration_sec))),
            },
        }

        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
        url = f"{self.BASE_URL}/models/{model}:predictLongRunning"
        logger.info("Submitting Veo 3.1 job (%s, %ss)", model, req.duration_sec)
        resp = httpx.post(url, json=payload, headers=headers, timeout=30.0)
        if resp.status_code >= 400:
            raise RuntimeError(f"Veo API error ({resp.status_code}): {resp.text[:300]}")

        op_name = resp.json()["name"]
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            poll = httpx.get(
                f"{self.BASE_URL}/{op_name}", headers={"x-goog-api-key": api_key}, timeout=15.0
            )
            poll.raise_for_status()
            data = poll.json()
            if data.get("done"):
                if "error" in data:
                    raise RuntimeError(f"Veo generation failed: {data['error']}")
                samples = (
                    data.get("response", {})
                    .get("generateVideoResponse", {})
                    .get("generatedSamples", [])
                )
                if not samples:
                    raise RuntimeError("Veo completed without returning generatedSamples.")
                video_uri = samples[0]["video"]["uri"]
                dl = httpx.get(
                    video_uri,
                    headers={"x-goog-api-key": api_key},
                    follow_redirects=True,
                    timeout=60.0,
                )
                dl.raise_for_status()
                req.output_mp4_path.parent.mkdir(parents=True, exist_ok=True)
                req.output_mp4_path.write_bytes(dl.content)

                cap = cv2.VideoCapture(str(req.output_mp4_path))
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
                fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                last_frame_path = req.output_mp4_path.with_suffix(".last.png")
                if fc > 0:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, fc - 1)
                    ok, frame = cap.read()
                    if ok:
                        cv2.imwrite(str(last_frame_path), frame)
                cap.release()
                return VideoGenResult(
                    provider_id=self.id,
                    output_mp4_path=req.output_mp4_path,
                    duration_sec=round(fc / fps, 2) if fps else float(req.duration_sec),
                    width=w,
                    height=h,
                    last_frame_path=last_frame_path if last_frame_path.exists() else None,
                )
            time.sleep(4.0)

        raise TimeoutError("Veo 3.1 operation timed out after 300s.")
