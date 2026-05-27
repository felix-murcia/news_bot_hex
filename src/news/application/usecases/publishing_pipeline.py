"""Publishing pipeline usecase - images, enrichment, and distribution."""

from config.logging_config import get_logger
from src.news.domain.ports import (
    GeneratedPostsRepository,
    GeneratedArticlesRepository,
)

logger = get_logger("news_bot.usecase.publishing")


class ImageFetcherUseCase:
    """Fetch images from web sources."""

    def __init__(self, generated_posts_repo: GeneratedPostsRepository):
        self._generated_posts_repo = generated_posts_repo

    def execute(self) -> dict:
        """Fetch and cache images for generated posts."""
        logger.info("[IMAGES] Iniciando búsqueda de imágenes")

        try:
            from src.shared.adapters.google_images_fetcher import run as fetch_google_images

            # Run Google Images fetcher
            fetch_google_images()
            logger.info("[IMAGES] ✅ Google Images fetcher completado")

        except Exception as e:
            logger.warning(f"[IMAGES] ⚠️ Error en Google Images fetcher: {e}")

        return {"status": "ok", "message": "Image fetching completed"}


class ImageEnricherUseCase:
    """Enrich posts and articles with images."""

    def __init__(
        self,
        generated_posts_repo: GeneratedPostsRepository,
        generated_articles_repo: GeneratedArticlesRepository,
    ):
        self._generated_posts_repo = generated_posts_repo
        self._generated_articles_repo = generated_articles_repo

    def execute(self) -> dict:
        """Enrich generated content with images."""
        logger.info("[ENRICH] Iniciando enriquecimiento con imágenes")

        try:
            from src.shared.adapters.image_enricher import enrich_posts, enrich_articles

            # Enrich posts
            try:
                posts = self._generated_posts_repo.load_all()
                if posts:
                    enrich_posts(posts)
                    self._generated_posts_repo.save_all(posts)
                    logger.info(f"[ENRICH] ✅ Enriquecidos {len(posts)} posts con imágenes")
            except Exception as e:
                logger.warning(f"[ENRICH] ⚠️ Error enriqueciendo posts: {e}")

            # Enrich articles
            try:
                articles = self._generated_articles_repo.load_all()
                if articles:
                    enrich_articles(articles)
                    self._generated_articles_repo.save_all(articles)
                    logger.info(f"[ENRICH] ✅ Enriquecidos {len(articles)} artículos con imágenes")
            except Exception as e:
                logger.warning(f"[ENRICH] ⚠️ Error enriqueciendo artículos: {e}")

        except Exception as e:
            logger.warning(f"[ENRICH] ⚠️ Error en enriquecimiento: {e}")

        return {"status": "ok", "message": "Image enrichment completed"}


class PublishersUseCase:
    """Publish content to social networks and WordPress."""

    def __init__(
        self,
        generated_posts_repo: GeneratedPostsRepository,
        generated_articles_repo: GeneratedArticlesRepository,
    ):
        self._generated_posts_repo = generated_posts_repo
        self._generated_articles_repo = generated_articles_repo

    def execute(self) -> dict:
        """Publish to all configured platforms."""
        logger.info("[PUBLISH] Iniciando publicación en redes sociales")

        results = {}

        # Publish to WordPress
        try:
            from src.shared.adapters.wordpress_publisher import run as publish_wordpress
            publish_wordpress()
            logger.info("[PUBLISH] ✅ WordPress publicado")
            results["wordpress"] = "ok"
        except Exception as e:
            logger.warning(f"[PUBLISH] ⚠️ Error publicando a WordPress: {e}")
            results["wordpress"] = f"error: {str(e)}"

        # Publish to Bluesky
        try:
            from src.shared.adapters.bluesky_publisher import run as publish_bluesky
            publish_bluesky()
            logger.info("[PUBLISH] ✅ Bluesky publicado")
            results["bluesky"] = "ok"
        except Exception as e:
            logger.warning(f"[PUBLISH] ⚠️ Error publicando a Bluesky: {e}")
            results["bluesky"] = f"error: {str(e)}"

        # Publish to Mastodon
        try:
            from src.shared.adapters.mastodon_publisher import run as publish_mastodon
            publish_mastodon()
            logger.info("[PUBLISH] ✅ Mastodon publicado")
            results["mastodon"] = "ok"
        except Exception as e:
            logger.warning(f"[PUBLISH] ⚠️ Error publicando a Mastodon: {e}")
            results["mastodon"] = f"error: {str(e)}"

        # Publish to Facebook
        try:
            from src.shared.adapters.facebook_publisher import run as publish_facebook
            publish_facebook()
            logger.info("[PUBLISH] ✅ Facebook publicado")
            results["facebook"] = "ok"
        except Exception as e:
            logger.warning(f"[PUBLISH] ⚠️ Error publicando a Facebook: {e}")
            results["facebook"] = f"error: {str(e)}"

        logger.info("[PUBLISH] ========== Publicación completada ==========")
        return {"status": "ok", "message": "Publishing completed", "results": results}
