"""Adapter for image enrichment (metadata, optimization)."""

from typing import List
from config.logging_config import get_logger
from src.shared.domain.ports.image_enricher_port import ImageEnricherPort

logger = get_logger("news_bot.adapter.image_enricher")


class ImageEnricherAdapter(ImageEnricherPort):
    """Adapter for enriching images with metadata and optimization."""

    def __init__(self):
        """Initialize enricher."""
        pass

    def enrich(self, posts: List[dict], articles: List[dict]) -> None:
        """Enrich posts and articles with image metadata."""
        try:
            logger.info("[IMAGE_ENRICHER] Starting image enrichment")
            from src.shared.adapters.image_enricher import run as run_enricher
            run_enricher()
            logger.info("[IMAGE_ENRICHER] Image enrichment completed")
        except Exception as e:
            logger.error(f"[IMAGE_ENRICHER] Enrichment failed: {e}")
            raise
