"""
Audio Transcriber using Groq Whisper API.

Reemplaza el modelo local Whisper por Groq API para transcripción.
Uso del servicio HTTP ffmpeg para conversión a MP3 comprimido.
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

logger = get_logger("audio_bot.infra.transcriber")

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

    file_size = os.path.getsize(audio_path)
    logger.info(f"[TRANSCRIBER] Enviando a Groq: {file_size / 1024 / 1024:.1f} MB")

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

    # Log raw response for debugging
    logger.info(f"[TRANSCRIBER] Groq HTTP {resp.status_code}")

    if resp.status_code != 200:
        error_text = resp.text[:500] if resp.text else "No response body"
        logger.error(f"[TRANSCRIBER] Groq error response: {error_text}")
        raise RuntimeError(f"Groq API returned {resp.status_code}: {error_text[:200]}")

    # Groq con response_format="text" devuelve texto plano, no JSON
    content_type = resp.headers.get("Content-Type", "")
    if "application/json" in content_type:
        result = resp.json()
        text = result.get("text", "").strip()
    else:
        # Texto plano directo
        text = resp.text.strip()

    if not text:
        logger.warning("[TRANSCRIBER] Transcripción vacía")
        return ""

    return text


def transcribe_audio(audio_path: str) -> str:
    """Transcribe un archivo de audio usando Groq Whisper API."""
    import time

    step_start = time.time()

    logger.info(f"Transcription started: {os.path.basename(audio_path)}")

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio no encontrado: {audio_path}")

    mp3_path = None
    try:
        # Paso único: Convertir a MP3 comprimido (64k) y enviar a Groq directamente
        logger.info("[TRANSCRIBER] Convirtiendo a MP3 (64k)...")
        mp3_path = _audio_converter.convert_to_mp3(
            input_path=audio_path,
            bitrate="64k",
            delete_original=False,
        )
        if not mp3_path:
            raise RuntimeError("[TRANSCRIBER] Falló la conversión a MP3")

        mp3_size = os.path.getsize(mp3_path) / (1024 * 1024)
        logger.info(
            f"[TRANSCRIBER] MP3 generado: {os.path.basename(mp3_path)} ({mp3_size:.1f} MB)"
        )

        # Enviar MP3 directamente a Groq (sin WAV intermedio)
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


class AudioTranscriber:
    """Transcriptor de audios usando Groq."""

    def __init__(self, model: str = "whisper-large-v3-turbo"):
        self.model = model

    def transcribe(self, audio_path: str) -> str:
        """Transcribe un audio."""
        return transcribe_audio(audio_path)


def run(audio_path: str) -> str:
    """Función principal."""
    return transcribe_audio(audio_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        result = transcribe_audio(sys.argv[1])
        print(f"✅ {len(result)} caracteres")
    else:
        print("Usage: python audio_transcriber.py <audio_file>")
