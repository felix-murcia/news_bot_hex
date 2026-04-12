"""
FastAPI Router for News Pipeline.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from config.logging_config import get_logger

logger = get_logger("news_bot.api.router")

router = APIRouter()


# ============================================================
# Request/Response Models
# ============================================================
class ProcessUrlRequest(BaseModel):
    url: str
    provider: str | None = None
    use_ai: bool = True

    def get_model_provider(self) -> str:
        """Resolve model provider at runtime (not import time)."""
        if self.provider:
            return self.provider
        from config.settings import Settings
        return Settings.AI_PROVIDER


class PipelineResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None


# ============================================================
# Endpoints
# ============================================================
@router.post("/process_url", response_model=PipelineResponse)
def news_process_url(req: ProcessUrlRequest):
    """Process a news URL and generate article + tweet."""
    try:
        from src.news.application.usecases.news_to_news import process_news_url
        from src.news.infrastructure.adapters import JinaContentExtractor

        model_provider = req.get_model_provider()
        result = process_news_url(
            url=req.url,
            content_extractor=JinaContentExtractor(),
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
def news_rss():
    """Fetch RSS news and store in MongoDB."""
    try:
        from src.news.entrypoints.cli import main_rss

        main_rss()
        return PipelineResponse(status="ok", message="RSS news fetched successfully")
    except Exception as e:
        logger.error(f"Error fetching RSS: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify", response_model=PipelineResponse)
def news_verify():
    """Verify and score news articles."""
    try:
        from src.news.entrypoints.cli import main_full_verify

        main_full_verify()
        return PipelineResponse(status="ok", message="News verification completed")
    except Exception as e:
        logger.error(f"Error during verification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/soft", response_model=PipelineResponse)
def news_soft():
    """Soft verify and select best news."""
    try:
        from src.news.entrypoints.cli import main_soft

        result = main_soft()
        return PipelineResponse(
            status="ok",
            message="Soft verification completed",
            data={"title": result.get("title", ""), "score": result.get("score", 0)},
        )
    except Exception as e:
        logger.error(f"Error during soft verify: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/article", response_model=PipelineResponse)
def news_article(provider: str | None = None, limit: int = 1):
    """Generate professional articles from verified news."""
    try:
        from src.news.application.usecases.article import run
        from config.settings import Settings

        model_provider = provider or Settings.AI_PROVIDER
        results = run(limit=limit, use_gemini=True, model_provider=model_provider)
        return PipelineResponse(
            status="ok",
            message=f"Generated {len(results)} article(s)",
            data={"count": len(results)},
        )
    except Exception as e:
        logger.error(f"Error generating articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/content", response_model=PipelineResponse)
def news_content(network: str = "bluesky", provider: str | None = None):
    """Generate social media posts (tweets) from verified news."""
    try:
        from src.news.application.usecases.content import run_content
        from config.settings import Settings

        model_provider = provider or Settings.AI_PROVIDER
        results = run_content(network=network, use_gemini=True, model_provider=model_provider)
        return PipelineResponse(
            status="ok",
            message=f"Generated {len(results)} post(s)",
            data={"count": len(results)},
        )
    except Exception as e:
        logger.error(f"Error generating content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pipeline", response_model=PipelineResponse)
def news_full_pipeline():
    """Execute the complete news pipeline."""
    try:
        from src.news.entrypoints.cli import main_pipeline

        main_pipeline()
        return PipelineResponse(status="ok", message="Full pipeline executed")
    except Exception as e:
        logger.error(f"Error in full pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))
