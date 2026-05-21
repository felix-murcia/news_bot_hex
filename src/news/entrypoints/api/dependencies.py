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
    return FullVerifyNewsUseCase(
        article_repo=article_repo,
        verified_repo=verified_repo,
        published_urls_repo=published_urls_repo,
        keywords_repo=keywords_repo,
        scoring_config_repo=scoring_config_repo,
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


def get_image_fetcher_usecase(
    generated_posts_repo=Depends(get_generated_posts_repo),
):
    """Use case para descargar imágenes."""
    from src.news.application.usecases.publishing_pipeline import ImageFetcherUseCase
    return ImageFetcherUseCase(generated_posts_repo)


def get_image_enricher_usecase(
    generated_posts_repo=Depends(get_generated_posts_repo),
    generated_articles_repo=Depends(get_generated_articles_repo),
):
    """Use case para enriquecer con imágenes."""
    from src.news.application.usecases.publishing_pipeline import ImageEnricherUseCase
    return ImageEnricherUseCase(generated_posts_repo, generated_articles_repo)


def get_publishers_usecase(
    generated_posts_repo=Depends(get_generated_posts_repo),
    generated_articles_repo=Depends(get_generated_articles_repo),
):
    """Use case para publicar en redes sociales."""
    from src.news.application.usecases.publishing_pipeline import PublishersUseCase
    return PublishersUseCase(generated_posts_repo, generated_articles_repo)
