"""Adapter for Mastodon social publishing."""

from typing import Dict, Any
from config.logging_config import get_logger
from src.shared.domain.ports.social_publisher_port import SocialPublisherPort

logger = get_logger("news_bot.adapter.mastodon")


class MastodonPublisherAdapter(SocialPublisherPort):
    """Adapter for publishing to Mastodon."""

    def __init__(self):
        """Initialize Mastodon publisher adapter."""
        self._publisher = None
        try:
            from src.shared.adapters.mastodon_publisher import MastodonPublisher
            self._publisher = MastodonPublisher()
            logger.info("[MASTODON_ADAPTER] Mastodon publisher initialized")
        except Exception as e:
            logger.warning(f"[MASTODON_ADAPTER] Failed to initialize: {e}")

    def is_available(self) -> bool:
        """Check if Mastodon publisher is available."""
        return self._publisher is not None

    def publish(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """Publish post to Mastodon."""
        if not self.is_available():
            return {
                "platform": "mastodon",
                "status": "skipped",
                "error": "Mastodon not configured"
            }

        try:
            logger.info("[MASTODON_ADAPTER] Publishing to Mastodon")
            result = self._publisher.publish_posts([post_data])
            logger.info(f"[MASTODON_ADAPTER] Published: {result}")
            return {
                "platform": "mastodon",
                "status": "ok" if result.get("published", 0) > 0 else "error",
                "published": result.get("published", 0),
            }
        except Exception as e:
            logger.error(f"[MASTODON_ADAPTER] Publication failed: {e}")
            return {
                "platform": "mastodon",
                "status": "error",
                "error": str(e)
            }
