import os
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("news_bot")


def get_gemini_client(config: Optional[dict] = None) -> "GeminiClient":
    """Get Gemini client instance."""
    return GeminiClient(config or {})


class GeminiClient:
    """Client for Gemini API."""

    def __init__(self, config: dict):
        self.config = config
        self.api_key = os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            logger.warning("[GEMINI] API key not found in environment")
            raise RuntimeError("GEMINI_API_KEY not set")

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate content using Gemini."""
        try:
            from google import genai as google_genai

            client = google_genai.Client(api_key=self.api_key)
            model_name = self.config.get("model_name", "gemini-2.5-flash")

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            return response.text or ""

        except ImportError:
            logger.error("[GEMINI] google-genai not installed")
            raise RuntimeError("Install google-genai: pip install google-genai")
        except Exception as e:
            logger.error(f"[GEMINI] Error generating: {e}")
            raise


class MockGeminiClient:
    """Mock Gemini client for testing."""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def generate(self, prompt: str, **kwargs) -> str:
        """Mock generate method."""
        return (
            "<h1>Test Title</h1>\n<p>Generated content from prompt: "
            + prompt[:100]
            + "...</p>"
        )


def get_mock_gemini_client(config: Optional[dict] = None) -> "MockGeminiClient":
    """Get mock Gemini client for testing."""
    return MockGeminiClient(config)


class GeminiClientWrapper:
    """Wrapper for Gemini client to implement LLMClient interface."""

    def __init__(self, config: dict):
        self._client = GeminiClient(config)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        return self._client.generate(prompt)

    def validate_key(self) -> bool:
        return self._client.api_key is not None
