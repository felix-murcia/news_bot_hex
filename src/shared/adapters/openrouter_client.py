import os
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from config.settings import Settings
from src.logging_config import get_logger

load_dotenv()

logger = get_logger("news_bot")

DEFAULT_MODEL = Settings.OPENROUTER_MODEL
DEFAULT_TEMPERATURE = Settings.MODEL_PARAMS_CONTENT["temperature"]
DEFAULT_MAX_TOKENS = Settings.MODEL_PARAMS_CONTENT.get("max_tokens", 2048)
REFERER = Settings.OPENROUTER_REFERER
APP_TITLE = Settings.OPENROUTER_APP_TITLE


def get_openrouter_client(config: Optional[dict] = None) -> "OpenRouterClient":
    """Get OpenRouter client instance."""
    return OpenRouterClient(config if config else {})


class OpenRouterClient:
    """Client for OpenRouter API."""

    def __init__(self, config: dict):
        self.config = config
        self.api_key = os.getenv("OPENROUTER_API_KEY")

        if not self.api_key:
            logger.warning("[OPENROUTER] API key not found in environment")
            raise RuntimeError("OPENROUTER_API_KEY not set")

    def validate_key(self) -> bool:
        """Validate the API key."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": REFERER,
                "X-OpenRouter-Title": APP_TITLE,
            }
            response = requests.get(
                "https://openrouter.ai/api/v1/auth/key",
                headers=headers,
                timeout=10,
            )
            if response.status_code == 200:
                logger.info("[OPENROUTER] API key valid")
                return True
            else:
                logger.warning(f"[OPENROUTER] API key invalid: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"[OPENROUTER] Error validating key: {e}")
            return False

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Generate content using OpenRouter."""
        model = self.config.get("model", DEFAULT_MODEL)
        temperature = temperature or self.config.get("temperature", DEFAULT_TEMPERATURE)
        max_tokens = max_tokens or self.config.get("max_tokens", DEFAULT_MAX_TOKENS)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": REFERER,
            "X-OpenRouter-Title": APP_TITLE,
        }

        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            logger.error(f"[OPENROUTER] Error generating: {e}")
            raise
        except Exception as e:
            logger.error(f"[OPENROUTER] Error: {e}")
            raise


class MockOpenRouterClient:
    """Mock OpenRouter client for testing."""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def generate(self, prompt: str, **kwargs) -> str:
        """Mock generate method."""
        return (
            "<h1>Test Title</h1>\n<p>Generated content from prompt: "
            + prompt[:100]
            + "...</p>"
        )


def get_mock_openrouter_client(config: Optional[dict] = None) -> "MockOpenRouterClient":
    """Get mock OpenRouter client for testing."""
    return MockOpenRouterClient(config)


class OpenRouterClientWrapper:
    """Wrapper for OpenRouter client to implement LLMClient interface."""

    def __init__(self, config: dict):
        self._client = OpenRouterClient(config)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        return self._client.generate(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def validate_key(self) -> bool:
        return self._client.validate_key()
