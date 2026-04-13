import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger("news_bot.usecase.content")

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"
POSTS_PATH = DATA_DIR / "generated_posts.json"

POST_LIMITS = {
    "bluesky": 300,
    "twitter": 280,
    "mastodon": 500,
    "facebook": 63206,
}


class ContentUseCase:
    """Caso de uso para generar contenido (tweets/posts) para redes sociales."""

    def __init__(
        self,
        network: str = "bluesky",
        use_ai: bool = True,
        ai_config: Optional[dict] = None,
        model_provider: str = Settings.AI_PROVIDER,
        ai_model=None,
        mode: str = "news",
    ):
        self.network = network
        self.mode = mode
        self.MAX_CHARS = POST_LIMITS.get(network, 280)
        self.use_ai = use_ai
        self.ai_config = ai_config or {}
        self.model_provider = model_provider
        self.ai_model = ai_model

    def _get_ai_model(self):
        """Obtiene el modelo de IA (lazy loading)."""
        if self.ai_model is None:
            from src.shared.adapters.ai.ai_factory import get_ai_adapter

            if self.use_ai:
                provider = self.model_provider
            else:
                provider = "mock"
            self.ai_model = get_ai_adapter(provider, self.ai_config)
            logger.info(f"[CONTENT] Adapter '{provider}' instanciado")
        return self.ai_model

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

    def _generate_tweet_ai(self, news_item: Dict) -> str:
        from src.shared.adapters.ai.agents import TweetGeopoliticsAgent

        title = news_item.get("title", "")
        tema = news_item.get("tema", "Noticias")
        desc = news_item.get("desc", "")[:200]

        model = self._get_ai_model()
        agent = TweetGeopoliticsAgent(model)
        tweet = agent.generate(title=title, tema=tema, context=desc)

        from src.shared.utils.tweet_truncation import truncate_social_post

        tweet = truncate_social_post(tweet, limit=self.MAX_CHARS)
        tweet = tweet.strip()

        # Aplicar post-edición automática
        from src.shared.utils.content_post_editor import post_edit_content
        tweet = post_edit_content(tweet)

        if not tweet:
            logger.error(
                f"[CONTENT] Tweet generado vacío para: {title[:80]}... "
                f"(tema: {tema}). Se aborta la publicación."
            )
            raise RuntimeError(
                f"Tweet vacío para '{title[:80]}...'. No se publica contenido de baja calidad."
            )

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
        logger.info(
            f"[CONTENT] Ejecutando para {self.network} (provider: {self.model_provider})"
        )

        news_list = self._get_verified_news()
        if not news_list:
            logger.warning("[CONTENT] No hay noticias verificadas")
            return []

        posts = []
        for news_item in news_list[:limit]:
            url = news_item.get("url", "")

            if self.use_ai:
                tweet = self._generate_tweet_ai(news_item)
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


class ContentGeminiUseCase(ContentUseCase):
    """Legacy compatibility wrapper."""

    def __init__(
        self,
        network: str = "bluesky",
        use_gemini: bool = True,
        gemini_config: Optional[dict] = None,
        mode: str = "news",
        **kwargs,
    ):
        model_provider = Settings.AI_PROVIDER if use_gemini else "mock"
        super().__init__(
            network=network,
            use_ai=use_gemini,
            ai_config=gemini_config,
            model_provider=model_provider,
            mode=mode,
            **kwargs,
        )


def run_content(
    llm=None,
    network: str = "bluesky",
    use_gemini: bool = True,
    gemini_config: Optional[Dict] = None,
    mode: str = "news",
    model_provider: str = Settings.AI_PROVIDER,
) -> List[Dict]:
    """Función principal para generar tweets."""
    logger.info(f"[CONTENT] Ejecutando (provider: {model_provider}, red: {network})")
    use_case = ContentUseCase(
        network=network,
        use_ai=use_gemini,
        ai_config=gemini_config,
        model_provider=model_provider,
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
    parser.add_argument(
        "--model",
        type=str,
        default=Settings.AI_PROVIDER,
        choices=Settings.SUPPORTED_AI_PROVIDERS,
        help="Modelo de IA a usar",
    )

    args = parser.parse_args()

    results = run_content(
        network=args.network,
        use_gemini=not args.local,
        mode=args.mode,
        model_provider=args.model,
    )

    if results:
        print(f"✅ {len(results)} tweet(s) generado(s)")
        for i, post in enumerate(results[:3], 1):
            print(f"  {i}. {post.get('tweet', '')[:80]}...")
    else:
        print("⚠️ No se generaron tweets")


if __name__ == "__main__":
    main()
