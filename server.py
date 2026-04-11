"""
FastAPI Server - Entry point for Docker.

Provides REST API endpoints for the news, audio, and video pipelines.
"""

import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("news_bot_server")

app = FastAPI(
    title="News Bot Hex",
    description="AI-powered news pipeline with article generation and social media posting",
    version="1.0.0",
)


# ============================================================
# Request/Response Models
# ============================================================
class ProcessUrlRequest(BaseModel):
    url: str
    model: str = "openrouter"
    use_ai: bool = True


class AudioRequest(BaseModel):
    url: str
    model: str = "openrouter"
    tema: str = "Audios"


class VideoRequest(BaseModel):
    url: str
    model: str = "openrouter"
    tema: str = "Videos"


class PipelineResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None


# ============================================================
# Health
# ============================================================
@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "service": "news_bot_hex"}


# ============================================================
# News Pipeline
# ============================================================
@app.post("/news/process_url", response_model=PipelineResponse)
def news_process_url(req: ProcessUrlRequest):
    """Process a news URL and generate article + tweet."""
    try:
        from src.news.application.usecases.news_to_news import process_news_url

        result = process_news_url(url=req.url, model_provider=req.model, use_ai=req.use_ai)
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


@app.post("/news/rss", response_model=PipelineResponse)
def news_rss():
    """Fetch RSS news and store in MongoDB."""
    try:
        from src.news.entrypoints.cli import main_rss

        main_rss()
        return PipelineResponse(status="ok", message="RSS news fetched successfully")
    except Exception as e:
        logger.error(f"Error fetching RSS: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/news/verify", response_model=PipelineResponse)
def news_verify():
    """Verify and score news articles."""
    try:
        from src.news.entrypoints.cli import main_full_verify

        main_full_verify()
        return PipelineResponse(status="ok", message="News verification completed")
    except Exception as e:
        logger.error(f"Error during verification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/news/soft", response_model=PipelineResponse)
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


@app.post("/news/article", response_model=PipelineResponse)
def news_article(model: str = "openrouter", limit: int = 1):
    """Generate professional articles from verified news."""
    try:
        from src.news.application.usecases.article import run

        results = run(limit=limit, use_gemini=True, model_provider=model)
        return PipelineResponse(
            status="ok",
            message=f"Generated {len(results)} article(s)",
            data={"count": len(results)},
        )
    except Exception as e:
        logger.error(f"Error generating articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/news/content", response_model=PipelineResponse)
def news_content(network: str = "bluesky", model: str = "openrouter"):
    """Generate social media posts (tweets) from verified news."""
    try:
        from src.news.application.usecases.content import run_content

        results = run_content(network=network, use_gemini=True, model_provider=model)
        return PipelineResponse(
            status="ok",
            message=f"Generated {len(results)} post(s)",
            data={"count": len(results)},
        )
    except Exception as e:
        logger.error(f"Error generating content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/news/pipeline", response_model=PipelineResponse)
def news_full_pipeline():
    """Execute the complete news pipeline."""
    try:
        from src.news.entrypoints.cli import main_pipeline

        main_pipeline()
        return PipelineResponse(status="ok", message="Full pipeline executed")
    except Exception as e:
        logger.error(f"Error in full pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Audio Pipeline
# ============================================================
@app.post("/audio/process", response_model=PipelineResponse)
def audio_process(req: AudioRequest):
    """Process audio URL and generate article + tweet."""
    try:
        from src.audio.application.usecases.audio_to_news import process_audio_url

        result = process_audio_url(url=req.url, model_provider=req.model, use_ai=True)
        return PipelineResponse(
            status="ok",
            message="Audio processed successfully",
            data={
                "transcript_length": len(result.get("transcript", "")),
                "article_length": len(result.get("article", "")),
                "post": result.get("post", "")[:200],
            },
        )
    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Video Pipeline
# ============================================================
@app.post("/video/process", response_model=PipelineResponse)
def video_process(req: VideoRequest):
    """Process video URL and generate article + tweet."""
    try:
        from src.video.application.usecases.video_to_news import process_video_url

        result = process_video_url(url=req.url, model_provider=req.model, use_ai=True)
        return PipelineResponse(
            status="ok",
            message="Video processed successfully",
            data={
                "transcript_length": len(result.get("transcript", "")),
                "article_length": len(result.get("article", "")),
                "post": result.get("post", "")[:200],
            },
        )
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
