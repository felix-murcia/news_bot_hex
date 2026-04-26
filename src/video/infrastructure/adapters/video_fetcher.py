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
    """Find the downloaded file after yt-dlp processing."""
    # Priorizar MP3 generado por postprocesador
    mp3_path = os.path.join(output_dir, f"{video_id}.mp3")
    if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 1024:
        return mp3_path

    # Buscar cualquier archivo con el video_id (por si yt-dlp usa otra extensión)
    for name in os.listdir(output_dir):
        if name.startswith(video_id) and name != f"{video_id}.%(ext)s":
            path = os.path.join(output_dir, name)
            if os.path.isfile(path) and os.path.getsize(path) > 1024:
                return path

    return None


def download_mp3(
    url: str, output_dir: str = None, video_id: str = None
) -> Optional[str]:
    """Descarga el audio del video y lo convierte a MP3 usando yt-dlp + AudioConverter."""
    import time

    if not video_id:
        video_id = extract_video_id(url) or str(uuid.uuid4())

    if output_dir is None:
        output_dir = CACHE_DIR
    os.makedirs(output_dir, exist_ok=True)

    # Audio final en MP3
    final_mp3 = os.path.join(output_dir, f"{video_id}.mp3")

    # Check cache
    if os.path.exists(final_mp3):
        logger.info(f"Audio MP3 cache hit: {video_id}.mp3")
        return final_mp3

    step_start = time.time()
    logger.info(f"Audio download started: {url[:80]}...")

    # Paso 1: Descargar el mejor audio disponible (sin convertir)
    output_template = os.path.join(output_dir, f"{video_id}.%(ext)s")
    ydl_opts = {
        "outtmpl": output_template,
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "extractor_retries": 3,
        "fragment_retries": 3,
        "geo_bypass": True,
    }

    audio_path = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Buscar el archivo de audio descargado
        audio_path = _find_downloaded_file(output_dir, video_id)
        if not audio_path:
            logger.error(f"Audio download failed: no file found")
            return None

        logger.info(
            f"Audio downloaded: {os.path.basename(audio_path)} "
            f"({os.path.getsize(audio_path) / 1024 / 1024:.1f} MB)"
        )

        # Paso 2: Convertir a MP3 usando el servicio de conversión (si no es MP3)
        if audio_path.endswith(".mp3"):
            logger.info(f"Audio already in MP3 format")
            # Renombrar a nombre estandarizado si es necesario
            if audio_path != final_mp3:
                os.rename(audio_path, final_mp3)
                audio_path = final_mp3
            return audio_path
        else:
            logger.info(f"Converting {os.path.basename(audio_path)} → MP3...")
            converter = AudioConverter()
            mp3_path = converter.convert_to_mp3(
                input_path=audio_path,
                output_path=final_mp3,
                bitrate="64k",
                delete_original=True,
            )
            if mp3_path and os.path.exists(mp3_path):
                elapsed = time.time() - step_start
                size_mb = os.path.getsize(mp3_path) / (1024 * 1024)
                logger.info(
                    f"Audio MP3 ready in {elapsed:.1f}s: {os.path.basename(mp3_path)} ({size_mb:.1f} MB)"
                )
                return mp3_path
            else:
                logger.error("Audio MP3 conversion failed")
                return None

    except Exception as e:
        logger.error(f"Audio MP3 download error: {e}")
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
        _cleanup_partial(output_dir, video_id)
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
