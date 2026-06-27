"""
Composición de Dependencias (Dependency Injection Container).

Este módulo es el Composition Root de la aplicación — el único lugar
donde se instancian los adaptadores y casos de uso. FastAPI integra
este contenedor de DI via el sistema `Depends()`.

Arquitectura Hexagonal: DIP (Dependency Inversion Principle)
"""

from functools import lru_cache
from fastapi import Depends
from config.settings import Settings
from config.logging_config import get_logger
from src.news.domain.ports import VerifiedNewsRepository

logger = get_logger("news_bot.api.dependencies")


# ============================================================
# Database Dependencies
# ============================================================
def get_db():
    """Obtiene la conexión a la BD (factory para testing/mockeo)."""
    from src.shared.adapters.mongo_db import get_database
    return get_database()


# ============================================================
# Repository Dependencies
# ============================================================
def get_rss_source_repo(db=Depends(get_db)):
    """Repositorio de fuentes RSS."""
    from src.news.infrastructure.adapters import MongoRSSSourceRepository
    from src.news.domain.ports import RSSSourceRepository
    return MongoRSSSourceRepository(db)


def get_article_repo(db=Depends(get_db)):
    """Repositorio de artículos raw."""
    from src.news.infrastructure.adapters import MongoArticleRepository
    from src.news.domain.ports import ArticleRepository
    return MongoArticleRepository(db)


def get_verified_news_repo(db=Depends(get_db)):
    """Repositorio de noticias verificadas."""
    from src.news.infrastructure.adapters import MongoVerifiedNewsRepository
    from src.news.domain.ports import VerifiedNewsRepository
    return MongoVerifiedNewsRepository(db)


def get_published_urls_repo(db=Depends(get_db)):
    """Repositorio de URLs publicadas."""
    from src.news.infrastructure.adapters import MongoPublishedUrlsRepository
    from src.news.domain.ports import PublishedUrlsRepository
    return MongoPublishedUrlsRepository(db)


def get_keywords_repo(db=Depends(get_db)):
    """Repositorio de keywords."""
    from src.news.infrastructure.adapters import MongoKeywordsRepository
    from src.news.domain.ports import KeywordsRepository
    return MongoKeywordsRepository(db)


def get_generated_posts_repo(db=Depends(get_db)):
    """Repositorio de posts generados."""
    from src.news.infrastructure.adapters import MongoGeneratedPostsRepository
    from src.news.domain.ports import GeneratedPostsRepository
    return MongoGeneratedPostsRepository(db)


def get_generated_articles_repo(db=Depends(get_db)):
    """Repositorio de artículos generados."""
    from src.news.infrastructure.adapters import MongoGeneratedArticlesRepository
    from src.news.domain.ports import GeneratedArticlesRepository
    return MongoGeneratedArticlesRepository(db)


def get_scoring_config_repo(db=Depends(get_db)):
    """Repositorio de configuración de scoring."""
    from src.news.infrastructure.adapters import MongoScoringConfigRepository
    from src.news.domain.ports import ScoringConfigRepository
    return MongoScoringConfigRepository(db)


def get_metrics_repository(db=Depends(get_db)):
    """Repositorio de métricas de pipeline."""
    from src.news.infrastructure.adapters.mongo_metrics_repository import MongoMetricsRepository
    from src.news.domain.ports.metrics_repository_port import MetricsRepositoryPort
    return MongoMetricsRepository(db)


def get_timer_config_repository(db=Depends(get_db)):
    """Repositorio de configuración del timer."""
    from src.news.infrastructure.adapters.mongo_timer_config_repository import MongoTimerConfigRepository
    from src.news.domain.ports.timer_config_repository_port import TimerConfigRepositoryPort
    return MongoTimerConfigRepository(db)


# ============================================================
# Adapter Dependencies
# ============================================================
def get_content_extractor():
    """Extractor de contenido desde URLs."""
    from src.news.infrastructure.adapters import JinaContentExtractor
    from src.news.domain.ports import ContentExtractor
    return JinaContentExtractor()


def get_rss_fetcher():
    """Fetcher de feeds RSS."""
    from src.news.infrastructure.adapters import FeedparserRSSFetcher
    from src.news.domain.ports import RSSFetcher
    return FeedparserRSSFetcher()


def get_news_validator():
    """Validador de noticias."""
    from src.news.infrastructure.adapters import ClassicNewsValidatorAdapter
    return ClassicNewsValidatorAdapter()


def get_audio_converter():
    """Conversor de audio (local o externo según AUDIO_CONVERTER_MODE)."""
    from src.shared.infrastructure.composition_root import create_audio_converter
    return create_audio_converter()


def get_audio_post_processor():
    """Post-procesador de audio TTS."""
    from src.shared.infrastructure.composition_root import create_audio_post_processor
    return create_audio_post_processor()


