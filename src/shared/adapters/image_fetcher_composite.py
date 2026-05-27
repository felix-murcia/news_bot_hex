"""Composite adapter for image fetching (Unsplash + Google)."""

from typing import List
from config.logging_config import get_logger
from src.shared.domain.ports.image_fetcher_port import ImageFetcherPort

logger = get_logger("news_bot.adapter.image_fetcher")


class ImageFetcherCompositeAdapter(ImageFetcherPort):
    """
    Composite adapter that fetches images from multiple sources:
    - Unsplash (primary, by default)
    - Google Images (fallback)
    """

    def __init__(self):
        """Initialize composite fetcher with Unsplash and Google adapters."""
        pass

    def fetch(self, posts: List[dict]) -> None:
        """Fetch images from Unsplash and Google for posts."""
        try:
            logger.info("[IMAGE_FETCHER] Starting image fetch from Unsplash")
            from src.shared.adapters.unsplash_fetcher import run as run_unsplash
            run_unsplash()
        except Exception as e:
            logger.warning(f"[IMAGE_FETCHER] Unsplash fetch failed: {e}")

        try:
            logger.info("[IMAGE_FETCHER] Starting image fetch from Google")
            from src.shared.adapters.google_images_fetcher import run as run_google
            run_google()
        except Exception as e:
            logger.warning(f"[IMAGE_FETCHER] Google fetch failed: {e}")

        logger.info("[IMAGE_FETCHER] Image fetch completed")
