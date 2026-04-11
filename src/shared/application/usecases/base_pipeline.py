"""Base pipeline use case with shared logic for all media pipelines.

This abstract class extracts the common functionality between audio, video,
and news pipelines to avoid code duplication.
"""

import logging
import re
import tempfile
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.shared.adapters.image_enricher import ImageEnricher
from src.shared.adapters.wordpress_publisher import (
    publish_post,
    ensure_category,
    ensure_tag,
    upload_image_from_url,
)
from src.shared.adapters.publishers.social import SocialMediaPublisher

logger = logging.getLogger("news_bot")


class BasePipelineUseCase(ABC):
    """Abstract base class for all media processing pipelines.

    Provides common functionality for:
    - Image enrichment (Unsplash, Google Images, extraction from source)
    - WordPress publishing (category/tag management, image upload, post creation)
    - Social media publishing (X, LinkedIn, Facebook, Bluesky, Mastodon)
    - Temporary file cleanup
    """

    def __init__(
        self,
        mode: str,
        no_publish: bool = False,
        enable_bluesky: bool = True,
        enable_mastodon: bool = True,
    ):
        self.mode = mode
        self.no_publish = no_publish
        self._image_enricher: Optional[ImageEnricher] = None
        self._social_publisher: Optional[SocialMediaPublisher] = None
        self._enable_bluesky = enable_bluesky
        self._enable_mastodon = enable_mastodon
        self._temp_files: List[str] = []

    @property
    def image_enricher(self) -> ImageEnricher:
        """Lazy-loaded image enricher."""
        if self._image_enricher is None:
            self._image_enricher = ImageEnricher(mode=self.mode)
        return self._image_enricher

    @property
    def social_publisher(self) -> SocialMediaPublisher:
        """Lazy-loaded social media publisher."""
        if self._social_publisher is None:
            self._social_publisher = SocialMediaPublisher(
                enable_bluesky=self._enable_bluesky,
                enable_mastodon=self._enable_mastodon,
            )
        return self._social_publisher

    def _track_temp_file(self, file_path: str):
        """Track a temporary file for later cleanup."""
        if file_path and os.path.exists(file_path):
            self._temp_files.append(file_path)

    def _cleanup_temp_files(self):
        """Remove all tracked temporary files."""
        cleaned = 0
        for file_path in self._temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    cleaned += 1
                    logger.debug(f"[CLEANUP] Removed: {file_path}")
            except Exception as e:
                logger.warning(f"[CLEANUP] Failed to remove {file_path}: {e}")

        if cleaned > 0:
            logger.info(f"[CLEANUP] Removed {cleaned} temporary file(s)")
        self._temp_files.clear()

    def _enrich_with_images(
        self, articles: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Enrich articles with images from multiple sources.

        Steps:
        1. Try Unsplash
        2. Try Google Images
        3. Use ImageEnricher to select best option
        """
        logger.info("[IMAGE_ENRICHMENT] Fetching from Unsplash")
        try:
            from src.shared.adapters.unsplash_fetcher import UnsplashFetcher

            unsplash_fetcher = UnsplashFetcher(mode=self.mode)
            articles = unsplash_fetcher.fetch_for_posts(articles)
        except Exception as e:
            logger.warning(f"[IMAGE_ENRICHMENT] Unsplash error: {e}")

        logger.info("[IMAGE_ENRICHMENT] Fetching from Google Images")
        try:
            from src.shared.adapters.google_images_fetcher import GoogleImagesFetcher

            google_fetcher = GoogleImagesFetcher(mode=self.mode)
            articles = google_fetcher.fetch_for_posts(articles)
        except Exception as e:
            logger.warning(f"[IMAGE_ENRICHMENT] Google Images error: {e}")

        logger.info("[IMAGE_ENRICHMENT] Selecting best images")
        enriched = self.image_enricher.enrich(articles)
        logger.info(f"[IMAGE_ENRICHMENT] Enriched {len(enriched)} article(s)")

        return enriched

    def _publish_to_wordpress(
        self, article: Dict[str, Any], tema: str
    ) -> Optional[str]:
        """Publish an article to WordPress.

        Returns:
            WordPress post URL if successful, None otherwise
        """
        if self.no_publish:
            logger.info("[WORDPRESS] Publishing skipped (no-publish mode)")
            return None

        logger.info("[WORDPRESS] Publishing article")
        try:
            # Determine category
            topic = article.get("labels", [tema])[0] if article.get("labels") else tema
            # Normalize common topics to default category
            topic_normalization = {
                "Audio",
                "Podcast",
                "Video",
                "Política",
                "Política internacional",
            }
            if topic in topic_normalization:
                topic = "Noticias"

            category_id = ensure_category(topic)

            # Handle tags
            labels = article.get("labels", [])
            precomputed_tags = article.get("hashtags", [])
            all_tags = list(set(labels + precomputed_tags))
            tag_ids = [ensure_tag(t) for t in all_tags if isinstance(t, str)]
            tag_ids = [tid for tid in tag_ids if tid is not None]

            # Upload featured image
            image_url = article.get("image_url")
            featured_image_id = None
            if image_url and "nbes.blog" not in image_url:
                try:
                    featured_image_id = upload_image_from_url(
                        image_url,
                        alt_text=article.get("alt_text"),
                        credit=article.get("image_credit"),
                    )
                except Exception as e:
                    logger.warning(f"[WORDPRESS] Failed to upload image: {e}")

            # Clean content (remove h1 tags - WordPress uses title)
            content = article.get("content", "")
            content = re.sub(
                r"<h1[^>]*>.*?</h1>",
                "",
                content,
                flags=re.DOTALL | re.IGNORECASE,
            )
            content = content.strip()

            # Publish
            article_title = article.get("title") or "Untitled"
            wordpress_url = publish_post(
                title=article_title,
                content=content,
                categories=[category_id] if category_id else None,
                tags=tag_ids if tag_ids else None,
                is_draft=False,
                featured_image=featured_image_id,
                excerpt=article.get("excerpt"),
                slug=article.get("slug"),
                seo_title=None,
                focus_keyword=article_title,
                canonical_url=None,
            )

            if wordpress_url:
                logger.info(f"[WORDPRESS] ✅ Published: {wordpress_url}")
            else:
                logger.warning("[WORDPRESS] Failed to publish")

            return wordpress_url

        except Exception as e:
            logger.error(f"[WORDPRESS] Error publishing: {e}")
            return None

    def _publish_to_social(
        self, article: Dict[str, Any], tweet: str, source_url: str
    ) -> List[Dict[str, Any]]:
        """Publish to social media platforms.

        Returns:
            List of publishing results per platform
        """
        if self.no_publish:
            logger.info("[SOCIAL] Publishing skipped (no-publish mode)")
            return []

        logger.info("[SOCIAL] Publishing to social media")
        try:
            post_for_social = {
                "tweet": tweet,
                "wp_url": article.get("wp_url", article.get("url", "")),
                "url": source_url,
                "image_url": article.get("image_url", ""),
            }
            social_results = self.social_publisher.publish(post_for_social)
            logger.info(f"[SOCIAL] Published to {len(social_results)} platform(s)")
            return social_results
        except Exception as e:
            logger.error(f"[SOCIAL] Error publishing to social media: {e}")
            return []

    @abstractmethod
    def run(self, url: str, tema: str) -> Dict[str, Any]:
        """Execute the full pipeline.

        Args:
            url: Source URL (audio, video, or news)
            tema: Topic/category for the article

        Returns:
            Dictionary with pipeline results
        """
        raise NotImplementedError("Subclasses must implement run()")

    def build_result(
        self,
        url: str,
        transcript: str,
        article: Dict[str, Any],
        article_file: str,
        tweets: List[str],
        wordpress_url: Optional[str],
        social_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build a standardized result dictionary.

        Args:
            url: Source URL
            transcript: Transcription text
            article: Article dictionary
            article_file: Path to saved article file
            tweets: List of generated tweets
            wordpress_url: WordPress post URL
            social_results: Social media publishing results

        Returns:
            Standardized result dictionary
        """
        return {
            "url": url,
            "transcript": transcript,
            "article": article,
            "article_file": article_file,
            "images": [article.get("image_url", [])],
            "tweets": tweets,
            "wordpress_url": wordpress_url,
            "social_results": social_results,
            "mode": self.mode,
        }
