"""Centralized logging configuration.

All loggers write to both stdout and file (/app/logs/news_bot.log).
Log files are rotated daily, keeping 7 days of history.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from config.settings import Settings

# Log directory: /app/logs inside Docker, falls back to /tmp/logs on host
log_dir_env = Settings.LOG_DIR or "/app/logs"
LOG_DIR = Path(log_dir_env)
if not LOG_DIR.exists():
    # Fallback for non-Docker environments
    LOG_DIR = Path("/tmp/logs")

LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "news_bot.log"

# Log format: timestamp | level | logger_name | message
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-25s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

MAX_BYTES = 50 * 1024 * 1024  # 50 MB per file
BACKUP_COUNT = 7  # Keep 7 rotated files


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root logger with file and console handlers.

    This should be called once at application startup (server.py, CLI entrypoints).
    Subsequent calls are safe — they only add handlers if not already configured.
    """

    root_logger = logging.getLogger()

    # Avoid adding duplicate handlers on re-import
    if root_logger.handlers:
        return

    root_logger.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # --- File handler (rotating) ---
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        # If we can't write to the log file, fall back to console only
        print(f"WARNING: Cannot write to {LOG_FILE}: {e}", file=sys.stderr)

    # --- Console handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Silence overly verbose third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("yt_dlp").setLevel(logging.WARNING)
    logging.getLogger("feedparser").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name, inheriting from root logger.

    Usage:
        logger = get_logger(__name__)
        # or
        logger = get_logger("news_bot.pipeline")
    """
    return logging.getLogger(name)
