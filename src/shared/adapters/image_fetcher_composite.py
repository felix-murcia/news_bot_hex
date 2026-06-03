"""Composite adapter for image fetching (Wikimedia → Unsplash fallback)."""

from typing import List
from config.logging_config import get_logger
from src.shared.domain.ports.image_fetcher_port import ImageFetcherPort

logger = get_logger("news_bot.adapter.image_fetcher")


class ImageFetcherCompositeAdapter(ImageFetcherPort):
    """
    Fetches images in priority order:
    1. Wikimedia Commons (primary — photojournalism, CC licensed)
    2. Google Images (secondary fallback)
    3. Unsplash (last resort — stock photography)
    """

    def __init__(self):
        pass

    def fetch(self, posts: List[dict]) -> None:
        try:
            logger.info("[IMAGE_FETCHER] Starting image fetch from Wikimedia Commons")
            from src.shared.adapters.wikimedia_fetcher import run as run_wikimedia
            run_wikimedia()
        except Exception as e:
            logger.warning(f"[IMAGE_FETCHER] Wikimedia fetch failed: {e}")

        try:
            logger.info("[IMAGE_FETCHER] Starting image fetch from Google Images")
            from src.shared.adapters.google_images_fetcher import run as run_google
            run_google()
        except Exception as e:
            logger.warning(f"[IMAGE_FETCHER] Google fetch failed: {e}")

        try:
            logger.info("[IMAGE_FETCHER] Starting image fetch from Unsplash (last resort)")
            from src.shared.adapters.unsplash_fetcher import run as run_unsplash
            run_unsplash()
        except Exception as e:
            logger.warning(f"[IMAGE_FETCHER] Unsplash fetch failed: {e}")

        logger.info("[IMAGE_FETCHER] Image fetch completed")
