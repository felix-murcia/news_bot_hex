"""Adapter for WordPress publishing."""

from typing import Dict, Any
from config.logging_config import get_logger
from src.shared.domain.ports.wordpress_publisher_port import WordPressPublisherPort

logger = get_logger("news_bot.adapter.wordpress_publisher")


class WordPressPublisherAdapter(WordPressPublisherPort):
    """Adapter for publishing articles to WordPress."""

    def __init__(self):
        """Initialize WordPress publisher adapter."""
        pass

    def publish(self) -> Dict[str, Any]:
        """Publish generated articles to WordPress."""
        try:
            logger.info("[WORDPRESS_ADAPTER] Publishing articles to WordPress")
            from src.shared.adapters.wordpress_publisher import run as run_wordpress
            result = run_wordpress()
            logger.info(f"[WORDPRESS_ADAPTER] Publication completed: {result}")
            return result
        except Exception as e:
            logger.error(f"[WORDPRESS_ADAPTER] Publication failed: {e}")
            raise
