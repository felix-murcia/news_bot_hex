import os
import re
import uuid
import json
from typing import Optional, Dict, Any

import yt_dlp
import requests
from config.logging_config import get_logger
from config.settings import Settings
from src.shared.adapters.audio_converter import AudioConverter

logger = get_logger("audio_bot.infra.fetcher")

CACHE_DIR = Settings.CACHE_DIR
os.makedirs(CACHE_DIR, exist_ok=True)

MAX_DURATION = 600

# Instancia global del conversor de audio (inyección de dependencia)
_audio_converter = AudioConverter()


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
        }
        logger.info(f"[AUDIO] Descarga directa: {url[:80]}...")

        # HEAD request primero para validar Content-Type
        head_resp = requests.head(
            url, headers=headers, timeout=15, allow_redirects=True
        )
        if head_resp.status_code in (200, 206):
            content_type = head_resp.headers.get("Content-Type", "").lower()
            # Si claramente no es audio, abortar inmediatamente
            if any(
                ct in content_type
                for ct in ("text/html", "text/plain", "application/json")
            ):
                logger.warning(f"[AUDIO] Content-Type no es audio: {content_type[:60]}")
                return None
            # Si es audio, extraer extensión correcta
            if "mpeg" in content_type or "mp3" in content_type:
                output_path = os.path.join(output_dir, f"{audio_id}.mp3")
            elif "mp4" in content_type or "m4a" in content_type:
                output_path = os.path.join(output_dir, f"{audio_id}.m4a")

        response = requests.get(url, headers=headers, timeout=120, stream=True)

        if response.status_code in (400, 401, 403, 410):
            logger.warning(
                f"[AUDIO] Error {response.status_code} - Token expirado o no autorizado"
            )
            return None

        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Validar tamaño mínimo (1MB = al menos ~1 min de audio)
        min_size = 500 * 1024  # 500KB mínimo
        if os.path.exists(output_path) and os.path.getsize(output_path) > min_size:
            logger.info(f"[AUDIO] ✅ Descarga directa completada: {output_path}")
            return output_path
        else:
            actual_size = (
                os.path.getsize(output_path) if os.path.exists(output_path) else 0
            )
            logger.warning(
                f"[AUDIO] Archivo demasiado pequeño ({actual_size} bytes < {min_size} bytes)"
            )
            if os.path.exists(output_path):
                os.remove(output_path)
            return None

    except requests.exceptions.HTTPError as e:
        if e.response.status_code in (400, 401, 403, 410):
            logger.warning(f"[AUDIO] HTTP {e.response.status_code} - No autorizado")
        return None
    except Exception as e:
        logger.error(f"[AUDIO] Error en descarga directa: {e}")
        return None


