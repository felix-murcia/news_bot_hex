"""Puerto/Interfaz para modelos de IA (Hexagonal Architecture - Port)."""

from abc import ABC, abstractmethod
from typing import Optional


class AIModelPort(ABC):
    """
    Interfaz base para cualquier modelo de IA.

    En arquitectura hexagonal, esto es el "Port" - la abstracción
    que define cómo la aplicación interactúa con los modelos de IA.
    """

    @abstractmethod
    def transcribe(self, audio_path: str) -> str:
        """Transcribe un archivo de audio."""
        raise NotImplementedError()

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """Genera contenido a partir de un prompt."""
        raise NotImplementedError()

    @abstractmethod
    def run_agent(self, mode: str, text: str, **kwargs) -> str:
        """Ejecuta un agente específico sobre un texto."""
        raise NotImplementedError()

    @abstractmethod
    def validate_key(self) -> bool:
        """Valida que la API key esté configurada."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def provider(self) -> str:
        """Nombre del proveedor del modelo."""
        raise NotImplementedError()
