from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "OpenSource AI Video Studio"
    APP_VERSION: str = "0.1.0"
    APP_ENV: Literal["development", "production", "test"] = "development"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"

    # Authentication (optional gate; set AUTH_REQUIRED=true for production)
    AUTH_REQUIRED: bool = False
    STUDIO_USERNAME: str = "admin"
    STUDIO_PASSWORD: str = "studio-local"
    AUTH_SECRET: str = "dev-local-studio-secret-key"

    # Database (SQLite async default for local dev; PostgreSQL/Supabase for production)
    DATABASE_URL: str = "sqlite+aiosqlite:///./storage/ai_video_studio.db"

    # Redis & Celery
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    CELERY_BROKER_URL: str = "redis://127.0.0.1:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://127.0.0.1:6379/1"

    # Storage & Disk Guard
    STORAGE_ROOT: Path = Path("../storage")
    MAX_MODEL_STORAGE_GB: float = 120.0
    MIN_FREE_DISK_GB: float = 40.0

    # Video Specification (Vertical 9:16, Top/Bottom 50/50)
    OUTPUT_WIDTH: int = 1080
    OUTPUT_HEIGHT: int = 1920
    TOP_VISUAL_HEIGHT: int = 960
    BOTTOM_AVATAR_HEIGHT: int = 960
    TARGET_FPS: int = 30
    DEFAULT_DURATION_SEC: int = 120

    # Hardware & Cross-Process GPU Lock
    COMPUTE_MODE: Literal["local_hybrid", "local_only", "cloud_preferred"] = "local_hybrid"
    LOCAL_VRAM_LIMIT_MB: int = 5800
    GPU_LOCK_TTL_SEC: int = 600
    GPU_LOCK_TIMEOUT_SEC: int = 120

    # Engine Defaults
    COMFYUI_URL: str = "http://127.0.0.1:8188"
    TTS_ENGINE: str = "kokoro"
    AUDIO_EXECUTION_DEVICE: Literal["cpu", "cuda", "auto"] = "cpu"
    KOKORO_MODEL_FILENAME: str = "kokoro-v1.0.onnx"
    KOKORO_VOICES_FILENAME: str = "voices-v1.0.bin"
    ASR_ENGINE: str = "faster-whisper"
    ASR_MODEL_SIZE: str = "base.en"
    ASR_COMPUTE_TYPE: str = "int8"
    AVATAR_ENGINE: str = "ditto"
    VISUAL_ENGINE: str = "hybrid_slide_sdxl_turbo"

    # Optional Cloud GPU Backend (Server-Side Only)
    CLOUD_GPU_PROVIDER: str = "none"
    CLOUD_GPU_API_KEY: str = ""
    CLOUD_GPU_ENDPOINT: str = ""
    CLOUD_AVATAR_ENGINE: str = "echomimic_v2"

    # Google Veo / Video Generation API (Server-Side Only)
    GEMINI_API_KEY: str = ""
    VEO_DEFAULT_MODEL: str = "veo-3.1-lite-generate-preview"

    @property
    def resolved_storage_root(self) -> Path:
        if self.STORAGE_ROOT.is_absolute():
            return self.STORAGE_ROOT
        project_root = Path(__file__).resolve().parents[3]
        return (project_root / "storage").resolve()

    @property
    def resolved_database_url(self) -> str:
        if self.DATABASE_URL.startswith("sqlite") and "ai_video_studio.db" in self.DATABASE_URL:
            db_path = (self.resolved_storage_root / "ai_video_studio.db").as_posix()
            if self.DATABASE_URL.startswith("sqlite+aiosqlite"):
                return f"sqlite+aiosqlite:///{db_path}"
            return f"sqlite:///{db_path}"
        return self.DATABASE_URL


settings = Settings()
