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
from config.logging_config import get_logger

load_dotenv(override=True)

logger = get_logger("audio_bot.infra.transcriber")


def _convert_to_wav(input_path: str, max_duration: int = 300) -> str:
    """Convert audio to 16kHz mono WAV for Groq API.
    
    Limita la duración para evitar 'Request Entity Too Large'.
    Groq tiene un límite de ~25MB por request (~15 min a 16kHz mono).
    """
    output_path = tempfile.mktemp(suffix=".wav")
    
    # Obtener duración real del audio
    actual_duration = max_duration
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", input_path],
            capture_output=True, text=True, timeout=10,
        )
        import json as _json
        actual_duration = float(_json.loads(probe.stdout)["format"]["duration"])
        actual_duration = min(actual_duration, max_duration)
    except Exception:
        pass
    
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-t", str(int(actual_duration)),
            "-ar", "16000",
            "-ac", "1",
            "-f", "wav",
            output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        size = os.path.getsize(output_path)
        logger.info(f"[TRANSCRIBER] Audio convertido a WAV: {size/1024/1024:.1f}MB ({actual_duration:.0f}s)")
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

    file_size = os.path.getsize(wav_path)
    logger.info(f"[TRANSCRIBER] Enviando a Groq: {file_size/1024/1024:.1f}MB")

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
