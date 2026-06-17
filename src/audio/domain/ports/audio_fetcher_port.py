"""Puerto/Interfaz para descarga de audio (Hexagonal Architecture - Port)."""

from abc import ABC, abstractmethod
from typing import Optional


class AudioFetcherPort(ABC):
    """Interfaz base para servicios de descarga de audio desde URLs."""

    @abstractmethod
    def fetch(self, url: str, audio_id: Optional[str] = None) -> Optional[str]:
        """Descarga un audio desde una URL.

        Args:
            url: URL del audio a descargar.
            audio_id: Identificador opcional del audio.

        Returns:
            Ruta del archivo descargado, o None si falla.
        """
        raise NotImplementedError()

    @abstractmethod
    def transcribe(self, audio_path: str) -> str:
        """Transcribe un archivo de audio a texto.

        Args:
            audio_path: Ruta al archivo de audio.

        Returns:
            Texto transcrito.
        """
        raise NotImplementedError()
