"""Puerto/Interfaz para descarga de video (Hexagonal Architecture - Port)."""

from abc import ABC, abstractmethod
from typing import Optional


class VideoFetcherPort(ABC):
    """Interfaz base para servicios de descarga de video desde URLs."""

    @abstractmethod
    def fetch(self, url: str, video_id: Optional[str] = None) -> Optional[str]:
        """Descarga un video desde una URL.

        Args:
            url: URL del video a descargar.
            video_id: Identificador opcional del video.

        Returns:
            Ruta del archivo descargado, o None si falla.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_info(self, url: str) -> Optional[dict]:
        """Obtiene metadatos de un video sin descargarlo.

        Args:
            url: URL del video.

        Returns:
            Diccionario con metadatos, o None si falla.
        """
        raise NotImplementedError()
