"""
Video Transcriber using Groq Whisper API.

Reemplaza el modelo local Whisper por Groq API para transcripción.
Uso del servicio HTTP ffmpeg para extracción de audio (MP3 comprimido).
"""

import os
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

from config.settings import Settings
from config.logging_config import get_logger
from src.shared.adapters.audio_converter import AudioConverter

load_dotenv(override=True)

logger = get_logger("video_bot.infra.transcriber")

# Instancia global del conversor (inyección de dependencia)
_audio_converter = AudioConverter()


def _send_to_groq(audio_path: str) -> str:
    """Send audio file (MP3, WAV, etc.) to Groq Whisper API."""
    api_key = Settings.GROQ_API_KEY
    if not api_key:
        raise RuntimeError("GROQ_API_KEY no configurada en .env")

    # Determinar MIME type por extensión
    ext = Path(audio_path).suffix.lower()
    mime_map = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")

    with open(audio_path, "rb") as f:
        resp = requests.post(
            Settings.GROQ_API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            data={
                "model": Settings.GROQ_TRANSCRIBE_MODEL,
                "language": "es",
                "response_format": "text",
            },
            files={"file": (os.path.basename(audio_path), f, mime_type)},
            timeout=600,
        )

    resp.raise_for_status()

    # When response_format="text", Groq returns plain text, not JSON
    content_type = resp.headers.get("content-type", "")
    try:
        if "application/json" in content_type:
            result = resp.json()
            text = result.get("text", "").strip()
        else:
            # Plain text response
            text = resp.text.strip()
    except (ValueError, KeyError) as e:
        logger.error(f"[TRANSCRIBER] Error parsing Groq response: {e}")
        logger.debug(f"[TRANSCRIBER] Response content-type: {content_type}")
        logger.debug(
            f"[TRANSCRIBER] Response body (first 500 chars): {resp.text[:500]}"
        )
        raise RuntimeError(f"Failed to parse Groq response: {e}")

    if not text:
        logger.warning("[TRANSCRIBER] Transcripción vacía")
        return ""

    return text


def transcribe_video(video_path: str) -> str:
    """Transcribe un video usando Groq Whisper API."""
    import time

    step_start = time.time()

    logger.info(f"Transcription started: {os.path.basename(video_path)}")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video no encontrado: {video_path}")

    mp3_path = None
    try:
        # Paso único: Convertir video a MP3 (baja calidad) y enviar a Groq
        logger.info("[TRANSCRIBER] Extrayendo audio como MP3 (64k)...")
        mp3_path = _audio_converter.convert_to_mp3(
            input_path=video_path,
            bitrate="64k",  # Comprime para reducir tamaño
            delete_original=False,
        )
        if not mp3_path:
            raise RuntimeError("[TRANSCRIBER] Falló la extracción de audio a MP3")

        mp3_size = os.path.getsize(mp3_path) / (1024 * 1024)
        logger.info(
            f"[TRANSCRIBER] MP3 generado: {os.path.basename(mp3_path)} ({mp3_size:.1f} MB)"
        )

        # Enviar MP3 directamente a Groq (sin conversión a WAV)
        logger.info("[TRANSCRIBER] Enviando MP3 a Groq...")
        text = _send_to_groq(mp3_path)
        elapsed = time.time() - step_start

        logger.info(
            f"Transcription completed in {elapsed:.1f}s: {len(text)} characters"
        )

        if not text or len(text) < 50:
            logger.warning("Transcription result is very short (< 50 chars)")

        return text

    except requests.HTTPError as e:
        error_detail = e.response.text if hasattr(e, "response") else str(e)
        logger.error(f"Groq API HTTP error: {error_detail}")
        raise RuntimeError(f"Groq API error: {error_detail}")
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise
    finally:
        # Limpiar archivo temporal MP3
        if mp3_path and os.path.exists(mp3_path):
            try:
                os.unlink(mp3_path)
            except OSError:
                pass


class VideoTranscriber:
    """Transcriptor de videos usando Groq."""

    def __init__(self, model: str = "whisper-large-v3-turbo"):
        self.model = model

    def transcribe(self, video_path: str) -> str:
        """Transcribe un video."""
        return transcribe_video(video_path)


def run(video_path: str) -> str:
    """Función principal."""
    return transcribe_video(video_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        result = transcribe_video(sys.argv[1])
        print(f"✅ {len(result)} caracteres")
    else:
        print("Usage: python video_transcriber.py <video_file>")