def get_tts_adapter():
    """Adaptador TTS (speaches, coqui o jetson según TTS_MODE)."""
    from src.shared.infrastructure.composition_root import create_tts_adapter
    return create_tts_adapter()


def get_ai_adapter():
    """Adaptador de IA (gemini, openrouter, groq, local según AI_PROVIDER)."""
    from src.shared.infrastructure.composition_root import create_ai_adapter
    return create_ai_adapter()


def get_audio_fetcher():
    """Fetcher de audio desde URLs."""
    from src.shared.infrastructure.composition_root import create_audio_fetcher
    return create_audio_fetcher()


def get_audio_transcriber():
    """Transcriptor de audio."""
    from src.shared.infrastructure.composition_root import create_audio_transcriber
    return create_audio_transcriber()


def get_video_fetcher():
    """Fetcher de video desde URLs."""
    from src.shared.infrastructure.composition_root import create_video_fetcher
    return create_video_fetcher()


def get_video_transcriber():
    """Transcriptor de video."""
    from src.shared.infrastructure.composition_root import create_video_transcriber
    return create_video_transcriber()


# ============================================================
# Use Case Dependencies
# ============================================================
def get_fetch_rss_usecase(
    source_repo=Depends(get_rss_source_repo),
    article_repo=Depends(get_article_repo),
    rss_fetcher=Depends(get_rss_fetcher),
):
    """Use case para obtener noticias RSS."""
    from src.news.application.usecases import FetchRSSNewsUseCase
    return FetchRSSNewsUseCase(source_repo, article_repo, rss_fetcher)


def get_verify_news_usecase(
    article_repo=Depends(get_article_repo),
    verified_repo=Depends(get_verified_news_repo),
    validator=Depends(get_news_validator),
    keywords_repo=Depends(get_keywords_repo),
    scoring_repo=Depends(get_scoring_config_repo),
):
    """Use case para verificar noticias."""
    from src.news.application.usecases import VerifyNewsUseCase
    return VerifyNewsUseCase(
        article_repo, verified_repo, validator, keywords_repo, scoring_repo
    )


def get_full_verify_usecase(
    article_repo=Depends(get_article_repo),
    verified_repo=Depends(get_verified_news_repo),
    published_urls_repo=Depends(get_published_urls_repo),
    keywords_repo=Depends(get_keywords_repo),
    scoring_config_repo=Depends(get_scoring_config_repo),
):
    """Use case para verificación completa."""
    from src.news.application.usecases import FullVerifyNewsUseCase
    from src.news.infrastructure.adapters import MongoFrozenTermsRepository
    return FullVerifyNewsUseCase(
        article_repo=article_repo,
        verified_repo=verified_repo,
        published_urls_repo=published_urls_repo,
        keywords_repo=keywords_repo,
        scoring_config_repo=scoring_config_repo,
        frozen_terms_repo=MongoFrozenTermsRepository(),
    )


def get_article_usecase(
    verified_repo: VerifiedNewsRepository = Depends(get_verified_news_repo),
    generated_articles_repo=Depends(get_generated_articles_repo),
):
    """Use case para generar artículos."""
    from src.news.application.usecases.article import ArticleUseCase
    return ArticleUseCase(verified_repo=verified_repo, generated_articles_repo=generated_articles_repo)


def get_content_usecase(
    verified_repo: VerifiedNewsRepository = Depends(get_verified_news_repo),
    generated_posts_repo=Depends(get_generated_posts_repo),
):
    """Use case para generar contenido (posts sociales)."""
    from src.news.application.usecases.content import ContentUseCase
    return ContentUseCase(verified_repo=verified_repo, generated_posts_repo=generated_posts_repo)


def get_soft_verify_usecase(
    verified_repo: VerifiedNewsRepository = Depends(get_verified_news_repo),
    published_urls_repo=Depends(get_published_urls_repo),
    content_extractor=Depends(get_content_extractor),
):
    """Use case para soft verify (seleccionar noticia para publicar)."""
    from src.news.application.usecases.soft_verify import SoftVerifyUseCase
    return SoftVerifyUseCase(verified_repo, published_urls_repo, content_extractor)


def get_cleanup_usecase(
    verified_repo=Depends(get_verified_news_repo),
    generated_posts_repo=Depends(get_generated_posts_repo),
    generated_articles_repo=Depends(get_generated_articles_repo),
):
    """Use case para limpiar estado de pipeline."""
    from src.news.application.usecases.cleanup import CleanupPipelineUseCase
    return CleanupPipelineUseCase(verified_repo, generated_posts_repo, generated_articles_repo)


# ============================================================
# Port Adapter Dependencies (must be defined before usecases that reference them)
# ============================================================
def get_image_fetcher_port():
    """Port adapter for image fetching (Unsplash + Google)."""
    from src.shared.adapters.image_fetcher_composite import ImageFetcherCompositeAdapter
    return ImageFetcherCompositeAdapter()


