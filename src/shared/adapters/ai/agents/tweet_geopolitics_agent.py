"""
Tweet Geopolitics Agent.

Agente genérico para generar tweets estilo geopolítico (The Economist).
Funciona con cualquier proveedor de IA a través de AIModelPort.
"""

import logging
from typing import TYPE_CHECKING

from src.shared.adapters.ai.prompt_loader import load_prompt
from src.shared.domain.services.tweet_response import TweetResponse, validar_tweet

if TYPE_CHECKING:
    from src.shared.domain.ports.ai_model_port import AIModelPort

logger = logging.getLogger(__name__)


class TweetGeopoliticsAgent:
    """
    Agente para generación de tweets estilo geopolítico (The Economist).

    Este agente es independiente del proveedor de IA. Recibe una instancia
    de AIModelPort y utiliza el prompt definido en prompts/tweet-geopolitics.md.

    Usage:
        from src.shared.adapters.ai.agents import TweetGeopoliticsAgent

        agent = TweetGeopoliticsAgent(ai)
        respuesta = agent.generate(title="BCE sube tipos", tema="Economía", context="...")
        if respuesta.publishable:
            publicar(respuesta.text)
        else:
            logger.warning(respuesta.reason)
    """

    AGENT_NAME = "tweet-geopolitics"
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
        title: str,
        tema: str = "Noticias",
        context: str = "",
        temperature: float = 0.2,
        max_tokens: int = 1024,
        **kwargs,
    ) -> TweetResponse:
        """
        1024, no 256: el default era 256 y devolvia content=None con
        finish_reason="length" — el pipeline abortaba con "Tweet generado
        vacío". Con Gemma 4 (sin reasoning) 1024 sobra de sobra; el margen
        queda para el caso de que OPENROUTER_MODEL apunte a un modelo con
        razonamiento, cuyo campo `reasoning` se paga con este mismo
        presupuesto. Los agentes de articulo usan 4096 por el mismo motivo.
        Genera un tweet estilo geopolítico.

        El prompt obliga al modelo a responder con JSON
        {"publicable": bool, "tweet"/"motivo"}; `validar_tweet` lo comprueba
        y decide si hay un tweet publicable (comprobación determinista, con
        segunda capa por patrones si no hay JSON).

        Args:
            title: Título de la noticia.
            tema: Tema o categoría.
            context: Contexto adicional (primeros 200-300 chars del artículo).
            temperature: Temperatura de generación (0.0-1.0).
            max_tokens: Máximo número de tokens.
            **kwargs: Argumentos adicionales pasados al adapter.

        Returns:
            TweetResponse: publishable + text (el tweet) o reason (motivo).
        """
        logger.info(f"[TWEET_GEOPOLITICS] Generating tweet for: {title[:80]}...")

        full_prompt = f"{self.prompt}\n\nTítulo: {title}\nTema: {tema}"
        if context:
            full_prompt += f"\nContenido: {context[:300]}"

        result = self.ai_client.generate(
            prompt=full_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        respuesta = validar_tweet(result, title=title)

        if respuesta.publishable:
            if len(respuesta.text) > self.MAX_CHARS:
                logger.warning(
                    f"[TWEET_GEOPOLITICS] Tweet exceeds {self.MAX_CHARS} chars "
                    f"(got {len(respuesta.text)})"
                )
            logger.info("[TWEET_GEOPOLITICS] Tweet generated successfully")
        else:
            logger.warning(
                f"[TWEET_GEOPOLITICS] Respuesta no publicable para {title[:60]}...: "
                f"{respuesta.reason[:120]}"
            )
        return respuesta

    def generate_batch(
        self,
        items: list[dict],
        temperature: float = 0.2,
        max_tokens: int = 1024,
        **kwargs,
    ) -> list[TweetResponse]:
        """
        Genera múltiples tweets desde una lista de items.

        Args:
            items: Lista de dicts con {"title": str, "tema": str, "context": str}.
            temperature: Temperatura de generación.
            max_tokens: Máximo número de tokens.
            **kwargs: Argumentos adicionales pasados al adapter.

        Returns:
            Lista de TweetResponse (una por item).
        """
        logger.info(f"[TWEET_GEOPOLITICS] Generating {len(items)} tweets")

        respuestas = []
        for item in items:
            respuesta = self.generate(
                title=item.get("title", ""),
                tema=item.get("tema", "Noticias"),
                context=item.get("context", ""),
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            respuestas.append(respuesta)

        return respuestas
