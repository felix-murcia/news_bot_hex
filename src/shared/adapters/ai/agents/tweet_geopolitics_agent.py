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
        max_tokens: int = 512,
        **kwargs,
    ) -> TweetResponse:
        """
        512 tokens: valor lógico para tweet (JSON con publicable + tweet 280 chars).
        El OpenRouterAdapter suma internamente OPENROUTER_REASONING_BUFFER (default 1024)
        para cubrir reasoning tokens en modelos free.
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

        # Seguridad extra: si la respuesta cruda parece JSON roto (tiene { pero
        # validar_tweet no pudo extraer JSON válido), rechazarla como no publicable.
        # Esto evita que JSON truncado ("{"publicable": true, "tweet": "Hola...") se
        # publique como texto plano.
        if respuesta.publishable:
            raw_stripped = result.strip()
            # Caso 1: empieza por { y contiene "publicable" (contrato del agente)
            # Caso 2: solo { o } (JSON obviamente roto)
            # Caso 3: parece JSON (tiene { y } pero ratio de símbolos alto)
            looks_like_broken_json = False
            if raw_stripped.startswith("{") and "publicable" in raw_stripped:
                looks_like_broken_json = True
            elif raw_stripped in ("{", "}", "{}", '{"publicable"', '{"tweet"'):
                looks_like_broken_json = True
            elif raw_stripped.startswith("{") and raw_stripped.endswith("}") and len(raw_stripped) > 10:
                # JSON-like pero validar_tweet no lo parseó -> probablemente truncado
                alnum = sum(c.isalnum() or c.isspace() for c in raw_stripped)
                symbols = len(raw_stripped) - alnum
                if symbols / len(raw_stripped) > 0.3:
                    looks_like_broken_json = True
            
            if looks_like_broken_json:
                logger.warning(
                    f"[TWEET_GEOPOLITICS] Respuesta parece JSON malformado, "
                    f"rechazando: {raw_stripped[:120]}"
                )
                return TweetResponse(
                    publishable=False,
                    reason="Respuesta parece JSON malformado (truncado o inválido)"
                )

        if respuesta.publishable:
            if len(respuesta.text) > self.MAX_CHARS:
                logger.warning(
                    f"[TWEET_GEOPOLITICS] Tweet exceeds {self.MAX_CHARS} chars "
                    f"(got {len(respuesta.text)})"
                )
            logger.info("[TWEET_GEOPOLITICS] Tweet generated successfully")
        else:
            logger.error(
                f"[TWEET_GEOPOLITICS] Respuesta no publicable para '{title[:80]}...': "
                f"{respuesta.reason[:160]}. Texto crudo (primeros 200 chars): {repr(result[:200])}"
            )
        return respuesta

    def generate_batch(
        self,
        items: list[dict],
        temperature: float = 0.2,
        max_tokens: int = 512,
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
