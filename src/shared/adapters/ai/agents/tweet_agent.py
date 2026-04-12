"""
Tweet Agent.

Agente genérico para generar tweets/posts optimizados para redes sociales.
Funciona con cualquier proveedor de IA a través de AIModelPort.
"""

import logging
from typing import TYPE_CHECKING

from src.shared.adapters.ai.prompt_loader import load_prompt

if TYPE_CHECKING:
    from src.shared.domain.ports.ai_model_port import AIModelPort

logger = logging.getLogger(__name__)


class TweetAgent:
    """
    Agente para generación de tweets/posts para redes sociales.

    Este agente es independiente del proveedor de IA. Recibe una instancia
    de AIModelPort y utiliza el prompt definido en prompts/post-tweet.md.

    Usage:
        from src.shared.adapters.ai.ai_factory import get_ai_adapter
        from src.shared.adapters.ai.agents.tweet_agent import TweetAgent

        ai = get_ai_adapter(provider="openrouter")
        agent = TweetAgent(ai)
        tweet = agent.generate("Noticia sobre inflación")
    """

    AGENT_NAME = "post-tweet"  # Matches prompts/post-tweet.md
    MAX_CHARS = 280

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
        news_or_topic: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        **kwargs,
    ) -> str:
        """
        Genera un tweet/post optimizado para redes sociales.

        Args:
            news_or_topic: Noticia o tema para el tweet.
            temperature: Temperatura de generación (0.0-1.0).
            max_tokens: Máximo número de tokens.
            **kwargs: Argumentos adicionales pasados al adapter.

        Returns:
            Tweet generado como string.
        """
        logger.info(f"[TWEET_AGENT] Generating tweet for: {news_or_topic[:80]}...")

        full_prompt = f"{self.prompt}\n\nNoticia/Tema:\n{news_or_topic}"

        result = self.ai_client.generate(
            prompt=full_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        tweet = result.strip()

        if len(tweet) > self.MAX_CHARS:
            logger.warning(
                f"[TWEET_AGENT] Tweet exceeds {self.MAX_CHARS} chars (got {len(tweet)})"
            )

        logger.info("[TWEET_AGENT] Tweet generated successfully")
        return tweet

    def generate_from_context(
        self,
        context: dict,
        temperature: float = 0.2,
        max_tokens: int = 256,
        **kwargs,
    ) -> str:
        """
        Genera un tweet a partir de un contexto estructurado.

        Args:
            context: Diccionario con datos contextuales.
            temperature: Temperatura de generación.
            max_tokens: Máximo número de tokens.
            **kwargs: Argumentos adicionales pasados al adapter.

        Returns:
            Tweet generado como string.
        """
        import json

        news_text = json.dumps(context, indent=2, ensure_ascii=False)
        logger.info(f"[TWEET_AGENT] Generating from context with keys: {list(context.keys())}")

        return self.generate(
            news_or_topic=news_text,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    def generate_batch(
        self,
        items: list[str],
        temperature: float = 0.2,
        max_tokens: int = 256,
        **kwargs,
    ) -> list[str]:
        """
        Genera múltiples tweets a partir de una lista de noticias.

        Args:
            items: Lista de noticias o temas.
            temperature: Temperatura de generación.
            max_tokens: Máximo número de tokens.
            **kwargs: Argumentos adicionales pasados al adapter.

        Returns:
            Lista de tweets generados.
        """
        logger.info(f"[TWEET_AGENT] Generating {len(items)} tweets")

        tweets = []
        for item in items:
            tweet = self.generate(
                news_or_topic=item,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            tweets.append(tweet)

        return tweets
