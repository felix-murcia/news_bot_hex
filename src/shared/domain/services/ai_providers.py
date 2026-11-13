"""Value object con las fábricas de IA y de agentes (B20.4d).

`application/` no puede importar `src.shared.adapters.ai.*`: los adaptadores
concretos (adaptadores de proveedor y agentes que cargan prompts del disco)
se inyectan como factories a través de este VO. Un solo parámetro travels por
todo el pipeline en lugar de cinco.

Las factories de agentes (no instancias) preservan el comportamiento actual:
cada llamada construye un agente nuevo y relee su prompt `.md` del disco.
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class AiProviders:
    """Fábricas de adaptadores de IA y de agentes de contenido.

    Attributes:
        adapter_factory: `f(provider) -> AIModelPort`.
        article_agent_factory: `f(ai_client) -> agente de artículo`.
        article_from_content_agent_factory: `f(ai_client, source_type) -> agente
            de artículo desde contenido (audio/video)`.
        tweet_agent_factory: `f(ai_client) -> agente de tweet`.
        tweet_geopolitics_agent_factory: `f(ai_client) -> agente de tweet de
            geopolítica`.
    """

    adapter_factory: Callable[[str], Any]
    article_agent_factory: Callable[[Any], Any]
    article_from_content_agent_factory: Callable[[Any, str], Any]
    tweet_agent_factory: Callable[[Any], Any]
    tweet_geopolitics_agent_factory: Callable[[Any], Any]
