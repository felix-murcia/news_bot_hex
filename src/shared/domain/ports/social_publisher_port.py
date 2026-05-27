"""Port abstraction for social media publishing (polymorphic)."""

from abc import ABC, abstractmethod
from typing import Dict, Any


class SocialPublisherPort(ABC):
    """Port for publishing to a single social media platform."""

    @abstractmethod
    def publish(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Publish post to platform.

        Args:
            post_data: Dict with 'tweet', 'url', 'wp_url', 'image_url'

        Returns:
            Dict with publication result
            Example: {"status": "ok", "url": "https://platform.com/post-id", "platform": "bluesky"}
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if publisher is configured and available."""
        pass
