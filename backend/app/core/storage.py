from pathlib import Path
import shutil
import uuid
from typing import Tuple

from fastapi import UploadFile
from PIL import Image

from app.core.config import settings


class InsufficientDiskSpaceError(RuntimeError):
    """Raised when free disk space falls below MIN_FREE_DISK_GB."""


class StorageManager:
    """Manages local storage directories, disk budget checks, and safe uploads."""

    ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
    ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or settings.resolved_storage_root).resolve()
        self.inputs_dir = self.root / "inputs"
        self.intermediate_dir = self.root / "intermediate"
        self.outputs_dir = self.root / "outputs"
        self.models_dir = self.root / "models"
        for d in (self.inputs_dir, self.intermediate_dir, self.outputs_dir, self.models_dir):
            d.mkdir(parents=True, exist_ok=True)

    def get_disk_stats(self) -> dict[str, float]:
        usage = shutil.disk_usage(self.root)
        gb = 1024 ** 3
        return {
            "total_gb": round(usage.total / gb, 2),
            "used_gb": round(usage.used / gb, 2),
            "free_gb": round(usage.free / gb, 2),
            "min_free_gb": settings.MIN_FREE_DISK_GB,
        }

    def ensure_disk_budget(self) -> None:
        stats = self.get_disk_stats()
        if stats["free_gb"] < settings.MIN_FREE_DISK_GB:
            raise InsufficientDiskSpaceError(
                f"Free disk ({stats['free_gb']} GB) is below minimum ({settings.MIN_FREE_DISK_GB} GB)."
            )

    async def save_character_image(
        self, project_id: str, upload: UploadFile
    ) -> Tuple[str, int, int]:
        self.ensure_disk_budget()
        ext = Path(upload.filename or "avatar.png").suffix.lower()
        if ext not in self.ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError(f"Unsupported image extension '{ext}'. Allowed: {self.ALLOWED_IMAGE_EXTENSIONS}")

        dest_dir = self.inputs_dir / project_id / "characters"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / f"{uuid.uuid4().hex}{ext}"

        content = await upload.read()
        dest_path.write_bytes(content)

        try:
            with Image.open(dest_path) as img:
                width, height = img.size
        except Exception as exc:
            dest_path.unlink(missing_ok=True)
            raise ValueError(f"Invalid image file: {exc}") from exc

        return str(dest_path.relative_to(self.root)).replace("\\", "/"), width, height

    async def save_voice_sample(self, project_id: str, upload: UploadFile) -> str:
        self.ensure_disk_budget()
        ext = Path(upload.filename or "sample.wav").suffix.lower()
        if ext not in self.ALLOWED_AUDIO_EXTENSIONS:
            raise ValueError(f"Unsupported audio extension '{ext}'. Allowed: {self.ALLOWED_AUDIO_EXTENSIONS}")

        dest_dir = self.inputs_dir / project_id / "voices"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / f"{uuid.uuid4().hex}{ext}"

        content = await upload.read()
        if not content:
            raise ValueError("Uploaded voice sample is empty.")
        dest_path.write_bytes(content)
        return str(dest_path.relative_to(self.root)).replace("\\", "/")
