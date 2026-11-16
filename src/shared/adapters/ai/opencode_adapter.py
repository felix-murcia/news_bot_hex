"""OpenCode Adapter (Hexagonal Architecture - Adapter).

Implementation of AIModelPort for OpenCode (self-hosted / API-compatible chat completions endpoint).
OpenAI-compatible chat completions endpoint.
"""

import logging
from typing import Dict, Optional

import requests
from dotenv import load_dotenv

from src.shared.utils.retry import retry_with_backoff, FatalAuthError
from src.shared.domain.ports.ai_model_port import AIModelPort
from config.settings import Settings

load_dotenv()

logger = logging.getLogger(__name__)


class OpenCodeAdapter(AIModelPort):
    """Adapter for OpenCode self-hosted or API catalog (OpenAI-compatible)."""

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
        """Initialize the OpenCode adapter.

        Args:
            config: Configuration dictionary
            validate_on_init: If True, validates API key on initialization
        """
        self.config = config or {}
        self.api_key = Settings.API_KEYS.get("opencode", "")
        self.model = self.config.get("model", Settings.OPENCODE_MODEL)
        self.api_url = self.config.get("api_url", Settings.OPENCODE_API_URL)

        if not self.api_key:
            logger.warning("[OPENCODE] API key not found")
        else:
            logger.info(f"[OPENCODE] Initialized with model: {self.model}")

            if validate_on_init and not self.validate_key():
                logger.error("[OPENCODE] API key validation failed")
                raise ValueError("OpenCode API key is invalid or not active")

    @property
    def provider(self) -> str:
        return "opencode"

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
        }

        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=60,
            )
        except requests.RequestException as e:
            logger.error(f"[OPENCODE] Error de red: {e}")
            raise

        # Fail-fast inmediato: 401/403 = API Key inválida o sin saldo.
        # No reintentar, no probar con otra candidata. Propagar FatalAuthError
        # directamente desde generate(); el decorator retry no lo captura porque
        # no hereda de requests.RequestException.
        if response.status_code in (401, 403):
            raise FatalAuthError(
                f"OPENCODE {response.status_code}: API Key inválida o sin saldo. "
                f"No se reintentará ni se probará con otra candidata."
            )

        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            logger.error(f"[OPENCODE] Error HTTP: {e}")
            raise

        try:
            result = response.json()
        except ValueError as e:
            logger.error(f"[OPENCODE] Error parseando JSON: {e}")
            raise

        choices = result.get("choices", [{}]).first if hasattr(result.get("choices", []), "first") else (result.get("choices", [{}])[0] if result.get("choices") else {})
        first_choice = choices if isinstance(choices, dict) else (result.get("choices", [{}])[0] if result.get("choices") else {})
        finish_reason = first_choice.get("finish_reason")
        content = first_choice.get("message", {}).get("content")

        try:
            if not content:
                logger.warning(
                    f"[OPENCODE] Empty content in response "
                    f"(finish_reason={finish_reason}). "
                    f"Raw response keys: {list(result.keys())}. "
                    f"Raw content: {repr(content)}"
                )
                if "output" in result:
                    content = result["output"]
                elif "text" in result:
                    content = result["text"]
            return content or ""
        except Exception as e:
            logger.error(f"[OPENCODE] Error: {e}")
            raise

    def transcribe(self, audio_path: str) -> str:
        raise NotImplementedError("OpenCode does not support transcription. Use Whisper.")

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
            }
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": "OK"}],
                "temperature": 0.0,
                "max_tokens": 1,
            }
            response = requests.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=10,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False