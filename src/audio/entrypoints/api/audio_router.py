"""
FastAPI Router for Audio Pipeline.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from config.logging_config import get_logger

logger = get_logger("audio_bot.api.router")

router = APIRouter()


# ============================================================
# Request/Response Models
# ============================================================
class AudioRequest(BaseModel):
    url: str
    provider: str | None = None
    tema: str = "Audios"

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
@router.post("/process", response_model=PipelineResponse)
def audio_process(req: AudioRequest):
    """Process audio URL and generate article + tweet."""
    try:
        from src.audio.application.usecases.audio_to_news import process_audio_url

        model_provider = req.get_model_provider()
        result = process_audio_url(url=req.url, model_provider=model_provider, use_ai=True)
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


class PipelineRequest(BaseModel):
    url: str
    tema: str
    no_publish: bool = False


@router.post("/pipeline", response_model=PipelineResponse)
def audio_pipeline(req: PipelineRequest):
    """Execute the complete audio pipeline: fetch → transcribe → article → publish."""
    try:
        from src.audio.application.usecases.audio_pipeline import AudioPipelineUseCase

        usecase = AudioPipelineUseCase(no_publish=req.no_publish)
        result = usecase.run(url=req.url, tema=req.tema)

        return PipelineResponse(
            status="ok",
            message="Audio pipeline executed successfully",
            data={
                "wordpress_url": result.get("wordpress_url", "N/A"),
                "social_platforms": len(result.get("social_results", [])),
            },
        )
    except Exception as e:
        logger.error(f"Error executing audio pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))
