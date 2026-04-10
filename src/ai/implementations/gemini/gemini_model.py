"""
Implementación de AIModel para Google Gemini.
"""

import os
import logging
from typing import Dict, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class GeminiAIModel:
    """Modelo de IA basado en Google Gemini."""

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
        self.api_key = os.getenv("GEMINI_API_KEY")
        self._client = None

        if not self.api_key:
            logger.warning("[GEMINI] API key no encontrada en entorno")

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
            "Gemini no soporta transcripción. Usa Whisper u otro modelo."
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
            "refinamiento": "Eres un editor experto. Refina y mejora el siguiente texto.",
            "tecnico": "Convierte el siguiente texto a formato técnico profesional.",
            "ejecutivo": "Resume el siguiente texto en formato ejecutivo conciso.",
            "project_manager": "Estructura el siguiente texto para gestión de proyectos.",
            "product_manager": "Estructura el siguiente texto para gestión de productos.",
            "quality_assurance": "Revisa el siguiente texto y señala problemas de calidad.",
            "bullet": "Convierte el siguiente texto a formato de viñetas.",
            "comparative": "Realiza un análisis comparativo del siguiente texto.",
        }
        return prompts.get(mode, "")

    def validate_key(self) -> bool:
        return self.api_key is not None and len(self.api_key) > 0
