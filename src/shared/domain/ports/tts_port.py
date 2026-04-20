"""Puerto/Interfaz para Text-to-Speech (Hexagonal Architecture - Port)."""

from abc import ABC, abstractmethod
from typing import Optional


class TTSPort(ABC):
    """
    Interfaz base para servicios de Text-to-Speech.

    En arquitectura hexagonal, esto es el "Port" - la abstracción
    que define cómo la aplicación interactúa con los servicios TTS.
    """

    @abstractmethod
    def text_to_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        model: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """Convierte texto a audio y devuelve la ruta del archivo.

        Args:
            text: Texto a convertir a audio.
            voice: Voz a usar para la síntesis.
            model: Modelo TTS a utilizar.
            output_path: Ruta donde guardar el audio (opcional).

        Returns:
            Ruta del archivo de audio generado.
        """
        raise NotImplementedError()

    @abstractmethod
    def is_available(self) -> bool:
        """Verifica si el servicio TTS está disponible."""
        raise NotImplementedError()
