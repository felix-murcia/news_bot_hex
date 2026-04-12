"""
FastAPI Router for Video Pipeline.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from config.settings import Settings
from src.logging_config import get_logger

logger = get_logger("video_bot.api.router")

router = APIRouter()


# ============================================================
# Request/Response Models
# ============================================================
class VideoRequest(BaseModel):
    url: str
    model: str = Settings.AI_PROVIDER
    tema: str = "Noticias"


class PipelineResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None


# ============================================================
# Endpoints
# ============================================================
@router.post("/process", response_model=PipelineResponse)
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
