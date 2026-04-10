import os
import logging
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("news_bot")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"
POSTS_PATH = DATA_DIR / "generated_posts.json"

POST_LIMITS = {
    "bluesky": 300,
    "twitter": 280,
    "mastodon": 500,
    "facebook": 63206,
}


class ContentGeminiUseCase:
    """Caso de uso para generar contenido (tweets/posts) para redes sociales."""

    def __init__(
        self,
        network: str = "bluesky",
        use_gemini: bool = True,
        gemini_config: dict = None,
        mode: str = "news",
    ):
        self.network = network
        self.mode = mode
        self.MAX_CHARS = POST_LIMITS.get(network, 280)
        self.use_gemini = use_gemini
        self.gemini_config = gemini_config or {}
        self.gemini_client = None
        self.llm = None

        if self.use_gemini:
            self._init_gemini()
        else:
            self._init_local()

    def _init_gemini(self):
        try:
            from src.shared.adapters.gemini_client import get_gemini_client

            self.gemini_client = get_gemini_client(self.gemini_config)
            logger.info(f"[CONTENT] ✅ Gemini Flash activado ({self.network})")
        except Exception as e:
            logger.error(f"[CONTENT] ❌ Error Gemini: {e}")
            self.use_gemini = False
            self._init_local()

    def _init_local(self):
        logger.info("[CONTENT] Modo local activado")

    def _get_verified_news(self) -> List[Dict]:
        try:
            from src.shared.adapters.mongo_db import get_database

            db = get_database()
            coll = db["verified_news"]
            news = list(coll.find({}))
            for n in news:
                n.pop("_id", None)
            return news
        except Exception as e:
            logger.error(f"[CONTENT] Error cargando verified_news: {e}")
            return []

    def _load_posts(self) -> List[Dict]:
        try:
            from src.shared.adapters.mongo_db import get_database

            db = get_database()
            coll = db["generated_posts"]
            posts = list(coll.find({}))
            for p in posts:
                p.pop("_id", None)
            return posts
        except Exception as e:
            logger.error(f"[CONTENT] Error cargando posts: {e}")
            return []

    def _save_posts(self, posts: List[Dict]):
        try:
            from src.shared.adapters.mongo_db import get_database

            db = get_database()
            coll = db["generated_posts"]
            coll.delete_many({})
            if posts:
                coll.insert_many(posts)
            logger.info(f"[CONTENT] Guardados {len(posts)} posts en MongoDB")
        except Exception as e:
            logger.error(f"[CONTENT] Error guardando posts: {e}")

    def _generate_tweet_gemini(self, news_item: Dict) -> str:
        title = news_item.get("title", "")
        tema = news_item.get("tema", "Noticias")
        url = news_item.get("url", "")

        prompt = f"""# ROLE: EDITOR JEFE DE GEOPOLÍTICA – THE ECONOMIST
Actúa como editor senior de la sección de geopolítica de The Economist. Tu función es transformar contenido en un tweet periodístico profesional, preciso y objetivo.

# INPUT
Título: {title}
Tema: {tema}

# HARD RULES (OBLIGATORIAS)
- Estilo escrito periodístico (The Economist, FT, El País).
- Objetividad total: no opiniones, no especulación, no sensacionalismo.
- Tercera persona, tono formal, sin coloquialismos.

# TWEET FORMAT (ESTRUCTURA OBLIGATORIA)
[L1] Hecho principal conciso y relevante (incluye datos si existen)
[L2] Contexto, impacto o consecuencia
[HASHTAGS] 2–3 hashtags específicos del tema

# NEGATIVE EXAMPLES (PROHIBIDO)
- "Descubre los detalles"
- "Link a la noticia"
- "Más información"
- Llamadas a la acción

# TASK
Genera EXACTAMENTE UN tweet periodístico profesional en español.
Máximo {self.MAX_CHARS} caracteres.
No incluyas prefacios, explicaciones ni texto adicional.
Empieza directamente con el tweet.

TWEET:"""

        try:
            result = self.gemini_client.generate(prompt)
            tweet = result.strip()
            if len(tweet) > self.MAX_CHARS:
                tweet = tweet[: self.MAX_CHARS - 3] + "..."
            return tweet
        except Exception as e:
            logger.error(f"[CONTENT] Error generando tweet: {e}")
            return self._generate_tweet_fallback(news_item)

    def _generate_tweet_fallback(self, news_item: Dict) -> str:
        title = news_item.get("title", "")[:200]
        tema = news_item.get("tema", "Noticias")

        tweet = f"📰 {title}\n\n#{tema.replace(' ', '')}"

        if len(tweet) > self.MAX_CHARS:
            tweet = tweet[: self.MAX_CHARS - 3] + "..."

        return tweet

    def _load_content_from_cache(self, url: str) -> Optional[str]:
        try:
            from src.shared.adapters.cache_manager import load_content_from_cache

            content, status = load_content_from_cache(url, max_age_hours=24)
            if content and status == "cache_hit":
                return content
            return None
        except Exception:
            return None

    def execute(self, limit: int = 1) -> List[Dict]:
        logger.info(f"[CONTENT] Ejecutando para {self.network} (modo: {self.mode})")

        news_list = self._get_verified_news()
        if not news_list:
            logger.warning("[CONTENT] No hay noticias verificadas")
            return []

        posts = []
        for news_item in news_list[:limit]:
            url = news_item.get("url", "")

            if self.use_gemini and self.gemini_client:
                tweet = self._generate_tweet_gemini(news_item)
            else:
                tweet = self._generate_tweet_fallback(news_item)

            post = {
                "tweet": tweet,
                "title": news_item.get("title", ""),
                "url": url,
                "source": news_item.get("source", ""),
                "source_type": news_item.get("source_type", "news_man"),
                "tema": news_item.get("tema", "Noticias"),
                "image_url": news_item.get("image_url", ""),
                "network": self.network,
            }
            posts.append(post)
            logger.info(f"[CONTENT] ✅ Tweet generado: {tweet[:60]}...")

        if posts:
            self._save_posts(posts)

        return posts


def run_content(
    llm=None,
    network: str = "bluesky",
    use_gemini: bool = True,
    gemini_config: Dict = None,
    mode: str = "news",
) -> List[Dict]:
    """Función principal para generar tweets."""
    logger.info(f"[CONTENT] Ejecutando (Gemini: {use_gemini}, red: {network})")
    use_case = ContentGeminiUseCase(
        network=network,
        use_gemini=use_gemini,
        gemini_config=gemini_config,
        mode=mode,
    )
    return use_case.execute()


def run(llm=None):
    """Wrapper para compatibilidad de pipeline."""
    return run_content(llm=llm)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generador de tweets")
    parser.add_argument("--local", action="store_true", help="Usar solo modelo local")
    parser.add_argument("--network", type=str, default="bluesky", help="Red social")
    parser.add_argument(
        "--mode", type=str, default="news", choices=["news", "audio", "video"]
    )

    args = parser.parse_args()

    results = run_content(
        network=args.network,
        use_gemini=not args.local,
        mode=args.mode,
    )

    if results:
        print(f"✅ {len(results)} tweet(s) generado(s)")
        for i, post in enumerate(results[:3], 1):
            print(f"  {i}. {post.get('tweet', '')[:80]}...")
    else:
        print("⚠️ No se generaron tweets")
