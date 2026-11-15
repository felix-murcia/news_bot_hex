"""
FastAPI Router for News Pipeline.

Usa FastAPI Depends() para inyecciones de dependencias (Composition Root).
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List

from config.logging_config import get_logger
from config.settings import Settings
from src.news.domain.exceptions import RepositoryError
from src.news.domain.ports import (
    ArticleRepository,
    VerifiedNewsRepository,
)
from src.news.application.usecases.article import ArticleUseCase
from src.news.entrypoints.api.dependencies import (
    get_article_repo,
    get_verified_news_repo,
    get_article_usecase,
    get_fetch_rss_usecase,
    get_full_verify_usecase,
    get_soft_verify_usecase,
    get_generated_posts_repo,
    get_process_url_job_coordinator,
    get_process_url_job_repository,
    get_generated_articles_repo,
    get_metrics_repository,
)
from src.news.entrypoints.api.error_handler import http_error, get_error_message

logger = get_logger("news_bot.api.router")

router = APIRouter()


def validate_provider(provider: str | None) -> str | None:
    """Validate that provider is supported, return the provider or None."""
    if not provider or not provider.strip():
        return None
    provider_lower = provider.lower()
    if provider_lower not in Settings.AI_ADAPTER_MAP:
        available = ", ".join(Settings.AI_ADAPTER_MAP.keys())
        raise ValueError(f"Proveedor no soportado: {provider}. Disponibles: {available}")
    return provider_lower


# ============================================================
# Request/Response Models
# ============================================================
class ProcessUrlRequest(BaseModel):
    url: str
    provider: str | None = None
    use_ai: bool = True


class PipelineResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None


# ============================================================
# Endpoints
# ============================================================
@router.post("/process_url", response_model=PipelineResponse)
def news_process_url(
    req: ProcessUrlRequest,
    job_coordinator=Depends(get_process_url_job_coordinator),
    job_repository=Depends(get_process_url_job_repository),
):
    """Start async processing of a news URL. Returns job_id for polling status."""
    try:
        if not req.url or not req.url.strip():
            msg, details = get_error_message("INVALID_URL")
            raise http_error(
                status_code=400,
                error_code="INVALID_URL",
                message=msg,
                details=details,
            )

        model_provider = req.provider or Settings.AI_PROVIDER
        try:
            validate_provider(model_provider)
        except ValueError as e:
            logger.error(f"[PROCESS_URL] {str(e)}")
            raise http_error(
                status_code=400,
                error_code="INVALID_REQUEST",
                message="Proveedor de IA no válido",
                exception=e,
                details=str(e),
            )

        # Create job and start async processing
        job_id = job_repository.create()
        job_coordinator.execute_async(job_id=job_id, url=req.url)

        return PipelineResponse(
            status="ok",
            message="URL processing started",
            data={"job_id": job_id},
        )

    except HTTPException:
        raise
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(f"[PROCESS_URL] {error_type}: {error_msg}")
        msg, details = get_error_message("PIPELINE_ERROR")
        raise http_error(
            status_code=500,
            error_code="PIPELINE_ERROR",
            message=msg,
            exception=e,
            details=details,
            context={"url": req.url, "error_type": error_type},
        )


@router.get("/process_url/status/{job_id}", response_model=PipelineResponse)
def get_process_url_status(
    job_id: str,
    job_repository=Depends(get_process_url_job_repository),
):
    """Get status and progress of a process_url job."""
    try:
        job = job_repository.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        return PipelineResponse(
            status="ok",
            message=job.get("message", ""),
            data={
                "job_id": job_id,
                "status": job["status"],
                "progress": job["progress"],
                "message": job.get("message", ""),
                "steps": job["steps"],
                "error": job.get("error"),
                "last_log": job.get("last_log"),
                "created_at": job.get("created_at"),
                "started_at": job.get("started_at"),
                "completed_at": job.get("completed_at"),
                "result": job.get("result"),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting process_url status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rss", response_model=PipelineResponse)
def news_rss(fetch_usecase=Depends(get_fetch_rss_usecase)):
    """Fetch RSS news and store in MongoDB."""
    try:
        result = fetch_usecase.execute()
        return PipelineResponse(
            status="ok",
            message="RSS news fetched successfully",
            data={"new_articles": result.get("new_articles", 0), "total_articles": result.get("total_articles", 0)},
        )
    except RepositoryError as e:
        msg, details = get_error_message("DATABASE_ERROR")
        raise http_error(
            status_code=503,
            error_code="DATABASE_ERROR",
            message=msg,
            exception=e,
            details=details,
        )
    except Exception as e:
        msg, details = get_error_message("PIPELINE_ERROR")
        raise http_error(
            status_code=500,
            error_code="PIPELINE_ERROR",
            message=msg,
            exception=e,
            details=details,
        )


class ArticleItem(BaseModel):
    title: str
    url: str
    source: str
    publishedAt: Optional[str] = None


@router.get("/rss", response_model=List[ArticleItem])
def news_rss_list(article_repo: ArticleRepository = Depends(get_article_repo)):
    """Return the articles currently stored in MongoDB."""
    try:
        articles = article_repo.get_all_articles()
        return [
            ArticleItem(
                title=a.title,
                url=a.url,
                source=a.source,
                publishedAt=a.published_at.isoformat() if hasattr(a.published_at, "isoformat") else a.published_at,
            )
            for a in articles
        ]
    except RepositoryError as e:
        logger.error(f"Database error listing RSS articles: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except Exception as e:
        logger.error(f"Error listing RSS articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify", response_model=PipelineResponse)
def news_verify(verify_usecase=Depends(get_full_verify_usecase)):
    """Verify and score news articles."""
    try:
        result = verify_usecase.execute()
        return PipelineResponse(status="ok", message="News verification completed", data=result)
    except RepositoryError as e:
        msg, details = get_error_message("DATABASE_ERROR")
        raise http_error(
            status_code=503,
            error_code="DATABASE_ERROR",
            message=msg,
            exception=e,
            details=details,
        )
    except Exception as e:
        msg, details = get_error_message("PIPELINE_ERROR")
        raise http_error(
            status_code=500,
            error_code="PIPELINE_ERROR",
            message=msg,
            exception=e,
            details=details,
        )


@router.post("/soft", response_model=PipelineResponse)
def news_soft(soft_usecase=Depends(get_soft_verify_usecase)):
    """Soft verify and select best news."""
    try:
        result = soft_usecase.execute()
        return PipelineResponse(
            status="ok",
            message="Soft verification completed",
            data={"title": result.get("title", ""), "score": result.get("score", 0), "url": result.get("url", "")},
        )
    except RepositoryError as e:
        msg, details = get_error_message("DATABASE_ERROR")
        raise http_error(
            status_code=503,
            error_code="DATABASE_ERROR",
            message=msg,
            exception=e,
            details=details,
        )
    except Exception as e:
        msg, details = get_error_message("PIPELINE_ERROR")
        raise http_error(
            status_code=500,
            error_code="PIPELINE_ERROR",
            message=msg,
            exception=e,
            details=details,
        )


@router.post("/article", response_model=PipelineResponse)
def news_article(
    provider: str | None = None,
    limit: int = 1,
    article_usecase: ArticleUseCase = Depends(get_article_usecase),
):
    """Generate professional articles from verified news."""
    try:
        results = article_usecase.execute(limit=limit)
        return PipelineResponse(
            status="ok",
            message=f"Generated {len(results)} article(s)",
            data={"count": len(results)},
        )
    except RepositoryError as e:
        msg, details = get_error_message("DATABASE_ERROR")
        raise http_error(
            status_code=503,
            error_code="DATABASE_ERROR",
            message=msg,
            exception=e,
            details=details,
        )
    except Exception as e:
        msg, details = get_error_message("ARTICLE_GENERATION_FAILED")
        raise http_error(
            status_code=500,
            error_code="ARTICLE_GENERATION_FAILED",
            message=msg,
            exception=e,
            details=details,
        )


@router.post("/content", response_model=PipelineResponse)
def news_content(
    network: str = "bluesky",
    provider: str | None = None,
    verified_repo: VerifiedNewsRepository = Depends(get_verified_news_repo),
    generated_posts_repo=Depends(get_generated_posts_repo),
):
    """Generate social media posts (tweets) from verified news."""
    try:
        from src.news.application.usecases.content import ContentUseCase

        model_provider = provider or Settings.AI_PROVIDER
        from src.shared.adapters.cache_manager import load_content_from_cache
        from src.shared.adapters.content_post_editor import post_edit_content
        from src.shared.adapters.social_post_adapter import truncate_social_post
        from src.shared.infrastructure.composition_root import create_ai_providers

        content_usecase = ContentUseCase(
            verified_repo=verified_repo,
            generated_posts_repo=generated_posts_repo,
            ai_providers=create_ai_providers(),
            social_truncator=truncate_social_post,
            post_editor=post_edit_content,
            cache_loader=load_content_from_cache,
            network=network,
            model_provider=model_provider,
        )
        results = content_usecase.execute()
        return PipelineResponse(
            status="ok",
            message=f"Generated {len(results)} post(s)",
            data={"count": len(results)},
        )
    except RepositoryError as e:
        msg, details = get_error_message("DATABASE_ERROR")
        raise http_error(
            status_code=503,
            error_code="DATABASE_ERROR",
            message=msg,
            exception=e,
            details=details,
        )
    except Exception as e:
        msg, details = get_error_message("TWEET_GENERATION_FAILED")
        raise http_error(
            status_code=500,
            error_code="TWEET_GENERATION_FAILED",
            message=msg,
            exception=e,
            details=details,
        )


@router.post("/pipeline", response_model=PipelineResponse)
def news_full_pipeline(
    generated_articles_repo=Depends(get_generated_articles_repo),
    generated_posts_repo=Depends(get_generated_posts_repo),
    verified_news_repo=Depends(get_verified_news_repo),
    metrics_repo=Depends(get_metrics_repository),
):
    """Start the complete news pipeline asynchronously (returns job_id for polling)."""
    try:
        from src.news.application.usecases.pipeline_job import create_job
        from src.news.application.usecases.pipeline_executor import execute_pipeline_async
        from src.news.entrypoints.cli import main_rss, main_prepare_articles, main_full_verify
        from src.shared.application.usecases.tts_from_article import TTSFromArticleUseCase
        from src.shared.adapters.tts_text_processor import TTSTextProcessor
        from src.shared.infrastructure.composition_root import (
            create_ai_providers,
            create_audio_converter,
            create_audio_converter_url_getter,
            create_social_publisher,
            create_tts_adapter,
            create_video_generator,
            create_wordpress_publisher,
            run_image_enricher,
            run_image_google,
            run_image_unsplash,
        )

        job_id = create_job()
        from src.news.infrastructure.adapters.content_extractor import JinaContentExtractor
        content_extractor = JinaContentExtractor()
        tts_usecase = TTSFromArticleUseCase(
            create_tts_adapter(),
            create_audio_converter(),
            TTSTextProcessor(),
            create_audio_converter_url_getter(),
        )
        from src.shared.adapters.cache_manager import load_content_from_cache
        from src.shared.adapters.content_post_editor import post_edit_content
        from src.shared.adapters.social_post_adapter import truncate_social_post
        from src.shared.adapters.seo_optimizer import (
            slugify as seo_slugify,
            extract_focus_keyphrase,
            generate_meta_description,
            generate_excerpt,
            truncate_seo_title,
            clean_title as seo_clean_title,
        )
        from src.shared.domain.services.seo_helpers import SeoHelpers

        seo_helpers = SeoHelpers(
            slugify=seo_slugify,
            extract_focus_keyphrase=extract_focus_keyphrase,
            generate_meta_description=generate_meta_description,
            truncate_seo_title=truncate_seo_title,
            clean_title=seo_clean_title,
            generate_excerpt=generate_excerpt,
        )

        started = execute_pipeline_async(
            job_id,
            generated_articles_repo,
            generated_posts_repo,
            verified_news_repo,
            main_rss,
            main_prepare_articles,
            main_full_verify,
            metrics_repo,
            create_social_publisher(),
            tts_usecase,
            run_image_unsplash,
            run_image_google,
            run_image_enricher,
            lambda article, post: create_wordpress_publisher().publish_article(article, post),
            create_video_generator,
            social_truncator=truncate_social_post,
            post_editor=post_edit_content,
            cache_loader=load_content_from_cache,
            seo_helpers=seo_helpers,
            ai_providers=create_ai_providers(),
            content_extractor=content_extractor,
        )

        if not started:
            raise HTTPException(
                status_code=409,
                detail="Pipeline is already executing. Only one execution allowed at a time."
            )

        return PipelineResponse(
            status="ok",
            message="Pipeline started",
            data={"job_id": job_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        msg, details = get_error_message("PIPELINE_ERROR")
        raise http_error(
            status_code=500,
            error_code="PIPELINE_ERROR",
            message=msg,
            exception=e,
            details=details,
        )


@router.get("/pipeline/status/{job_id}", response_model=PipelineResponse)
def get_pipeline_status(job_id: str):
    """Get pipeline job status and progress."""
    try:
        from src.news.application.usecases.pipeline_job import get_job

        job = get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        return PipelineResponse(
            status="ok",
            message=job.get("message", ""),
            data={
                "job_id": job_id,
                "status": job["status"],
                "progress": job["progress"],
                "message": job.get("message", ""),
                "steps": job["steps"],
                "error": job.get("error"),
                "last_log": job.get("last_log"),
                "created_at": job.get("created_at"),
                "started_at": job.get("started_at"),
                "completed_at": job.get("completed_at"),
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
