import os
import re
import uuid
from typing import Optional

import yt_dlp
from config.logging_config import get_logger
from config.settings import Settings
from src.shared.adapters.audio_converter import AudioConverter

logger = get_logger("video_bot.infra.fetcher")

# Instancia global del conversor (inyección de dependencia)
_audio_converter = AudioConverter()

CACHE_DIR = Settings.CACHE_DIR
os.makedirs(CACHE_DIR, exist_ok=True)


def extract_video_id(url: str) -> Optional[str]:
    """Extrae el ID único del video desde una URL."""
    patterns = [
        r"status/(\d+)",
        r"watch\?v=([a-zA-Z0-9_-]+)",
        r"youtu\.be/([a-zA-Z0-9_-]+)",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]+)",
        r"youtube\.com/embed/([a-zA-Z0-9_-]+)",
        r"youtube\.com/v/([a-zA-Z0-9_-]+)",
        r"tiktok\.com/@[\w]+/video/(\d+)",
        r"instagram\.com/reel/([a-zA-Z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def download_video(
    url: str, output_dir: str = None, video_id: str = None
) -> Optional[str]:
    """Descarga el video desde la URL usando yt_dlp."""
    import time

    if not video_id:
        video_id = extract_video_id(url) or str(uuid.uuid4())

    if output_dir is None:
        output_dir = CACHE_DIR
    os.makedirs(output_dir, exist_ok=True)

    step_start = time.time()

    # Check cache for any file with this video_id and valid audio
    for cached in os.listdir(output_dir):
        if cached.startswith(video_id) and cached != f"{video_id}.mp4":
            cached_path = os.path.join(output_dir, cached)
            if _audio_converter.has_audio_stream(cached_path):
                logger.info(f"Video cache hit: {cached}")
                return cached_path

    output_path = os.path.join(output_dir, f"{video_id}.%(ext)s")

    logger.info(f"Video download started: {url[:80]}...")

    import yt_dlp

    # Try multiple format strategies in order of preference
    format_strategies = [
        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "bestvideo+bestaudio/best",
        "best",
    ]

    last_error = None
    for fmt in format_strategies:
        try:
            ydl_opts = {
                "outtmpl": output_path,
                "format": fmt,
                "quiet": True,
                "no_warnings": True,
                "nocheckcertificate": True,
                "extractor_retries": 3,
                "fragment_retries": 3,
                "skip_download": False,
                "http_chunk_size": 10485760,
                "geo_bypass": True,
                "merge_output_format": "mp4",
                "postprocessors": [
                    {
                        "key": "FFmpegVideoConvertor",
                        "preferedformat": "mp4",
                    }
                ],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Find the actual downloaded file (yt-dlp may produce mp4 or webm)
            downloaded = _find_downloaded_file(output_dir, video_id)
            if downloaded and _audio_converter.has_audio_stream(downloaded):
                elapsed = time.time() - step_start
                size_mb = os.path.getsize(downloaded) / (1024 * 1024)
                logger.info(
                    f"Video downloaded in {elapsed:.1f}s ({fmt}): "
                    f"{os.path.basename(downloaded)} {size_mb:.1f} MB"
                )
                return downloaded
            elif downloaded:
                logger.debug(f"Downloaded file has no audio, cleaning up")
                os.remove(downloaded)
        except Exception as e:
            last_error = e
            logger.debug(f"Format '{fmt}' failed: {e}")
            # Clean up partial downloads
            _cleanup_partial(output_dir, video_id)
            continue

    # All format strategies failed
    logger.error(f"Video download error (all formats failed): {last_error}")
    return None


def _find_downloaded_file(output_dir: str, video_id: str) -> Optional[str]:
    """Find the actual downloaded file, which may have any extension."""
    for name in os.listdir(output_dir):
        if name.startswith(video_id) and name != f"{video_id}.%(ext)s":
            path = os.path.join(output_dir, name)
            if os.path.getsize(path) > 1024:
                return path
    return None


def _cleanup_partial(output_dir: str, video_id: str):
    """Remove partial download files for a given video ID."""
    for name in os.listdir(output_dir):
        if name.startswith(video_id):
            path = os.path.join(output_dir, name)
            try:
                os.remove(path)
            except OSError:
                pass


def get_video_info(url: str) -> Optional[dict]:
    """Obtiene información del video sin descargarlo."""
    try:
        import yt_dlp

        ydl_opts = {"quiet": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "id": info.get("id"),
                "title": info.get("title"),
                "description": info.get("description"),
                "duration": info.get("duration"),
                "uploader": info.get("uploader"),
                "upload_date": info.get("upload_date"),
                "thumbnail": info.get("thumbnail"),
            }
    except Exception as e:
        logger.error(f"[VIDEO] Error obteniendo info de {url}: {e}")
        return None


class VideoFetcher:
    """Fetcher para videos."""

    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir or CACHE_DIR

    def fetch(self, url: str, video_id: str = None) -> Optional[str]:
        """Descarga un video desde URL."""
        return download_video(url, self.cache_dir, video_id)

    def get_info(self, url: str) -> Optional[dict]:
        """Obtiene información del video."""
        return get_video_info(url)


def run(url: str, output_dir: str = None) -> Optional[str]:
    """Función principal."""
    return download_video(url, output_dir)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        result = run(sys.argv[1])
        print(f"Resultado: {result}")
