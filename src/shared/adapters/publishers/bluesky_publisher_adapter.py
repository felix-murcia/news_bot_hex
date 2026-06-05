"""Adapter for Bluesky social publishing."""

from typing import Dict, Any
from config.logging_config import get_logger
from src.shared.domain.ports.social_publisher_port import SocialPublisherPort

logger = get_logger("news_bot.adapter.bluesky")


class BlueskyPublisherAdapter(SocialPublisherPort):
    """Adapter for publishing to Bluesky."""

    def __init__(self):
        """Initialize Bluesky publisher adapter."""
        self._publisher = None
        try:
            from src.shared.adapters.bluesky_publisher import BlueskyPublisher
            self._publisher = BlueskyPublisher()
            logger.info("[BLUESKY_ADAPTER] Bluesky publisher initialized")
        except Exception as e:
            logger.warning(f"[BLUESKY_ADAPTER] Failed to initialize: {e}")

    def is_available(self) -> bool:
        """Check if Bluesky publisher is available."""
        return self._publisher is not None

    def publish(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """Publish post to Bluesky."""
        if not self.is_available():
            return {
                "platform": "bluesky",
                "status": "skipped",
                "error": "Bluesky not configured"
            }

        try:
            logger.info("[BLUESKY_ADAPTER] Publishing to Bluesky")
            result = self._publisher.publish_posts([post_data])
            logger.info(f"[BLUESKY_ADAPTER] Published: {result}")
            return {
                "platform": "bluesky",
                "status": "ok" if result.get("published", 0) > 0 else "error",
                "published": result.get("published", 0),
            }
        except Exception as e:
            logger.error(f"[BLUESKY_ADAPTER] Publication failed: {e}")
            return {
                "platform": "bluesky",
                "status": "error",
                "error": str(e)
            }
