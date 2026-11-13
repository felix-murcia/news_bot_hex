"""Helpers de test para la inyección de IA (B20.4d).

Los use-cases ya no buscan adaptadores por su cuenta (`get_ai_adapter`) ni
importan agentes concretos: reciben un `AiProviders` (VO) con las factories
inyectadas. Los tests construyen ese VO con dobles de prueba.

Uso típico:

    from ai_helpers import build_ai_providers

    use_case = ContentUseCase(
        ...,
        ai_providers=build_ai_providers(),
    )
"""

from unittest.mock import Mock

from src.shared.domain.services.ai_providers import AiProviders
from src.shared.domain.services.tweet_response import TweetResponse


class FakeAgent:
    """Agente de mentira: `generate()` devuelve siempre el mismo valor."""

    def __init__(self, result):
        self._result = result
        self.calls = []

    def generate(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self._result


def build_ai_providers(
    *,
    model=None,
    article_html="<h1>Título de prueba</h1><p>Contenido del artículo de prueba.</p>",
    article_from_content_html="<h1>Título de prueba</h1><p>Contenido del artículo de prueba.</p>",
    tweet_text="Tweet de prueba",
    tweet_response=None,
):
    """Construye un `AiProviders` con dobles de prueba.

    Args:
        model: Modelo de IA que devuelve `adapter_factory`.
        article_html: HTML que devuelve el agente de artículo.
        article_from_content_html: HTML que devuelve el agente de artículo
            desde contenido (audio/video).
        tweet_text: Texto que devuelve el agente de tweet.
        tweet_response: `TweetResponse` que devuelve el agente de tweet de
            geopolítica. Por defecto: publicable con `tweet_text`.

    Returns:
        AiProviders con factories que devuelven dobles configurables.
    """
    model = model if model is not None else Mock()
    respuesta = (
        tweet_response
        if tweet_response is not None
        else TweetResponse(publishable=True, text=tweet_text)
    )

    return AiProviders(
        adapter_factory=Mock(return_value=model),
        article_agent_factory=Mock(return_value=FakeAgent(article_html)),
        article_from_content_agent_factory=Mock(
            return_value=FakeAgent(article_from_content_html)
        ),
        tweet_agent_factory=Mock(return_value=FakeAgent(tweet_text)),
        tweet_geopolitics_agent_factory=Mock(return_value=FakeAgent(respuesta)),
    )
