from typing import Callable, Dict, List, Optional

import logging
from src.news.domain.ports import VerifiedNewsRepository, GeneratedPostsRepository
from src.shared.domain.services.ai_providers import AiProviders

logger = logging.getLogger(__name__)
POST_LIMITS = {
    "bluesky": 300,
    "twitter": 280,
    "mastodon": 500,
    "facebook": 63206,
}

class ContentUseCase:
    """Caso de uso para generar contenido (tweets/posts) para redes sociales (DIP: inyección de repositorio)."""

    def __init__(
        self,
        verified_repo: VerifiedNewsRepository,
        generated_posts_repo: GeneratedPostsRepository,
        ai_providers: AiProviders,
        social_truncator: Callable[..., str],
        post_editor: Callable[..., str],
        cache_loader: Callable[..., tuple[Optional[str], str]],
        network: str = "bluesky",
        use_ai: bool = True,
        model_provider: str | None = None,
        ai_model=None,
        mode: str = "news",
    ):
        if ai_providers is None:
            raise ValueError("ai_providers es requerido")
        self.verified_repo = verified_repo
        self.generated_posts_repo = generated_posts_repo
        self._ai_providers = ai_providers
        self._social_truncator = social_truncator
        self._post_editor = post_editor
        self._cache_loader = cache_loader
        self.network = network
        self.mode = mode
        self.MAX_CHARS = POST_LIMITS.get(network, 280)
        self.use_ai = use_ai
        self.model_provider = model_provider
        self.ai_model = ai_model

    def _get_ai_model(self):
        """Obtiene el modelo de IA (lazy loading)."""
        if self.ai_model is None:
            if self.use_ai:
                provider = self.model_provider  # Puede ser None; el factory resuelve el default
            else:
                provider = "mock"
            self.ai_model = self._ai_providers.adapter_factory(provider)
            logger.info(f"[CONTENT] Adapter '{provider or 'auto'}' instanciado")
        return self.ai_model

    def _get_verified_news(self) -> List[Dict]:
        """Obtiene noticias verificadas usando el repositorio inyectado (DIP)."""
        try:
            articles = self.verified_repo.get_all_news()
            return [a.to_dict() for a in articles]
        except Exception as e:
            logger.error(f"[CONTENT] Error cargando verified_news: {e}")
            return []

    def _load_posts(self) -> List[Dict]:
        try:
            return self.generated_posts_repo.load_all()
        except Exception as e:
            logger.error(f"[CONTENT] Error cargando posts: {e}")
            return []

    def _save_posts(self, posts: List[Dict]):
        try:
            self.generated_posts_repo.save_all(posts)
            logger.info(f"[CONTENT] Guardados {len(posts)} posts en MongoDB")
        except Exception as e:
            logger.error(f"[CONTENT] Error guardando posts: {e}")

    def _generate_tweet_ai(self, news_item: Dict) -> str:
        """Genera el tweet con IA y lo devuelve.

        El agente responde con JSON {"publicable": bool, ...} (ver
        src/shared/domain/services/tweet_response.py): la publicabilidad la
        declara el modelo y la decide `validar_tweet`, sin listas de frases.
        Si no hay tweet publicable se lanza RuntimeError y no se publica nada.
        """
        title = news_item.get("title", "")
        tema = news_item.get("tema", "Noticias")
        desc = news_item.get("desc", "")[:200]

        model = self._get_ai_model()
        agent = self._ai_providers.tweet_geopolitics_agent_factory(model)
        respuesta = agent.generate(title=title, tema=tema, context=desc)

        if not respuesta.publishable:
            logger.error(
                f"[CONTENT] La IA no generó un tweet publicable para: "
                f"{title[:80]}... (tema: {tema}). Motivo: {respuesta.reason[:160]}"
            )
            raise RuntimeError(
                f"La IA no generó un tweet publicable para '{title[:80]}...': "
                f"{respuesta.reason}. No se publica contenido de baja calidad."
            )

        tweet = self._social_truncator(respuesta.text, limit=self.MAX_CHARS)
        tweet = tweet.strip()

        # Aplicar post-edición automática
        tweet = self._post_editor(tweet)

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
            content, status = self._cache_loader(url, max_age_hours=24)
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
            item_title = news_item.get("title", "")

            try:
                if self.use_ai:
                    tweet = self._generate_tweet_ai(news_item)
                else:
                    tweet = self._generate_tweet_fallback(news_item)
            except Exception as e:
                logger.warning(
                    f"[CONTENT] ⏭️ Se omite la noticia '{item_title[:80]}...' ({url}) "
                    f"por error en la generación del tweet: {e}"
                )
                continue

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
        ai_providers: AiProviders,
        verified_repo: VerifiedNewsRepository,
        generated_posts_repo: GeneratedPostsRepository,
        social_truncator: Callable[..., str],
        post_editor: Callable[..., str],
        cache_loader: Callable[..., tuple[Optional[str], str]],
        network: str = "bluesky",
        use_gemini: bool = True,
        mode: str = "news",
        model_provider: Optional[str] = None,
        **kwargs,
    ):
        resolved_provider = model_provider or ("local" if use_gemini else "mock")
        super().__init__(
            verified_repo=verified_repo,
            generated_posts_repo=generated_posts_repo,
            ai_providers=ai_providers,
            social_truncator=social_truncator,
            post_editor=post_editor,
            cache_loader=cache_loader,
            network=network,
            use_ai=use_gemini,
            model_provider=resolved_provider,
            mode=mode,
            **kwargs,
        )


