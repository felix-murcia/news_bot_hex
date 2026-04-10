"""
Google Gemini Adapter (Hexagonal Architecture - Adapter).

Implementation of AIModelPort for Google Gemini.
"""

import os
import logging
from typing import Dict, Optional

from dotenv import load_dotenv

from src.shared.utils.retry import retry_with_backoff

load_dotenv()

logger = logging.getLogger(__name__)


class GeminiAdapter:
    """Adapter for Google Gemini."""

    AGENTS = [
        "refinamiento",
        "tecnico",
        "ejecutivo",
        "project_manager",
        "product_manager",
        "quality_assurance",
        "bullet",
        "comparative",
    ]

    def __init__(self, config: Dict = None, validate_on_init: bool = False):
        """Initialize the Gemini adapter.
        
        Args:
            config: Configuration dictionary
            validate_on_init: If True, validates API key on initialization
        """
        self.config = config or {}
        self.api_key = os.getenv("GEMINI_API_KEY")
        self._client = None

        if not self.api_key:
            logger.warning("[GEMINI] API key not found in environment")
        else:
            model_name = self.config.get("model_name", "gemini-2.5-flash")
            logger.info(f"[GEMINI] Initialized with model: {model_name}")
            
            if validate_on_init and not self.validate_key():
                logger.error("[GEMINI] API key validation failed")
                raise ValueError("Gemini API key is invalid or not active")

    @property
    def provider(self) -> str:
        return "gemini"

    def _get_client(self):
        if self._client is None:
            from google import genai as google_genai

            self._client = google_genai.Client(api_key=self.api_key)
        return self._client

    def transcribe(self, audio_path: str) -> str:
        raise NotImplementedError(
            "Gemini does not support transcription. Use Whisper or another model."
        )

    @retry_with_backoff(
        max_retries=3,
        base_delay=2.0,
        max_delay=30.0,
        retryable_exceptions=(Exception,),  # Gemini SDK can raise various exceptions
    )
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        try:
            client = self._get_client()
            model_name = self.config.get("model_name", "gemini-2.5-flash")

            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            response = client.models.generate_content(
                model=model_name,
                contents=full_prompt,
            )
            return response.text

        except ImportError:
            logger.error("[GEMINI] google-genai no instalado")
            raise RuntimeError("Instala google-genai: pip install google-genai")
        except Exception as e:
            logger.error(f"[GEMINI] Error en generate: {e}")
            raise

    def run_agent(self, mode: str, text: str, **kwargs) -> str:
        if mode not in self.AGENTS:
            raise ValueError(f"Agent '{mode}' is not valid")

        from src.shared.adapters.ai.prompt_loader import load_prompt

        agent_prompt = load_prompt(mode)
        prompt = f"{agent_prompt}\n\nText:\n{text}"

        return self.generate(
            prompt=prompt,
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 2048),
        )

    def validate_key(self) -> bool:
        """Validate that the API key is configured."""
        return self.api_key is not None and len(self.api_key) > 0
