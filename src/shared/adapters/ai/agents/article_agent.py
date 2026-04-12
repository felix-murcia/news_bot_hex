"""
Article Agent.

Agente genérico para generar artículos periodísticos profesionales.
Funciona con cualquier proveedor de IA a través de AIModelPort.
"""

import logging
from typing import TYPE_CHECKING

from src.shared.adapters.ai.prompt_loader import load_prompt

if TYPE_CHECKING:
    from src.shared.domain.ports.ai_model_port import AIModelPort

logger = logging.getLogger(__name__)


class ArticleAgent:
    """
    Agente para generación de artículos periodísticos.

    Este agente es independiente del proveedor de IA. Recibe una instancia
    de AIModelPort y utiliza el prompt definido en prompts/article.md.

    Usage:
        from src.shared.adapters.ai.ai_factory import get_ai_adapter
        from src.shared.adapters.ai.agents.article_agent import ArticleAgent

        ai = get_ai_adapter(provider="gemini")
        agent = ArticleAgent(ai)
        article = agent.generate("Tema del artículo")
    """

    AGENT_NAME = "article"

    def __init__(self, ai_client: "AIModelPort"):
        """
        Inicializa el agente con un cliente de IA.

        Args:
            ai_client: Instancia de AIModelPort (Gemini, OpenRouter, Local, etc.)
        """
        self.ai_client = ai_client
        self._prompt = None

    @property
    def prompt(self) -> str:
        """Carga el prompt bajo demanda (lazy loading)."""
        if self._prompt is None:
            self._prompt = load_prompt(self.AGENT_NAME)
        return self._prompt

    def generate(
        self,
        topic_or_news: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs,
    ) -> str:
        """
        Genera un artículo periodístico profesional.

        Args:
            topic_or_news: Tema o noticia base para el artículo.
            temperature: Temperatura de generación (0.0-1.0).
            max_tokens: Máximo número de tokens.
            **kwargs: Argumentos adicionales pasados al adapter.

        Returns:
            Artículo generado como string.
        """
        logger.info(f"[ARTICLE_AGENT] Generating article for: {topic_or_news[:80]}...")

        full_prompt = f"{self.prompt}\n\nTema/Noticia:\n{topic_or_news}"

        result = self.ai_client.generate(
            prompt=full_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        logger.info("[ARTICLE_AGENT] Article generated successfully")
        return result

    def generate_from_context(
        self,
        context: dict,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs,
    ) -> str:
        """
        Genera un artículo a partir de un contexto estructurado.

        Args:
            context: Diccionario con datos contextuales (ej: {"headline": "...", "sources": [...]}).
            temperature: Temperatura de generación.
            max_tokens: Máximo número de tokens.
            **kwargs: Argumentos adicionales pasados al adapter.

        Returns:
            Artículo generado como string.
        """
        import json

        news_text = json.dumps(context, indent=2, ensure_ascii=False)
        logger.info(f"[ARTICLE_AGENT] Generating from context with keys: {list(context.keys())}")

        return self.generate(
            topic_or_news=news_text,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