def run_content(
    llm=None,
    network: str = "bluesky",
    use_gemini: bool = True,
    mode: str = "news",
    model_provider: str = None,
    *,
    ai_providers: AiProviders,
    generated_posts_repo: GeneratedPostsRepository,
    verified_news_repo: VerifiedNewsRepository,
    social_truncator: Callable[..., str],
    post_editor: Callable[..., str],
    cache_loader: Callable[..., tuple[Optional[str], str]],
) -> List[Dict]:
    """Función principal para generar tweets."""
    # Pasa model_provider tal cual (puede ser None); el factory resuelve el default
    provider_for_log = model_provider or "auto"
    logger.info(f"[CONTENT] Ejecutando (provider: {provider_for_log}, red: {network})")
    use_case = ContentUseCase(
        verified_repo=verified_news_repo,
        generated_posts_repo=generated_posts_repo,
        ai_providers=ai_providers,
        social_truncator=social_truncator,
        post_editor=post_editor,
        cache_loader=cache_loader,
        network=network,
        use_ai=use_gemini,
        model_provider=model_provider,
        mode=mode,
    )
    return use_case.execute()


def main():
    import argparse
    from config.settings import Settings
    from src.shared.infrastructure.composition_root import (  # TODO B11c (main/argparse)
        create_ai_providers,
        create_generated_posts_repository,
        create_verified_news_repository,
    )

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

    social_truncator = __import__(
        "src.shared.adapters.social_post_adapter", fromlist=["truncate_social_post"]
    ).truncate_social_post
    post_editor = __import__(
        "src.shared.adapters.content_post_editor", fromlist=["post_edit_content"]
    ).post_edit_content
    cache_loader = __import__(
        "src.shared.adapters.cache_manager", fromlist=["load_content_from_cache"]
    ).load_content_from_cache

    results = run_content(
        network=args.network,
        use_gemini=not args.local,
        mode=args.mode,
        model_provider=args.model,
        ai_providers=create_ai_providers(),
        generated_posts_repo=create_generated_posts_repository(),
        verified_news_repo=create_verified_news_repository(),
        social_truncator=social_truncator,
        post_editor=post_editor,
        cache_loader=cache_loader,
    )

    if results:
        print(f"✅ {len(results)} tweet(s) generado(s)")
        for i, post in enumerate(results[:3], 1):
            print(f"  {i}. {post.get('tweet', '')[:80]}...")
    else:
        print("⚠️ No se generaron tweets")


if __name__ == "__main__":
    main()
