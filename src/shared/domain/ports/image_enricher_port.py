"""Port abstraction for image enrichment with metadata."""

from abc import ABC, abstractmethod
from typing import List


class ImageEnricherPort(ABC):
    """Port for enriching images with metadata and optimization."""

    @abstractmethod
    def enrich(self, posts: List[dict], articles: List[dict]) -> None:
        """
        Enrich posts and articles with image metadata.

        Args:
            posts: List of generated posts to enrich
            articles: List of generated articles to enrich
        """
        pass
