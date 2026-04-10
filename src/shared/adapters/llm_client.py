"""
Generic LLM Client Abstraction (Port).

This module provides a generic interface for LLM clients, allowing the application
to work with any LLM provider (Gemini, OpenRouter, Anthropic, etc.) without
coupling to specific implementations.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

logger = logging.getLogger("news_bot")


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """Generate content from prompt."""
        pass

    @abstractmethod
    def validate_key(self) -> bool:
        """Validate the API key."""
        pass


def get_llm_client(provider: str = "gemini", config: Dict = None) -> LLMClient:
    """
    Factory function to get an LLM client by provider name.

    Args:
        provider: One of "gemini", "openrouter", "anthropic"
        config: Client configuration dict

    Returns:
        LLMClient instance
    """
    config = config or {}

    if provider == "gemini":
        from src.shared.adapters.gemini_client import GeminiClientWrapper

        return GeminiClientWrapper(config)
    elif provider == "openrouter":
        from src.shared.adapters.openrouter_client import OpenRouterClientWrapper

        return OpenRouterClientWrapper(config)
    elif provider == "anthropic":
        from src.shared.adapters.anthropic_client import AnthropicClientWrapper

        return AnthropicClientWrapper(config)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


class GeminiClientWrapper(LLMClient):
    """Wrapper for Gemini client."""

    def __init__(self, config: dict):
        from src.shared.adapters.gemini_client import get_gemini_client

        self._client = get_gemini_client(config)
        self._config = config

    def generate(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        return self._client.generate(prompt)

    def validate_key(self) -> bool:
        return self._client.api_key is not None


class OpenRouterClientWrapper(LLMClient):
    """Wrapper for OpenRouter client."""

    def __init__(self, config: dict):
        from src.shared.adapters.openrouter_client import get_openrouter_client

        self._client = get_openrouter_client(config)
        self._config = config

    def generate(
        self,
        prompt: str,
        system_prompt: str = None,
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


def get_mock_llm_client(config: dict = None) -> LLMClient:
    """Get mock LLM client for testing."""
    return MockLLMClient(config or {})


class MockLLMClient(LLMClient):
    """Mock LLM client for testing."""

    def __init__(self, config: dict = None):
        self._config = config or {}

    def generate(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        return (
            "<h1>Test Title</h1>\n<p>Generated content from prompt: "
            + prompt[:100]
            + "...</p>"
        )

    def validate_key(self) -> bool:
        return True
