from contextlib import contextmanager
from pathlib import Path
import time
import uuid
from typing import Iterator, Optional

import portalocker
import redis

from app.core.config import settings
from app.core.logging import logger
from app.core.vram import VRAMMonitor


class GPULockTimeoutError(RuntimeError):
    """Raised when the cross-process GPU lock cannot be acquired within timeout."""


class CrossProcessGPULock:
    """
    Cross-process GPU mutex combining:
    1. OS-level file lock (portalocker) across all local Python/worker/CLI processes.
    2. Redis distributed lock (SET NX EX) when Redis is reachable.
    Automatically unloads models on release so VRAM is clean for the next stage.
    """

    LOCK_KEY = "ai_video_studio:gpu_mutex"
    _RELEASE_LUA = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """

    def __init__(
        self,
        lock_file: Optional[Path] = None,
        ttl_sec: Optional[int] = None,
        timeout_sec: Optional[int] = None,
    ) -> None:
        inter_dir = settings.resolved_storage_root / "intermediate"
        inter_dir.mkdir(parents=True, exist_ok=True)
        self.lock_file = lock_file or (inter_dir / ".gpu.lock")
        self.ttl_sec = ttl_sec or settings.GPU_LOCK_TTL_SEC
        self.timeout_sec = timeout_sec or settings.GPU_LOCK_TIMEOUT_SEC

    def _get_redis(self) -> Optional[redis.Redis]:
        try:
            client = redis.Redis.from_url(
                settings.REDIS_URL, socket_timeout=1.0, socket_connect_timeout=1.0
            )
            client.ping()
            return client
        except Exception:
            return None

    @contextmanager
    def acquire(self, owner: str = "worker") -> Iterator[None]:
        token = f"{owner}:{uuid.uuid4()}"
        deadline = time.monotonic() + self.timeout_sec
        redis_client = self._get_redis()
        redis_acquired = False

        # 1. Acquire OS-level cross-process file lock
        file_lock = portalocker.Lock(
            str(self.lock_file),
            mode="a+",
            timeout=self.timeout_sec,
        )
        try:
            file_lock.acquire()
        except portalocker.exceptions.LockException as exc:
            raise GPULockTimeoutError(
                f"Timed out waiting for OS GPU lock ({self.lock_file})"
            ) from exc

        try:
            # 2. Acquire Redis distributed lock if Redis is online
            if redis_client is not None:
                while time.monotonic() < deadline:
                    if redis_client.set(self.LOCK_KEY, token, nx=True, ex=self.ttl_sec):
                        redis_acquired = True
                        break
                    time.sleep(0.25)
                if not redis_acquired:
                    raise GPULockTimeoutError(
                        "Timed out waiting for Redis distributed GPU lock."
                    )

            logger.info("Acquired cross-process GPU lock (%s)", token)
            yield
        finally:
            try:
                VRAMMonitor.unload_models()
            finally:
                if redis_client is not None and redis_acquired:
                    try:
                        redis_client.eval(self._RELEASE_LUA, 1, self.LOCK_KEY, token)
                    except Exception as exc:
                        logger.warning("Failed to release Redis GPU lock: %s", exc)
                file_lock.release()
                logger.info("Released cross-process GPU lock (%s)", token)