def _download_with_ytdlp(
    url: str, output_dir: str, audio_id: str, max_duration: int
) -> Optional[str]:
    """Descarga usando yt-dlp y convierte a MP3 mediante servicio HTTP."""
    import yt_dlp
    from src.shared.adapters.audio_converter import AudioConverter

    # Inicializar conversor
    converter = AudioConverter()

    outtmpl = os.path.join(output_dir, f"{audio_id}.%(ext)s")

    ydl_opts: Dict[str, Any] = {
        "outtmpl": outtmpl,
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "extractor_retries": 3,
        "fragment_retries": 3,
        "ignoreerrors": False,
        # Sin postprocessors - la conversión la haremos después con AudioConverter
        "postprocessors": [],
        "headers": {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Accept-Language": "es-ES,es;q=0.9",
            "Referer": "https://www.rtve.es/",
        },
    }

    try:
        logger.info(f"[AUDIO] Descargando con yt-dlp: {url[:80]}...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[arg-type]
            ydl.download([url])

        # Encontrar archivo descargado (cualquier extensión de audio)
        downloaded_path = None
        audio_extensions = [".webm", ".m4a", ".mp3", ".ogg", ".opus", ".wav", ".flac"]
        for ext in audio_extensions:
            path = os.path.join(output_dir, f"{audio_id}{ext}")
            if os.path.exists(path) and os.path.getsize(path) > 1024:
                downloaded_path = path
                logger.info(f"[AUDIO] Archivo descargado: {os.path.basename(path)}")
                break

        if not downloaded_path:
            logger.error(f"[AUDIO] No se encontró archivo descargado para {audio_id}")
            return None

        # Si ya es MP3, renombrar a la ruta final y devolver
        if downloaded_path.endswith(".mp3"):
            final_path = os.path.join(output_dir, f"{audio_id}.mp3")
            if downloaded_path != final_path:
                os.rename(downloaded_path, final_path)
            logger.info(f"[AUDIO] ✅ Descarga yt-dlp exitosa (MP3): {final_path}")
            return final_path

        # Convertir a MP3 usando AudioConverter (endpoint HTTP ffmpeg)
        mp3_path = os.path.join(output_dir, f"{audio_id}.mp3")
        logger.info(
            f"[AUDIO] Convirtiendo {os.path.basename(downloaded_path)} → MP3..."
        )

        converted = converter.convert_to_mp3(
            input_path=downloaded_path,
            output_path=mp3_path,
        )

        if converted and os.path.exists(converted):
            # Eliminar archivo original descargado
            try:
                os.remove(downloaded_path)
            except Exception:
                pass
            logger.info(f"[AUDIO] ✅ Conversión a MP3 exitosa: {converted}")
            return converted
        else:
            logger.error("[AUDIO] Falló la conversión a MP3")
            # Eliminar archivo original por limpieza
            try:
                os.remove(downloaded_path)
            except Exception:
                pass
            return None

    except Exception as e:
        logger.error(f"[AUDIO] Error en yt-dlp: {e}")
        return None


def download_audio(
    url: str,
    output_dir: Optional[str] = None,
    audio_id: Optional[str] = None,
    max_duration: int = MAX_DURATION,
) -> Optional[str]:
    """Descarga el audio desde cualquier tipo de URL.

    Estrategia genérica:
    1. Descarga directa con requests (funciona para URLs directas, CDN con tokens, etc.)
    2. Si falla o el archivo no es válido, intenta yt-dlp
    3. Valida siempre que el resultado sea un audio real
    """
    import time

    step_start = time.time()

    if not audio_id:
        audio_id = extract_audio_id(url) or str(uuid.uuid4())

    if output_dir is None:
        output_dir = CACHE_DIR
    os.makedirs(output_dir, exist_ok=True)

    output_path_mp3 = os.path.join(output_dir, f"{audio_id}.mp3")

    # Verificar caché válido
    if os.path.exists(output_path_mp3):
        if os.path.getsize(
            output_path_mp3
        ) > 1024 and _audio_converter.has_audio_stream(output_path_mp3):
            logger.info(f"Audio cache hit: {os.path.basename(output_path_mp3)}")
            return output_path_mp3
        else:
            logger.warning(f"Caché inválido, eliminando: {output_path_mp3}")
            os.remove(output_path_mp3)

    logger.info(f"Audio download started: {url[:80]}...")

    # ============================================================
    # ESTRATEGIA 1: Descarga directa con requests
    # Funciona para URLs directas (.mp3, .m4a), CDN con tokens, etc.
    # ============================================================
    result = _download_direct(url, output_dir, audio_id)
    if result and _audio_converter.has_audio_stream(result):
        logger.info(f"Direct download completed in {time.time() - step_start:.1f}s")
        return result

    if result:
        logger.warning("Downloaded file is not valid audio, cleaning up")
        try:
            os.remove(result)
        except OSError:
            pass

    # ============================================================
    # ESTRATEGIA 2: yt-dlp (para YouTube, podcasts, páginas web)
    # ============================================================
    logger.info("Direct download failed, trying yt-dlp...")
    result = _download_with_ytdlp(url, output_dir, audio_id, max_duration)
    if result and _audio_converter.has_audio_stream(result):
        logger.info(f"yt-dlp download completed in {time.time() - step_start:.1f}s")
        return result

    if result:
        logger.warning("yt-dlp downloaded invalid file")
        try:
            os.remove(result)
        except OSError:
            pass

    logger.error(f"Audio download failed: {url}")
    return None


def transcribe_audio(audio_path: str) -> str:
    """Transcribe un archivo de audio usando Groq Whisper API."""
    from src.audio.infrastructure.adapters.audio_transcriber import (
        transcribe_audio as _transcribe,
    )

    return _transcribe(audio_path)


class AudioFetcher:
    """Fetcher para archivos de audio."""

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir or CACHE_DIR

    def fetch(self, url: str, audio_id: Optional[str] = None) -> Optional[str]:
        """Descarga un audio desde URL."""
        return download_audio(url, self.cache_dir, audio_id)

    def transcribe(self, audio_path: str) -> str:
        """Transcribe un audio."""
        return transcribe_audio(audio_path)


def run(url: str, output_dir: Optional[str] = None) -> Optional[str]:
    """Función principal."""
    return download_audio(url, output_dir)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        result = run(sys.argv[1])
        print(f"Resultado: {result}")
