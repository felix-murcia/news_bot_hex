"""
FastAPI Server - Entry point for Docker.

Provides REST API endpoints for the news, audio, and video pipelines.
Uses modular routers for clean organization.
"""

from fastapi import FastAPI

from config.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger("news_bot.server")

from src.news.entrypoints.api.news_router import router as news_router
from src.audio.entrypoints.api.audio_router import router as audio_router
from src.video.entrypoints.api.video_router import router as video_router

app = FastAPI(
    title="News Bot Hex",
    description="AI-powered news pipeline with article generation and social media posting",
    version="1.0.0",
)

# Register routers
app.include_router(news_router, prefix="/news", tags=["news"])
app.include_router(audio_router, prefix="/audio", tags=["audio"])
app.include_router(video_router, prefix="/video", tags=["video"])


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "service": "news_bot_hex"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
