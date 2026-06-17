"""Puerto/Interfaz para transcripción de video (Hexagonal Architecture - Port)."""

from abc import ABC, abstractmethod


class VideoTranscriberPort(ABC):
    """Interfaz base para servicios de transcripción de audio de video."""

    @abstractmethod
    def transcribe(self, audio_path: str) -> str:
        """Transcribe el audio de un video a texto.

        Args:
            audio_path: Ruta al archivo de audio extraído del video.

        Returns:
            Texto transcrito.
        """
        raise NotImplementedError()
