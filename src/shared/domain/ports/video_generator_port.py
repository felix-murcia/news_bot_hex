"""Puerto (interface) para generación de video desde audio e imagen.

Este puerto define el contrato que cualquier adaptador de generación
de video debe implementar, siguiendo el principio de inversión de dependencias
(D de SOLID). La capa de aplicación depende de abstracciones, no de implementaciones
concretas.
"""

from abc import ABC, abstractmethod
from typing import Optional


class VideoGeneratorPort(ABC):
    """Puerto para generar videos a partir de audio e imagen."""

    @abstractmethod
    def create_video_from_audio(
        self, audio_path: str, output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Genera un video combinando un audio con una imagen.

        Args:
            audio_path: Ruta al archivo de audio.
            output_path: Ruta de salida opcional para el video.

        Returns:
            Ruta del video generado, o None si falla.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Verifica si el servicio de generación de video está disponible.

        Returns:
            True si el servicio está operativo, False en caso contrario.
        """
        pass
