"""
FastAPI Router for News Pipeline.

Usa FastAPI Depends() para inyecciones de dependencias (Composition Root).
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import subprocess

from config.logging_config import get_logger
from config.settings import Settings
from src.news.domain.exceptions import RepositoryError
from src.news.domain.ports import (
    ArticleRepository,
    VerifiedNewsRepository,
    ContentExtractor,
)
from src.news.application.usecases.article import ArticleUseCase
from src.news.application.usecases.content import ContentUseCase
from src.news.entrypoints.api.dependencies import (
    get_content_extractor,
    get_article_repo,
    get_verified_news_repo,
    get_article_usecase,
    get_content_usecase,
    get_fetch_rss_usecase,
    get_full_verify_usecase,
    get_soft_verify_usecase,
    get_generated_posts_repo,
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


class TimerConfig(BaseModel):
    enabled: bool
    schedule_time: str
    frequency: str = "daily"


# ============================================================
# Endpoints
# ============================================================
@router.post("/process_url", response_model=PipelineResponse)
def news_process_url(
    req: ProcessUrlRequest,
    extractor: ContentExtractor = Depends(get_content_extractor),
):
    """Process a news URL and generate article + tweet."""
    try:
        from src.news.application.usecases.news_to_news import process_news_url

        if not req.url or not req.url.strip():
            msg, details = get_error_message("INVALID_URL")
            raise http_error(
                status_code=400,
                error_code="INVALID_URL",
                message=msg,
                details=details,
            )

        model_provider = req.provider or Settings.AI_PROVIDER
        # Validate provider is supported
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
        result = process_news_url(
            url=req.url,
            content_extractor=extractor,
            model_provider=model_provider,
            use_ai=req.use_ai,
            force_extract=True,  # Always force fresh extraction for manual URL processing
        )

        title = result.get("article_data", {}).get("article", {}).get("title", "")
        post = result.get("post", "")[:200] if result.get("post") else ""
        mode = result.get("mode", "")

        return PipelineResponse(
            status="ok",
            message="News processed successfully",
            data={
                "title": title,
                "post": post,
                "mode": mode,
            },
        )
    except HTTPException:
        raise
    except ValueError as e:
        error_msg = str(e)
        logger.error(f"[PROCESS_URL] ValueError: {error_msg}")
        if "No se pudo extraer" in error_msg:
            code = "CONTENT_EXTRACTION_FAILED"
        elif "contenido insuficiente" in error_msg.lower() or len(error_msg) > 0 and "100" in error_msg:
            code = "CONTENT_TOO_SHORT"
        else:
            code = "INVALID_REQUEST"
        msg, details = get_error_message(code)
        raise http_error(
            status_code=400,
            error_code=code,
            message=msg,
            exception=e,
            details=details,
            context={"original_error": error_msg},
        )
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
            context={"url": req.url, "provider": model_provider, "error_type": error_type},
        )


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
        content_usecase = ContentUseCase(
            verified_repo=verified_repo,
            generated_posts_repo=generated_posts_repo,
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
def news_full_pipeline():
    """Start the complete news pipeline asynchronously (returns job_id for polling)."""
    try:
        from src.news.application.usecases.pipeline_job import create_job
        from src.news.application.usecases.pipeline_executor import execute_pipeline_async

        job_id = create_job()
        execute_pipeline_async(job_id)

        return PipelineResponse(
            status="ok",
            message="Pipeline started",
            data={"job_id": job_id}
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


@router.get("/timer/config", response_model=PipelineResponse)
def get_timer_config():
    """Get current timer configuration."""
    try:
        from config.timer_config import get_timer_config

        config = get_timer_config()
        return PipelineResponse(
            status="ok",
            message="Timer configuration retrieved",
            data={
                "enabled": config.enabled,
                "schedule_time": config.schedule_time,
                "frequency": config.frequency,
            }
        )
    except Exception as e:
        logger.error(f"Error getting timer config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/timer/config", response_model=PipelineResponse)
def update_timer_config(config: TimerConfig):
    """Update timer configuration."""
    try:
        from config.timer_config import update_timer_config

        updated = update_timer_config(
            enabled=config.enabled,
            schedule_time=config.schedule_time,
            frequency=config.frequency
        )

        # Try to control systemctl timer (may fail due to permissions)
        control_message = ""
        try:
            if config.enabled:
                result = subprocess.run(
                    ["systemctl", "--user", "start", "news-bot-pipeline.timer"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    control_message = " (Timer started)"
            else:
                result = subprocess.run(
                    ["systemctl", "--user", "stop", "news-bot-pipeline.timer"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    control_message = " (Timer stopped)"
        except Exception as e:
            logger.warning(f"[TIMER] Could not control systemctl: {e}")
            if not config.enabled:
                control_message = " (Manual control via: systemctl --user stop news-bot-pipeline.timer)"
            else:
                control_message = " (Manual control via: systemctl --user start news-bot-pipeline.timer)"

        logger.info(f"[TIMER] Configuration updated: {updated.to_dict()}{control_message}")

        return PipelineResponse(
            status="ok",
            message=f"Timer configuration updated{control_message}",
            data={
                "enabled": updated.enabled,
                "schedule_time": updated.schedule_time,
                "frequency": updated.frequency,
            }
        )
    except Exception as e:
        logger.error(f"Error updating timer config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers", response_model=PipelineResponse)
def get_supported_providers():
    """Get list of supported AI providers."""
    try:
        providers = list(Settings.AI_ADAPTER_MAP.keys())
        return PipelineResponse(
            status="ok",
            message="Supported providers retrieved",
            data={"providers": providers}
        )
    except Exception as e:
        logger.error(f"Error getting supported providers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timer/status", response_model=PipelineResponse)
def get_timer_status():
    """Get systemd timer status (or fallback if running in Docker)."""
    try:
        from config.timer_config import get_timer_config

        config = get_timer_config()

        # Try to get systemd status (may fail in Docker)
        is_active = None
        status_output = ""
        timers_output = ""

        try:
            result = subprocess.run(
                ["systemctl", "--user", "status", "news-bot-pipeline.timer"],
                capture_output=True,
                text=True,
                timeout=10
            )
            is_active = result.returncode == 0
            status_output = result.stdout

            # Get next execution time
            next_exec = subprocess.run(
                ["systemctl", "--user", "list-timers", "news-bot-pipeline.timer", "--no-pager"],
                capture_output=True,
                text=True,
                timeout=10
            )
            timers_output = next_exec.stdout
        except FileNotFoundError:
            # systemctl not available (e.g., running in Docker)
            # Use config to determine status instead
            logger.info("[TIMER] systemctl not available (running in Docker?), using config status")
            is_active = config.enabled
            status_output = f"Timer is {'enabled' if config.enabled else 'disabled'} (systemctl unavailable)"
            timers_output = f"Schedule: {config.schedule_time} ({config.frequency})"
        except Exception as e:
            logger.warning(f"[TIMER] Could not get systemd status: {e}")
            is_active = config.enabled
            status_output = f"Timer is {'enabled' if config.enabled else 'disabled'} (status unavailable)"
            timers_output = f"Schedule: {config.schedule_time} ({config.frequency})"

        return PipelineResponse(
            status="ok",
            message="Timer status retrieved",
            data={
                "active": is_active,
                "enabled": config.enabled,
                "schedule_time": config.schedule_time,
                "frequency": config.frequency,
                "status_output": status_output,
                "timers_output": timers_output,
            }
        )
    except Exception as e:
        logger.error(f"Error getting timer status: {e}", exc_info=True)
        # Return fallback response instead of 500 error
        return PipelineResponse(
            status="ok",
            message="Timer status (fallback)",
            data={
                "active": False,
                "status_output": "Status unavailable",
                "error": str(e)
            }
        )
