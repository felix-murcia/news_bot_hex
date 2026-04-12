"""
FastAPI Router for Audio Pipeline.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from src.logging_config import get_logger

logger = get_logger("audio_bot.api.router")

router = APIRouter()


# ============================================================
# Request/Response Models
# ============================================================
class AudioRequest(BaseModel):
    url: str
    model: str = "openrouter"
    tema: str = "Audios"


class PipelineResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None


# ============================================================
# Endpoints
# ============================================================
@router.post("/process", response_model=PipelineResponse)
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
