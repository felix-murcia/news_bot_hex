"""Publishing pipeline usecase - images, enrichment, and distribution."""

from typing import List

from config.logging_config import get_logger
from src.news.domain.ports import (
    GeneratedPostsRepository,
    GeneratedArticlesRepository,
)
from src.shared.domain.ports.image_fetcher_port import ImageFetcherPort
from src.shared.domain.ports.image_enricher_port import ImageEnricherPort
from src.shared.domain.ports.social_publisher_port import SocialPublisherPort
from src.shared.domain.ports.wordpress_publisher_port import WordPressPublisherPort

logger = get_logger("news_bot.usecase.publishing")


class ImageFetcherUseCase:
    """Fetch images from web sources."""

    def __init__(
        self,
        generated_posts_repo: GeneratedPostsRepository,
        image_fetcher: ImageFetcherPort,
    ):
        self._generated_posts_repo = generated_posts_repo
        self._image_fetcher = image_fetcher

    def execute(self) -> dict:
        """Fetch and cache images for generated posts."""
        logger.info("[IMAGES] Iniciando búsqueda de imágenes")
        try:
            posts = self._generated_posts_repo.load_all()
            if posts:
                self._image_fetcher.fetch(posts)
            logger.info("[IMAGES] ✅ Image fetcher completado")
        except Exception as e:
            logger.warning(f"[IMAGES] ⚠️ Error en image fetcher: {e}")
        return {"status": "ok", "message": "Image fetching completed"}


class ImageEnricherUseCase:
    """Enrich posts and articles with images."""

    def __init__(
        self,
        generated_posts_repo: GeneratedPostsRepository,
        generated_articles_repo: GeneratedArticlesRepository,
        image_enricher: ImageEnricherPort,
    ):
        self._generated_posts_repo = generated_posts_repo
        self._generated_articles_repo = generated_articles_repo
        self._image_enricher = image_enricher

    def execute(self) -> dict:
        """Enrich generated content with images."""
        logger.info("[ENRICH] Iniciando enriquecimiento con imágenes")
        try:
            posts = self._generated_posts_repo.load_all() or []
            articles = self._generated_articles_repo.load_all() or []
            self._image_enricher.enrich(posts, articles)
            if posts:
                self._generated_posts_repo.save_all(posts)
            if articles:
                self._generated_articles_repo.save_all(articles)
            logger.info(f"[ENRICH] ✅ Enriquecidos {len(posts)} posts y {len(articles)} artículos")
        except Exception as e:
            logger.warning(f"[ENRICH] ⚠️ Error en enriquecimiento: {e}")
        return {"status": "ok", "message": "Image enrichment completed"}


class PublishersUseCase:
    """Publish content to social networks and WordPress."""

    def __init__(
        self,
        generated_posts_repo: GeneratedPostsRepository,
        generated_articles_repo: GeneratedArticlesRepository,
        wordpress_publisher: WordPressPublisherPort = None,
        social_publishers: List[SocialPublisherPort] = None,
    ):
        self._generated_posts_repo = generated_posts_repo
        self._generated_articles_repo = generated_articles_repo
        self._wordpress_publisher = wordpress_publisher
        self._social_publishers = social_publishers or []

    def execute(self) -> dict:
        """Publish to all configured platforms."""
        logger.info("[PUBLISH] Iniciando publicación en redes sociales")
        results = {}

        if self._wordpress_publisher:
            try:
                result = self._wordpress_publisher.publish()
                logger.info("[PUBLISH] ✅ WordPress publicado")
                results["wordpress"] = result.get("status", "ok")
            except Exception as e:
                logger.warning(f"[PUBLISH] ⚠️ Error publicando a WordPress: {e}")
                results["wordpress"] = f"error: {str(e)}"

        posts = self._generated_posts_repo.load_all() or []
        for publisher in self._social_publishers:
            platform = publisher.__class__.__name__.replace("PublisherAdapter", "").lower()
            try:
                for post in posts:
                    publisher.publish(post)
                logger.info(f"[PUBLISH] ✅ {platform} publicado")
                results[platform] = "ok"
            except Exception as e:
                logger.warning(f"[PUBLISH] ⚠️ Error publicando a {platform}: {e}")
                results[platform] = f"error: {str(e)}"

        logger.info("[PUBLISH] ========== Publicación completada ==========")
        return {"status": "ok", "message": "Publishing completed", "results": results}
