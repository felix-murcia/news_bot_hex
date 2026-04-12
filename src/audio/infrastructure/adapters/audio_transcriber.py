"""
Audio Transcriber using Groq Whisper API.

Reemplaza el modelo local Whisper por Groq API para transcripción.
"""

import os
import logging
import tempfile
import subprocess
from typing import Optional

import requests
from dotenv import load_dotenv

from config.settings import Settings
from src.logging_config import get_logger

load_dotenv()

logger = get_logger("audio_bot.infra.transcriber")


def _convert_to_wav(input_path: str) -> str:
    """Convert audio to 16kHz mono WAV for Groq API."""
    output_path = tempfile.mktemp(suffix=".wav")
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", input_path,
                "-ar", "16000",
                "-ac", "1",
                "-f", "wav",
                output_path,
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        size = os.path.getsize(output_path)
        logger.info(f"[TRANSCRIBER] Audio convertido a WAV: {size} bytes")
        return output_path
    except subprocess.CalledProcessError as e:
        logger.error(f"[TRANSCRIBER] FFmpeg falló: {e.stderr.decode()}")
        raise RuntimeError(f"FFmpeg failed: {e}")
    except FileNotFoundError:
        logger.error("[TRANSCRIBER] ffmpeg no encontrado en PATH")
        raise RuntimeError("ffmpeg es requerido para conversión de audio")


def _send_to_groq(wav_path: str) -> str:
    """Send WAV file to Groq Whisper API."""
    api_key = Settings.GROQ_API_KEY
    if not api_key:
        raise RuntimeError("GROQ_API_KEY no configurada en .env")

    with open(wav_path, "rb") as f:
        resp = requests.post(
            Settings.GROQ_API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            data={
                "model": Settings.GROQ_TRANSCRIBE_MODEL,
                "language": "es",
                "response_format": "text",
            },
            files={"file": ("audio.wav", f, "audio/wav")},
            timeout=300,
        )

    resp.raise_for_status()
    result = resp.json()
    text = result.get("text", "").strip()

    if not text:
        logger.warning("[TRANSCRIBER] Transcripción vacía")
        return ""

    return text


def transcribe_audio(audio_path: str) -> str:
    """Transcribe un audio usando Groq Whisper API."""
    import time
    step_start = time.time()

    logger.info(f"Transcription started: {os.path.basename(audio_path)}")

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio no encontrado: {audio_path}")

    wav_path = None
    try:
        wav_path = _convert_to_wav(audio_path)
        text = _send_to_groq(wav_path)
        elapsed = time.time() - step_start

        logger.info(f"Transcription completed in {elapsed:.1f}s: {len(text)} characters")

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
        if wav_path and os.path.exists(wav_path):
            try:
                os.unlink(wav_path)
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
