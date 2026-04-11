"""
AI Agents Package.

Agentes genéricos e independientes del proveedor de IA.
Cada agente utiliza AIModelPort para interactuar con cualquier proveedor.
"""

from src.shared.adapters.ai.agents.article_agent import ArticleAgent
from src.shared.adapters.ai.agents.tweet_agent import TweetAgent
from src.shared.adapters.ai.agents.article_from_content_agent import ArticleFromContentAgent
from src.shared.adapters.ai.agents.tweet_geopolitics_agent import TweetGeopoliticsAgent

__all__ = [
    "ArticleAgent",
    "TweetAgent",
    "ArticleFromContentAgent",
    "TweetGeopoliticsAgent",
]
