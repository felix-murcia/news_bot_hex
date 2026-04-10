"""
Interfaz base para cualquier modelo de IA integrado en TranscriberApp.

Cada modelo (Gemini, OpenAI, Mistral, OpenRouter, etc.) debe implementar
esta interfaz. El código de la aplicación solo conoce esta abstracción,
nunca las implementaciones concretas.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AIModel(ABC):
    """
    Interfaz base para cualquier modelo de IA.

    Proporciona una abstracción unificada para:
    - Transcripción de audio
    - Generación de contenido
    - Ejecución de agentes especializados
    """

    @abstractmethod
    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe un archivo de audio y devuelve el texto resultante.

        Args:
            audio_path: Ruta al archivo de audio a transcribir.

        Returns:
            Texto transcrito del audio.

        Raises:
            NotImplementedError: Si el modelo no soporta transcripción.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.transcribe() no está implementado."
        )

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str:
        """
        Genera contenido a partir de un prompt.

        Args:
            prompt: Prompt principal.
            system_prompt: Prompt de sistema (opcional).
            temperature: Temperatura para la generación.
            max_tokens: Máximo de tokens a generar.

        Returns:
            Contenido generado.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.generate() no está implementado."
        )

    @abstractmethod
    def run_agent(self, mode: str, text: str, **kwargs) -> str:
        """
        Ejecuta un agente específico sobre un texto.

        El agente puede ser:
        - "refinamiento": Mejora la calidad del texto
        - "tecnico": Convierte a formato técnico
        - "ejecutivo": Resume para ejecutivos
        - "project_manager": Formato para gestión de proyectos
        - "product_manager": Formato para gestión de productos
        - "quality_assurance": Revisión de calidad
        - "bullet": Formato de viñetas
        - "comparative": Análisis comparativo

        Args:
            mode: Modo del agente a ejecutar.
            text: Texto sobre el cual ejecutar el agente.
            **kwargs: Parámetros adicionales para el agente.

        Returns:
            Resultado del agente.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.run_agent() no está implementado."
        )

    @abstractmethod
    def validate_key(self) -> bool:
        """
        Valida que la API key esté configurada correctamente.

        Returns:
            True si la API key es válida, False en caso contrario.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.validate_key() no está implementado."
        )

    @property
    @abstractmethod
    def provider(self) -> str:
        """
        Nombre del proveedor del modelo.

        Returns:
            Nombre del proveedor (ej: "gemini", "openrouter", "local").
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.provider no está implementado."
        )
