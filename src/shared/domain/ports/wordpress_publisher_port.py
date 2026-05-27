"""Port abstraction for WordPress publishing."""

from abc import ABC, abstractmethod
from typing import Dict, Any


class WordPressPublisherPort(ABC):
    """Port for publishing articles to WordPress."""

    @abstractmethod
    def publish(self) -> Dict[str, Any]:
        """
        Publish generated articles to WordPress.

        Returns:
            Dict with published status and URLs
            Example: {"status": "ok", "url": "https://site.com/article-slug"}
        """
        pass
