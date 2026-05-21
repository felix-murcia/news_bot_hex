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

logger = get_logger("news_bot.api.router")

router = APIRouter()


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
    extractor: ContentExtractor = Depends(get_content_extractor),
):
    """Process a news URL and generate article + tweet."""
    try:
        from src.news.application.usecases.news_to_news import process_news_url

        model_provider = req.provider or Settings.AI_PROVIDER
        result = process_news_url(
            url=req.url,
            content_extractor=extractor,
            model_provider=model_provider,
            use_ai=req.use_ai,
        )
        return PipelineResponse(
            status="ok",
            message="News processed successfully",
            data={
                "title": result.get("article_data", {}).get("article", {}).get("title", ""),
                "post": result.get("post", "")[:200],
                "mode": result.get("mode", ""),
            },
        )
    except Exception as e:
        logger.error(f"Error processing news URL: {e}")
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
        logger.error(f"Database error fetching RSS: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except Exception as e:
        logger.error(f"Error fetching RSS: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        logger.error(f"Database error during verification: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except Exception as e:
        logger.error(f"Error during verification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        logger.error(f"Database error during soft verify: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except Exception as e:
        logger.error(f"Error during soft verify: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        logger.error(f"Database error generating articles: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except Exception as e:
        logger.error(f"Error generating articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        logger.error(f"Database error generating content: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except Exception as e:
        logger.error(f"Error generating content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        logger.error(f"Error starting pipeline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
                "steps": job["steps"],
                "error": job.get("error"),
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