def get_image_enricher_port():
    """Port adapter for image enrichment."""
    from src.shared.adapters.image_enricher_adapter import ImageEnricherAdapter
    return ImageEnricherAdapter()


def get_wordpress_publisher_port():
    """Port adapter for WordPress publishing."""
    from src.shared.adapters.wordpress_publisher_adapter import WordPressPublisherAdapter
    return WordPressPublisherAdapter()


def get_social_publisher_ports():
    """List of social publisher port adapters (Bluesky, Mastodon, Facebook)."""
    from src.shared.adapters.publishers.bluesky_publisher_adapter import BlueskyPublisherAdapter
    from src.shared.adapters.publishers.mastodon_publisher_adapter import MastodonPublisherAdapter
    from src.shared.adapters.publishers.facebook_publisher_adapter import FacebookPublisherAdapter

    publishers = []

    try:
        bluesky = BlueskyPublisherAdapter()
        if bluesky.is_available():
            publishers.append(bluesky)
    except Exception as e:
        logger.warning(f"Bluesky publisher not available: {e}")

    try:
        mastodon = MastodonPublisherAdapter()
        if mastodon.is_available():
            publishers.append(mastodon)
    except Exception as e:
        logger.warning(f"Mastodon publisher not available: {e}")

    try:
        facebook = FacebookPublisherAdapter()
        if facebook.is_available():
            publishers.append(facebook)
    except Exception as e:
        logger.warning(f"Facebook publisher not available: {e}")

    return publishers


def get_video_generator_port():
    """Port adapter for video generation."""
    from src.shared.infrastructure.composition_root import create_video_generator
    return create_video_generator()


def get_image_fetcher_usecase(
    generated_posts_repo=Depends(get_generated_posts_repo),
    image_fetcher=Depends(get_image_fetcher_port),
):
    """Use case para descargar imágenes."""
    from src.news.application.usecases.publishing_pipeline import ImageFetcherUseCase
    return ImageFetcherUseCase(generated_posts_repo, image_fetcher)


def get_image_enricher_usecase(
    generated_posts_repo=Depends(get_generated_posts_repo),
    generated_articles_repo=Depends(get_generated_articles_repo),
    image_enricher=Depends(get_image_enricher_port),
):
    """Use case para enriquecer con imágenes."""
    from src.news.application.usecases.publishing_pipeline import ImageEnricherUseCase
    return ImageEnricherUseCase(generated_posts_repo, generated_articles_repo, image_enricher)


def get_publishers_usecase(
    generated_posts_repo=Depends(get_generated_posts_repo),
    generated_articles_repo=Depends(get_generated_articles_repo),
    wordpress_publisher=Depends(get_wordpress_publisher_port),
    social_publishers=Depends(get_social_publisher_ports),
):
    """Use case para publicar en redes sociales."""
    from src.news.application.usecases.publishing_pipeline import PublishersUseCase
    return PublishersUseCase(generated_posts_repo, generated_articles_repo, wordpress_publisher, social_publishers)


# ============================================================
# Process URL ("Procesar URL Concreta") Dependencies
# ============================================================
def get_process_url_job_repository():
    """Job repository port for process_url async tracking (singleton)."""
    from src.news.application.usecases.pipeline_job import _default_repo
    return _default_repo


def get_process_url_content_processor(
    content_extractor=Depends(get_content_extractor),
):
    """Content processor function for process_url (wraps NewsToNewsUseCase)."""
    from src.news.application.usecases.news_to_news import process_news_url
    from config.settings import Settings

    def process_url(url: str):
        """Process URL → extract content + generate article/tweet/TTS/video"""
        return process_news_url(
            url=url,
            content_extractor=content_extractor,
            model_provider=Settings.AI_PROVIDER,
            use_ai=True,
            ai_config={},
            force_extract=True,
        )

    return process_url


def get_process_url_usecase(
    content_extractor=Depends(get_content_extractor),
    metrics_repo=Depends(get_metrics_repository),
):
    """ProcessUrlPipeline - same pipeline as automatic, starting from URL extraction."""
    from src.news.application.usecases.process_url_pipeline import ProcessUrlPipeline

    pipeline = ProcessUrlPipeline(
        content_extractor=content_extractor,
        metrics_repo=metrics_repo,
    )
    return pipeline.execute


def get_process_url_job_coordinator(
    job_repository=Depends(get_process_url_job_repository),
    process_url_usecase=Depends(get_process_url_usecase),
):
    """ProcessUrlJobCoordinator with all dependencies injected."""
    from src.news.application.usecases.process_url_executor import (
        ProcessUrlJobCoordinator,
    )

    return ProcessUrlJobCoordinator(
        job_repository=job_repository,
        process_url_usecase=process_url_usecase,
    )
