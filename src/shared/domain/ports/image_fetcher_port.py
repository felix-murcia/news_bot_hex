"""Port abstraction for image fetching from multiple sources."""

from abc import ABC, abstractmethod
from typing import List


class ImageFetcherPort(ABC):
    """Port for fetching images from various sources (Unsplash, Google, etc.)."""

    @abstractmethod
    def fetch(self, posts: List[dict]) -> None:
        """
        Fetch images for posts from configured sources.

        Args:
            posts: List of post dicts with title/content for image search
        """
        pass
