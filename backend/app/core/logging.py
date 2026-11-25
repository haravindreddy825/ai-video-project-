import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure structured console and rotating file logging."""
    logger = logging.getLogger("ai_video_studio")
    if logger.handlers:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    try:
        log_dir: Path = settings.resolved_storage_root
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "backend.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        pass

    return logger


logger = setup_logging()
