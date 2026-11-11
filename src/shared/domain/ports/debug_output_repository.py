from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict


class DebugOutputRepository(ABC):
    @abstractmethod
    def save_outputs(self, kind: str, article_data: Dict[str, Any], post: Dict[str, Any]) -> Path:
        """Guarda JSON de debug. kind: 'audio' | 'video'. Devuelve la ruta del fichero de artículos."""
