import os
import re
import uuid
import logging
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("news_bot")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def extract_video_id(url: str) -> Optional[str]:
    """Extrae el ID único del video desde una URL."""
    patterns = [
        r"status/(\d+)",
        r"watch\?v=([a-zA-Z0-9_-]+)",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]+)",
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
    if not video_id:
        video_id = extract_video_id(url) or str(uuid.uuid4())

    if output_dir is None:
        output_dir = CACHE_DIR
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, f"{video_id}.mp4")

    if os.path.exists(output_path):
        logger.info(f"[VIDEO] Video ya en caché: {output_path}")
        return output_path

    try:
        import yt_dlp

        ydl_opts = {
            "outtmpl": output_path,
            "format": "best",
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "extractor_retries": 3,
            "fragment_retries": 3,
            "skip_download": False,
            "http_chunk_size": 10485760,
        }
        logger.info(f"[VIDEO] Descargando: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if os.path.exists(output_path):
            logger.info(f"[VIDEO] ✅ Descargado: {output_path}")
            return output_path
        else:
            logger.error(f"[VIDEO] Video no encontrado tras descarga: {output_path}")
            return None
    except Exception as e:
        logger.error(f"[VIDEO] Error descargando {url}: {e}")
        return None


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
