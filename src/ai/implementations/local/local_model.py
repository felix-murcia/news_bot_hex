"""
Implementación de AIModel para modelos locales (fallback/mock).
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class LocalAIModel:
    """Modelo de IA local sin API externa."""

    AGENTS = {
        "refinamiento": "Refina y mejora la calidad del texto.",
        "tecnico": "Convierte a formato técnico profesional.",
        "ejecutivo": "Resume en formato ejecutivo conciso.",
        "bullet": "Convierte a formato de viñetas.",
    }

    def __init__(self, config: Dict = None):
        self.config = config or {}

    @property
    def provider(self) -> str:
        return "local"

    def transcribe(self, audio_path: str) -> str:
        try:
            import whisper

            model = whisper.load_model("medium")
            result = model.transcribe(audio_path)
            return result["text"].strip()
        except ImportError:
            raise RuntimeError("Whisper no instalado")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        return f"<h1>Contenido Local</h1><p>Fallback para: {prompt[:100]}...</p>"

    def run_agent(self, mode: str, text: str, **kwargs) -> str:
        if mode not in self.AGENTS:
            return f"[Agente '{mode}' no disponible en modo local]"
        return f"Local: {text[:200]}..."

    def validate_key(self) -> bool:
        return True


class MockAIModel:
    """Modelo mock para testing."""

    AGENTS = {
        "refinamiento": "Refina y mejora la calidad del texto.",
        "tecnico": "Convierte a formato técnico profesional.",
        "ejecutivo": "Resume en formato ejecutivo conciso.",
    }

    def __init__(self, config: Dict = None):
        self.config = config or {}

    @property
    def provider(self) -> str:
        return "mock"

    def transcribe(self, audio_path: str) -> str:
        return f"Transcripción mock de: {audio_path}"

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        return f"<h1>Test Title</h1><p>Generated content from prompt: {prompt[:100]}...</p>"

    def run_agent(self, mode: str, text: str, **kwargs) -> str:
        if mode not in self.AGENTS:
            return f"[Agente '{mode}' no válido]"
        return f"[Mock] Resultado del agente '{mode}' para: {text[:50]}..."

    def validate_key(self) -> bool:
        return True
