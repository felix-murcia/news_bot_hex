"""
FastAPI Server - Entry point for Docker.

Provides REST API endpoints for the news, audio, and video pipelines.
Uses modular routers for clean organization.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger("news_bot.server")

from src.news.entrypoints.api.news_router import router as news_router
from src.news.entrypoints.api.admin_router import router as admin_router
from src.news.entrypoints.api.metrics_router import router as metrics_router
from src.news.entrypoints.api.error_handlers import register_error_handlers
from src.audio.entrypoints.api.audio_router import router as audio_router
from src.video.entrypoints.api.video_router import router as video_router

app = FastAPI(
    title="News Bot Hex",
    description="AI-powered news pipeline with article generation and social media posting",
    version="1.0.0",
)

# Allow the React dev server (port 5173) and any local origin during development.
# In production, traffic goes through nginx so CORS is never exercised.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register global error handlers
register_error_handlers(app)

# Register routers
app.include_router(news_router, prefix="/news", tags=["news"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])
app.include_router(metrics_router, prefix="/metrics", tags=["metrics"])
app.include_router(audio_router, prefix="/audio", tags=["audio"])
app.include_router(video_router, prefix="/video", tags=["video"])


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "service": "news_bot_hex"}


@app.get("/logs/tail")
def logs_tail(lines: int = 20) -> dict:
    """Return the last N lines of the application log file."""
    from config.logging_config import LOG_FILE

    try:
        with open(LOG_FILE, "rb") as f:
            # Efficient tail: read from the end
            f.seek(0, 2)
            size = f.tell()
            block = min(size, 32_768)
            f.seek(-block, 2)
            raw = f.read().decode("utf-8", errors="replace")
        tail = raw.splitlines()[-lines:]
        return {"lines": tail}
    except FileNotFoundError:
        return {"lines": []}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
