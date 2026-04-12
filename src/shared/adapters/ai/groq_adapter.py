"""
Groq Whisper Adapter (Hexagonal Architecture - Adapter).

Implementation of AIModelPort for Groq Whisper transcription.
Uses Groq's API (OpenAI-compatible) for audio transcription.
"""

import os
import logging
import tempfile
import subprocess
from typing import Dict, Optional

import requests
from dotenv import load_dotenv

from src.shared.utils.retry import retry_with_backoff
from config.settings import Settings

load_dotenv()

logger = logging.getLogger(__name__)


class GroqAdapter:
    """Adapter for Groq Whisper transcription API."""

    def __init__(self, config: Dict = None, validate_on_init: bool = False):
        """Initialize the Groq adapter.

        Args:
            config: Configuration dictionary
            validate_on_init: If True, validates API key on initialization
        """
        self.config = config or {}
        self.api_key = os.getenv("GROQ_API_KEY")
        self.api_url = self.config.get(
            "api_url", Settings.GROQ_API_URL
        )
        self.model = self.config.get(
            "model", Settings.GROQ_TRANSCRIBE_MODEL
        )

        if not self.api_key:
            logger.warning("[GROQ] API key not found in environment")
        else:
            logger.info(f"[GROQ] Initialized with model: {self.model}")

            if validate_on_init and not self.validate_key():
                logger.error("[GROQ] API key validation failed")
                raise ValueError("Groq API key is invalid or not active")

    @property
    def provider(self) -> str:
        return "groq"

    @staticmethod
    def _convert_to_wav(input_path: str) -> str:
        """Convert audio to 16kHz mono WAV using local ffmpeg."""
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
            logger.info(f"[GROQ] Audio converted to WAV: {size} bytes")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"[GROQ] FFmpeg conversion failed: {e.stderr.decode()}")
            raise RuntimeError(f"FFmpeg failed: {e}")
        except FileNotFoundError:
            logger.error("[GROQ] ffmpeg not found in PATH")
            raise RuntimeError("ffmpeg is required for audio conversion")

    @retry_with_backoff(
        max_retries=3,
        base_delay=2.0,
        max_delay=30.0,
        retryable_exceptions=(requests.RequestException, ConnectionError, TimeoutError),
    )
    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file using Groq Whisper.

        Args:
            audio_path: Path to audio file (any format supported by ffmpeg)

        Returns:
            Transcribed text
        """
        logger.info(f"[GROQ] Transcribing: {os.path.basename(audio_path)}")

        # Convert to 16kHz mono WAV (Groq requirement)
        wav_path = None
        try:
            wav_path = self._convert_to_wav(audio_path)

            with open(wav_path, "rb") as f:
                resp = requests.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data={"model": self.model, "language": "es", "response_format": "text"},
                    files={"file": ("audio.wav", f, "audio/wav")},
                    timeout=300,
                )

            resp.raise_for_status()
            result = resp.json()
            text = result.get("text", "").strip()

            if not text:
                logger.warning("[GROQ] Empty transcription received")
                return ""

            logger.info(f"[GROQ] Transcription: {len(text)} chars")
            return text

        except requests.HTTPError as e:
            logger.error(f"[GROQ] API error: {e.response.text if hasattr(e, 'response') else e}")
            raise
        except Exception as e:
            logger.error(f"[GROQ] Transcription error: {e}")
            raise
        finally:
            if wav_path and os.path.exists(wav_path):
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """Groq is transcription-only. Use OpenRouter/Gemini for text generation."""
        raise NotImplementedError(
            "Groq adapter is for transcription only. "
            "Use OpenRouter or Gemini for text generation."
        )

    def run_agent(self, mode: str, text: str, **kwargs) -> str:
        """Groq is transcription-only."""
        raise NotImplementedError(
            "Groq adapter is for transcription only. "
            "Use OpenRouter or Gemini for agent operations."
        )

    def validate_key(self) -> bool:
        """Validate that the API key is configured."""
        return self.api_key is not None and len(self.api_key) > 0
