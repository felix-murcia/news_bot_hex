"""Adapter for Facebook social publishing."""

from typing import Dict, Any
from config.logging_config import get_logger
from src.shared.domain.ports.social_publisher_port import SocialPublisherPort

logger = get_logger("news_bot.adapter.facebook")


class FacebookPublisherAdapter(SocialPublisherPort):
    """Adapter for publishing to Facebook."""

    def __init__(self):
        """Initialize Facebook publisher adapter."""
        self._publisher = None
        try:
            from src.shared.adapters.facebook_publisher import FacebookPublisher
            self._publisher = FacebookPublisher()
            logger.info("[FACEBOOK_ADAPTER] Facebook publisher initialized")
        except Exception as e:
            logger.warning(f"[FACEBOOK_ADAPTER] Failed to initialize: {e}")

    def is_available(self) -> bool:
        """Check if Facebook publisher is available."""
        return self._publisher is not None

    def publish(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """Publish post to Facebook."""
        if not self.is_available():
            return {
                "platform": "facebook",
                "status": "skipped",
                "error": "Facebook not configured"
            }

        try:
            logger.info("[FACEBOOK_ADAPTER] Publishing to Facebook")
            result = self._publisher.publish_posts([post_data])
            logger.info(f"[FACEBOOK_ADAPTER] Published: {result}")
            return {
                "platform": "facebook",
                "status": "ok" if result.get("published", 0) > 0 else "error",
                "published": result.get("published", 0),
            }
        except Exception as e:
            logger.error(f"[FACEBOOK_ADAPTER] Publication failed: {e}")
            return {
                "platform": "facebook",
                "status": "error",
                "error": str(e)
            }
