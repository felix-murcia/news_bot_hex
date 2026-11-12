"""
FastAPI Router for Audio Pipeline.
"""

from fastapi import APIRouter, HTTPException, Depends
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
        from config.settings import Settings
        from src.audio.application.usecases.audio_to_news import AudioToNewsUseCase
        from src.audio.infrastructure.adapters.audio_fetcher import download_audio, transcribe_audio
        from src.shared.adapters.audio_converter import AudioConverter
        from src.shared.infrastructure.composition_root import create_debug_output_repository

        model_provider = req.get_model_provider()
        processor = AudioToNewsUseCase(
            debug_output_repo=create_debug_output_repository(),
            cache_dir=Settings.CACHE_DIR,
            wp_site_url=Settings.WP_SITE_URL,
            copyright_domains=Settings.VIDEO_COPYRIGHT_DOMAINS,
            download_audio=download_audio,
            transcribe_audio=transcribe_audio,
            has_audio_stream=AudioConverter().has_audio_stream,
            use_ai=True,
            model_provider=model_provider,
        )
        result = processor.process_audio_url(req.url)
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
def audio_pipeline(
    req: PipelineRequest,
    metrics_repo=Depends(lambda: None),  # Optional: metrics collection is non-fatal
):
    """Execute the complete audio pipeline: fetch → transcribe → article → publish."""
    try:
        from src.audio.application.usecases.audio_pipeline import AudioPipelineUseCase
        from src.news.entrypoints.api.dependencies import get_metrics_repository, get_db

        # Try to get metrics repo if not provided
        if not metrics_repo:
            try:
                db = get_db()
                metrics_repo = get_metrics_repository(db=db)
            except Exception as e:
                logger.warning(f"Could not initialize metrics repository: {e}")
                metrics_repo = None

        # Generate job ID for metrics tracking
        import uuid
        job_id = str(uuid.uuid4())

        from config.settings import Settings
        from src.shared.infrastructure.composition_root import (
            create_ai_adapter,
            create_audio_converter,
            create_audio_fetcher,
            create_audio_transcriber,
            create_tts_adapter,
            create_video_generator,
        )

        usecase = AudioPipelineUseCase(
            no_publish=req.no_publish,
            video_generator=create_video_generator(),
            audio_fetcher_factory=create_audio_fetcher,
            audio_transcriber_factory=create_audio_transcriber,
            tts_adapter_factory=create_tts_adapter,
            audio_converter=create_audio_converter(),
            ai_adapter_factory=create_ai_adapter,
            metrics_repo=metrics_repo,
            ai_provider=Settings.AI_PROVIDER,
            tts_voice=Settings.TTS_VOICE,
            tts_model=Settings.TTS_MODEL,
            wp_site_url=Settings.WP_SITE_URL,
            wp_default_image_url=Settings.WP_DEFAULT_IMAGE_URL,
        )
        result = usecase.run(url=req.url, tema=req.tema, job_id=job_id)

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
