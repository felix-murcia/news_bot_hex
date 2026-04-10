"""
Implementación de AIModel para OpenRouter.
"""

import os
import logging
from typing import Dict, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "openrouter/free"
REFERER = "http://nbes.blog"
APP_TITLE = "news_bot"


class OpenRouterAIModel:
    """Modelo de IA basado en OpenRouter."""

    AGENTS = {
        "refinamiento": "Refina y mejora la calidad del texto.",
        "tecnico": "Convierte a formato técnico profesional.",
        "ejecutivo": "Resume en formato ejecutivo conciso.",
        "project_manager": "Estructura para gestión de proyectos.",
        "product_manager": "Estructura para gestión de productos.",
        "quality_assurance": "Revisión y control de calidad.",
        "bullet": "Convierte a formato de viñetas.",
        "comparative": "Análisis comparativo.",
    }

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.model = self.config.get("model", DEFAULT_MODEL)

        if not self.api_key:
            logger.warning("[OPENROUTER] API key no encontrada")

    @property
    def provider(self) -> str:
        return "openrouter"

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
            "HTTP-Referer": REFERER,
            "X-OpenRouter-Title": APP_TITLE,
        }

        data = {
            "model": self.model,
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
        except Exception as e:
            logger.error(f"[OPENROUTER] Error: {e}")
            raise

    def transcribe(self, audio_path: str) -> str:
        raise NotImplementedError("OpenRouter no soporta transcripción. Usa Whisper.")

    def run_agent(self, mode: str, text: str, **kwargs) -> str:
        if mode not in self.AGENTS:
            raise ValueError(f"Agente '{mode}' no válido")

        agent_prompt = self._load_agent_prompt(mode)
        prompt = f"{agent_prompt}\n\nTexto:\n{text}"

        return self.generate(
            prompt=prompt,
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 2048),
        )

    def _load_agent_prompt(self, mode: str) -> str:
        prompts = {
            "refinamiento": "Eres un editor experto. Refina y mejora el texto.",
            "tecnico": "Convierte a formato técnico profesional.",
            "ejecutivo": "Resume en formato ejecutivo conciso.",
            "project_manager": "Estructura para gestión de proyectos.",
            "product_manager": "Estructura para gestión de productos.",
            "quality_assurance": "Revisa y señala problemas.",
            "bullet": "Convierte a formato de viñetas.",
            "comparative": "Realiza análisis comparativo.",
        }
        return prompts.get(mode, "")

    def validate_key(self) -> bool:
        if not self.api_key:
            return False
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": REFERER,
            }
            response = requests.get(
                "https://openrouter.ai/api/v1/auth/key",
                headers=headers,
                timeout=10,
            )
            return response.status_code == 200
        except:
            return False
