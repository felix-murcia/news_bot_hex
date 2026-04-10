import os
import re
import uuid
import logging
import subprocess
import json
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("audio_bot")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

MAX_DURATION = 600


def extract_audio_id(url: str) -> Optional[str]:
    """Extrae el ID único del audio desde una URL."""
    patterns = [
        r"/audios/.*/(\d+)/",
        r"watch\?v=([a-zA-Z0-9_-]+)",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]+)",
        r"podcasts\.apple\.com/.*?/id(\d+)",
        r"spotify\.com/.*?/episode/([a-zA-Z0-9]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_audio_duration(path: str) -> float:
    """Devuelve la duración en segundos usando ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


def is_direct_audio_url(url: str) -> bool:
    """Detecta si la URL es directamente un archivo de audio."""
    audio_extensions = [".mp3", ".m4a", ".wav", ".ogg", ".aac", ".flac", ".wma"]
    url_lower = url.lower()
    return any(
        url_lower.endswith(ext) or f"{ext}?" in url_lower for ext in audio_extensions
    )


def _is_rtve_url(url: str) -> bool:
    """Detecta si es una URL de RTVE (que requiere manejo especial)."""
    return "rtve.es" in url.lower()


def _download_direct(url: str, output_dir: str, audio_id: str) -> Optional[str]:
    """Descarga directa usando requests para URLs de audio."""
    import requests

    output_path = os.path.join(output_dir, f"{audio_id}.mp3")

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "audio/mpeg, audio/*,*/*",
            "Accept-Language": "es-ES,es;q=0.9",
            "Referer": "https://www.rtve.es/",
        }
        logger.info(f"[AUDIO] Descarga directa: {url[:80]}...")
        response = requests.get(url, headers=headers, timeout=60, stream=True)
        
        # Manejar específicamente errores de token expirado
        if response.status_code in (400, 401, 403, 410):
            logger.warning(f"[AUDIO] Error {response.status_code} - Token probablemente expirado")
            return None
            
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
            logger.info(f"[AUDIO] ✅ Descarga directa completada: {output_path}")
            return output_path
        else:
            logger.error(f"[AUDIO] Archivo vacío o no encontrado tras descarga directa")
            if os.path.exists(output_path):
                os.remove(output_path)
            return None

    except requests.exceptions.HTTPError as e:
        if e.response.status_code in (400, 401, 403, 410):
            logger.warning(f"[AUDIO] HTTP {e.response.status_code} - Token expirado, se usará yt-dlp")
        else:
            logger.error(f"[AUDIO] Error HTTP en descarga directa: {e}")
        return None
    except Exception as e:
        logger.error(f"[AUDIO] Error en descarga directa: {e}")
        return None


def _download_with_ytdlp(
    url: str, output_dir: str, audio_id: str, max_duration: int
) -> Optional[str]:
    """Descarga usando yt-dlp como método principal (no fallback)."""
    import yt_dlp

    output_path = os.path.join(output_dir, f"{audio_id}.mp3")
    
    # Si ya existe en caché, devolverlo
    if os.path.exists(output_path):
        logger.info(f"[AUDIO] Audio ya existe: {output_path}")
        return output_path
    
    outtmpl = os.path.join(output_dir, f"{audio_id}.%(ext)s")

    ydl_opts = {
        "outtmpl": outtmpl,
        "format": "bestaudio/best",
        "quiet": False,  # Cambiar a False para debug, True en producción
        "no_warnings": False,
        "extractor_retries": 5,
        "fragment_retries": 5,
        "ignoreerrors": False,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "headers": {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Accept-Language": "es-ES,es;q=0.9",
            "Referer": "https://www.rtve.es/",
        },
    }

    try:
        logger.info(f"[AUDIO] Descargando con yt-dlp: {url[:80]}...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Verificar archivo MP3
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
            logger.info(f"[AUDIO] ✅ Descarga yt-dlp exitosa: {output_path}")
            return output_path

        # Buscar otros formatos
        for ext in [".m4a", ".webm", ".wav", ".ogg", ".opus"]:
            alt_path = os.path.join(output_dir, f"{audio_id}{ext}")
            if os.path.exists(alt_path) and os.path.getsize(alt_path) > 1024:
                # Intentar convertir a MP3
                try:
                    mp3_path = os.path.join(output_dir, f"{audio_id}.mp3")
                    subprocess.run([
                        'ffmpeg', '-i', alt_path, '-acodec', 'libmp3lame',
                        '-ab', '192k', '-y', mp3_path
                    ], capture_output=True, check=True, timeout=120)
                    os.remove(alt_path)
                    logger.info(f"[AUDIO] ✅ Convertido a MP3: {mp3_path}")
                    return mp3_path
                except Exception as conv_err:
                    logger.warning(f"[AUDIO] No se pudo convertir a MP3: {conv_err}")
                    return alt_path

        logger.error(f"[AUDIO] No se encontró archivo descargado para {audio_id}")
        return None
        
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "400" in error_msg or "410" in error_msg or "Token incorrect" in error_msg:
            logger.error(f"[AUDIO] Token expirado o URL inválida. Error: {e}")
        else:
            logger.error(f"[AUDIO] Error en yt-dlp: {e}")
        return None
    except Exception as e:
        logger.error(f"[AUDIO] Error inesperado en yt-dlp: {e}")
        return None


def download_audio(
    url: str,
    output_dir: str = None,
    audio_id: str = None,
    max_duration: int = MAX_DURATION,
) -> Optional[str]:
    """Descarga el audio desde la URL."""
    if not audio_id:
        audio_id = extract_audio_id(url) or str(uuid.uuid4())

    if output_dir is None:
        output_dir = CACHE_DIR
    os.makedirs(output_dir, exist_ok=True)

    output_path_mp3 = os.path.join(output_dir, f"{audio_id}.mp3")

    # Verificar caché
    if os.path.exists(output_path_mp3):
        logger.info(f"[AUDIO] Audio ya en caché: {output_path_mp3}")
        return output_path_mp3

    # ============================================================
    # CASO 1: URL directa de audio (ej: https://ejemplo.com/audio.mp3)
    # ============================================================
    if is_direct_audio_url(url):
        logger.info(f"[AUDIO] URL directa de audio detectada")
        # Para URLs directas, intentar descarga directa primero
        result = _download_direct(url, output_dir, audio_id)
        if result:
            return result
        # Si falla, intentar con yt-dlp
        logger.warning(f"[AUDIO] Descarga directa falló, intentando con yt-dlp...")
        return _download_with_ytdlp(url, output_dir, audio_id, max_duration)

    # ============================================================
    # CASO 2: URL de página (YouTube, RTVE, podcast, etc.)
    # ============================================================
    
    # Para RTVE, ir directamente a yt-dlp (evita problemas de tokens)
    if _is_rtve_url(url):
        logger.info(f"[AUDIO] URL de RTVE detectada, usando yt-dlp directamente")
        return _download_with_ytdlp(url, output_dir, audio_id, max_duration)
    
    # Para otras plataformas, intentar extraer URL de audio primero
    try:
        import yt_dlp

        ydl_opts_info = {
            "quiet": True,
            "no_warnings": True,
            "extractor_retries": 3,
            "format": "bestaudio/best",
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as info_err:
            logger.warning(f"[AUDIO] Error extrayendo info: {info_err}")
            info = None

        if info:
            duration = info.get("duration")
            if duration and duration > max_duration:
                raise ValueError(
                    f"El audio dura {duration / 60:.1f} minutos, supera el límite de {max_duration / 60} minutos."
                )

            # Para URLs que no son de RTVE, podemos intentar extraer la URL directa
            # y descargar con requests (más rápido)
            if not _is_rtve_url(url):
                formats = info.get("formats", [])
                audio_formats = [
                    f for f in formats if f.get("vcodec") == "none" and f.get("acodec")
                ]

                if audio_formats:
                    best_audio = audio_formats[0]
                    url_to_download = best_audio.get("url")
                    if url_to_download:
                        logger.info(f"[AUDIO] Audio encontrado, descargando directamente...")
                        result = _download_direct(url_to_download, output_dir, audio_id)
                        if result:
                            return result
                        logger.warning("[AUDIO] Descarga directa de URL extraída falló")

    except Exception as e:
        logger.warning(f"[AUDIO] Error en extracción de metadata: {e}")

    # Fallback final: usar yt-dlp para la descarga completa
    return _download_with_ytdlp(url, output_dir, audio_id, max_duration)


def has_audio_stream(audio_path: str) -> bool:
    """Verifica si el archivo tiene flujo de audio válido."""
    if not audio_path or not os.path.exists(audio_path):
        return False
    
    if os.path.getsize(audio_path) < 1024:
        return False
        
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return "audio" in result.stdout.lower()
    except Exception:
        # Si ffprobe falla, asumir que es válido si tiene tamaño
        return os.path.getsize(audio_path) > 10240


def transcribe_audio(audio_path: str) -> str:
    """Transcribe un archivo de audio usando Whisper."""
    logger.info(f"[AUDIO] Transcribiendo: {audio_path}")

    try:
        import whisper

        model = whisper.load_model("tiny", device="cpu")
        result = model.transcribe(audio_path, language=None, task="transcribe")
        return result["text"].strip()
    except Exception as e:
        logger.error(f"[AUDIO] Error transcribiendo: {e}")
        raise


class AudioFetcher:
    """Fetcher para archivos de audio."""

    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir or CACHE_DIR

    def fetch(self, url: str, audio_id: str = None) -> Optional[str]:
        """Descarga un audio desde URL."""
        return download_audio(url, self.cache_dir, audio_id)

    def transcribe(self, audio_path: str) -> str:
        """Transcribe un audio."""
        return transcribe_audio(audio_path)


def run(url: str, output_dir: str = None) -> Optional[str]:
    """Función principal."""
    return download_audio(url, output_dir)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        result = run(sys.argv[1])
        print(f"Resultado: {result}")