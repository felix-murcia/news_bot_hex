"""Puerto/Interfaz para conversión de audio (Hexagonal Architecture - Port)."""

from abc import ABC, abstractmethod
from typing import Optional


class AudioConverterPort(ABC):
    """Interfaz base para servicios de conversión de audio."""

    @abstractmethod
    def convert_to_mp3(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        bitrate: str = "192k",
        delete_original: bool = False,
    ) -> Optional[str]:
        """Convierte un archivo de audio a MP3.

        Args:
            input_path: Ruta al archivo de entrada.
            output_path: Ruta de salida MP3 (si None, se genera automáticamente).
            bitrate: Bitrate del MP3.
            delete_original: Si True, elimina el archivo original tras conversión.

        Returns:
            Ruta del archivo MP3 generado, o None si falla.
        """
        raise NotImplementedError()

    @abstractmethod
    def convert_to_wav16k(
        self,
        input_path: str,
        output_path: Optional[str] = None,
    ) -> Optional[str]:
        """Convierte un archivo de audio a WAV 16kHz mono.

        Args:
            input_path: Ruta al archivo de entrada.
            output_path: Ruta de salida WAV (si None, se genera automáticamente).

        Returns:
            Ruta del archivo WAV generado, o None si falla.
        """
        raise NotImplementedError()

    @abstractmethod
    def has_audio_stream(self, file_path: str) -> bool:
        """Verifica si un archivo contiene un stream de audio.

        Args:
            file_path: Ruta al archivo.

        Returns:
            True si tiene stream de audio, False en caso contrario.
        """
        raise NotImplementedError()
