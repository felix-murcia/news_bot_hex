"""
OpenRouter Adapter (Hexagonal Architecture - Adapter).

Implementation of AIModelPort for OpenRouter.
"""

import os
import logging
from typing import Dict, Optional

import requests
from dotenv import load_dotenv

from src.shared.utils.retry import retry_with_backoff
from config.settings import Settings

load_dotenv()

logger = logging.getLogger(__name__)


class OpenRouterAdapter:
    """Adapter for OpenRouter."""

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
        """Initialize the OpenRouter adapter.
        
        Args:
            config: Configuration dictionary
            validate_on_init: If True, validates API key on initialization
        """
        self.config = config or {}
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.model = self.config.get("model", Settings.OPENROUTER_MODEL)

        if not self.api_key:
            logger.warning("[OPENROUTER] API key not found")
        else:
            logger.info(f"[OPENROUTER] Initialized with model: {self.model}")
            
            if validate_on_init and not self.validate_key():
                logger.error("[OPENROUTER] API key validation failed")
                raise ValueError("OpenRouter API key is invalid or not active")

    @property
    def provider(self) -> str:
        return "openrouter"

    @retry_with_backoff(
        max_retries=Settings.RETRY_MAX_ATTEMPTS,
        base_delay=Settings.RETRY_BASE_DELAY,
        max_delay=Settings.RETRY_MAX_DELAY,
        retryable_exceptions=(requests.RequestException, ConnectionError, TimeoutError),
    )
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": Settings.OPENROUTER_REFERER,
            "X-OpenRouter-Title": Settings.OPENROUTER_APP_TITLE,
        }

        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            response = requests.post(
                Settings.OPENROUTER_API_URL,
                headers=headers,
                json=data,
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content")
            if not content:
                logger.warning(f"[OPENROUTER] Empty content in response")
                # Try alternative response structure
                if "output" in result:
                    content = result["output"]
                elif "text" in result:
                    content = result["text"]
            return content or ""
        except Exception as e:
            logger.error(f"[OPENROUTER] Error: {e}")
            raise

    def transcribe(self, audio_path: str) -> str:
        raise NotImplementedError("OpenRouter does not support transcription. Use Whisper.")

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

    @retry_with_backoff(
        max_retries=2,
        base_delay=1.0,
        max_delay=10.0,
        retryable_exceptions=(requests.RequestException, ConnectionError, TimeoutError),
    )
    def validate_key(self) -> bool:
        """Validate that the API key is configured and active."""
        if not self.api_key:
            return False
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": Settings.OPENROUTER_REFERER,
            }
            response = requests.get(
                Settings.OPENROUTER_AUTH_URL,
                headers=headers,
                timeout=10,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False
