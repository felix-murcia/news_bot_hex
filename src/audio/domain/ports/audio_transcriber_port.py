"""Puerto/Interfaz para transcripción de audio (Hexagonal Architecture - Port)."""

from abc import ABC, abstractmethod


class AudioTranscriberPort(ABC):
    """Interfaz base para servicios de transcripción de audio."""

    @abstractmethod
    def transcribe(self, audio_path: str) -> str:
        """Transcribe un archivo de audio a texto.

        Args:
            audio_path: Ruta al archivo de audio.

        Returns:
            Texto transcrito.
        """
        raise NotImplementedError()
