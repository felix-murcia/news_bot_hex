"""
Article From Content Agent.

Agente genérico para generar artículos desde transcripciones, contenido web u otras fuentes.
Funciona con cualquier proveedor de IA a través de AIModelPort.
"""

import logging
from typing import Optional, TYPE_CHECKING

from src.shared.adapters.ai.prompt_loader import load_prompt

if TYPE_CHECKING:
    from src.shared.domain.ports.ai_model_port import AIModelPort

logger = logging.getLogger(__name__)


class ArticleFromContentAgent:
    """
    Agente para generar artículos desde transcripciones o contenido.

    Este agente es independiente del proveedor de IA. Recibe una instancia
    de AIModelPort y utiliza el prompt adecuado según la fuente.

    Usage:
        from src.shared.adapters.ai.agents import ArticleFromContentAgent

        agent = ArticleFromContentAgent(ai, source_type="transcript")
        article = agent.generate(transcript, tema="Economía")
    """

    # Mapa de tipo de fuente a nombre de prompt
    PROMPT_MAP = {
        "transcript": "article-from-transcript",
        "video": "article-from-video",
        "article": "article",
    }

    def __init__(self, ai_client: "AIModelPort", source_type: str = "transcript"):
        """
        Inicializa el agente.

        Args:
            ai_client: Instancia de AIModelPort.
            source_type: Tipo de fuente ("transcript", "video", "article").
        """
        self.ai_client = ai_client
        self.source_type = source_type
        self._prompt = None

    @property
    def prompt(self) -> str:
        """Carga el prompt bajo demanda (lazy loading)."""
        if self._prompt is None:
            prompt_name = self.PROMPT_MAP.get(self.source_type, "article")
            self._prompt = load_prompt(prompt_name)
        return self._prompt

    def generate(
        self,
        content: str,
        tema: str = "General",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs,
    ) -> str:
        """
        Genera un artículo desde contenido/transcripción.

        Args:
            content: Contenido base (transcripción, texto, etc.).
            tema: Tema o categoría del artículo.
            temperature: Temperatura de generación (0.0-1.0).
            max_tokens: Máximo número de tokens.
            **kwargs: Argumentos adicionales pasados al adapter.

        Returns:
            Artículo generado como string HTML.
        """
        logger.info(f"[ARTICLE_FROM_CONTENT] Generating from {self.source_type}: {tema}")

        full_prompt = f"{self.prompt}\n\nContenido:\n{content}\n\nTema: {tema}"

        result = self.ai_client.generate(
            prompt=full_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        logger.info("[ARTICLE_FROM_CONTENT] Article generated successfully")
        return result
