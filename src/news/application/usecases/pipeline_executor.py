"""Async pipeline executor - thin wrapper that starts PipelineRunner in a daemon thread."""

import threading
from typing import Optional

from src.news.domain.ports import ContentExtractor
from src.shared.domain.services.ai_providers import AiProviders

from src.news.application.usecases.pipeline_job import (
    add_step,  # noqa: F401 - re-exported for test patching
    update_job_status,  # noqa: F401 - re-exported for test patching
)
from src.news.application.usecases.pipeline_runner import (
    PipelineContext,
    PipelineRunner,
    logger,
)

# Global execution lock - only one pipeline execution at a time
_execution_lock = threading.Lock()


def execute_pipeline_async(
    job_id,
    generated_articles_repo,
    generated_posts_repo,
    verified_news_repo,
    rss_fetch_runner,
    prepare_articles_runner,
    full_verify_runner,
    metrics_repo,
    social_publisher,
    tts_usecase,
    image_unsplash_runner,
    image_google_runner,
    image_enricher_runner,
    wordpress_runner,
    video_generator_factory,
    *,
    social_truncator,
    post_editor,
    cache_loader,
    seo_helpers,
    ai_providers: AiProviders,
    content_extractor: Optional[ContentExtractor] = None,
) -> bool:
    """
    Execute pipeline in background thread with job tracking and metrics collection.

    Enrichment steps (images, audio, video) don't abort on failure - they mark PARTIAL.
    Critical steps (RSS, prepare articles, verification, posts, articles, WordPress, social) abort on failure.

    Args:
        job_id: Unique job identifier
        generated_articles_repo: Repository for generated articles (injected)
        generated_posts_repo: Repository for generated posts (injected)
        verified_news_repo: Repository for verified news (injected)
        rss_fetch_runner: Callable para fetch RSS (inyectado)
        prepare_articles_runner: Callable para preparar artículos (inyectado)
        full_verify_runner: Callable para verificación completa (inyectado)
        metrics_repo: Repository for metrics (injected)
        social_publisher: Publisher social inyectado
        tts_usecase: Caso de uso TTS inyectado
        image_unsplash_runner: Callable para fetch Unsplash (inyectado)
        image_google_runner: Callable para fetch Google (inyectado)
        image_enricher_runner: Callable para enriquecer imágenes (inyectado)
        wordpress_runner: Callable para publicar en WordPress (inyectado)
        video_generator_factory: Factory de generador de vídeo (inyectado)

    Returns:
        bool: True if execution started, False if another execution is in progress.
    """
    if not _execution_lock.acquire(blocking=False):
        logger.warning(f"[PIPELINE-JOB] {job_id} Rejected: Pipeline already executing")
        return False

    logger.info(f"[PIPELINE-JOB] {job_id} Lock acquired - execution starting")

    ctx = PipelineContext(job_id=job_id)
    runner = PipelineRunner(
        generated_articles_repo,
        generated_posts_repo,
        verified_news_repo,
        rss_fetch_runner,
        prepare_articles_runner,
        full_verify_runner,
        metrics_repo,
        social_publisher,
        tts_usecase,
        image_unsplash_runner,
        image_google_runner,
        image_enricher_runner,
        wordpress_runner,
        video_generator_factory,
        social_truncator=social_truncator,
        post_editor=post_editor,
        cache_loader=cache_loader,
        seo_helpers=seo_helpers,
        ai_providers=ai_providers,
        content_extractor=content_extractor,
    )

    def _target():
        try:
            runner.run(ctx)
        finally:
            _execution_lock.release()
            logger.info(f"[PIPELINE-JOB] {job_id} Ejecución completada - Lock liberado")

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    return True
