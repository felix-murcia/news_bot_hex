"""Video pipeline orchestrator.

This use-case orchestrates the complete video-to-article processing pipeline
by coordinating download, transcription, article generation, image enrichment,
and publishing to WordPress and social media.
"""

import logging
import os
from typing import Dict, Any, List, Optional

from src.video.application.usecases.article_from_video import (
    run_from_video,
)
from src.shared.application.usecases.base_pipeline import BasePipelineUseCase

logger = logging.getLogger("news_bot")


class VideoPipelineUseCase(BasePipelineUseCase):
    """Orchestrates the complete video processing pipeline."""

    def __init__(self, no_publish: bool = False):
        super().__init__(mode="video", no_publish=no_publish)

    def run(self, url: str, tema: str) -> Dict[str, Any]:
        logger.info("[1/10] Downloading video and extracting audio")

        transcript = ""
        video_path: Optional[str] = None

        try:
            from src.video.infrastructure.adapters.video_fetcher import download_video
            from src.video.infrastructure.adapters.video_transcriber import (
                transcribe_video,
            )

            video_path = download_video(url)
            if not video_path or not os.path.exists(video_path):
                raise RuntimeError(f"Failed to download video: {url}")

            self._track_temp_file(video_path)
            logger.info("[1/10] Video downloaded, transcribing...")
            transcript = transcribe_video(video_path)
            logger.info(
                f"[1/10] Transcription completed: {len(transcript)} characters"
            )

        except Exception as e:
            logger.error(f"[1/10] Error downloading/transcribing video: {e}")
            raise RuntimeError(f"Error in video download/transcription: {e}") from e

        logger.info("[2/10] Generating article and posts")
        try:
            result = run_from_video(
                transcript=transcript, url=url, tema=tema, llm_provider="openrouter"
            )
        except Exception as e:
            logger.error(f"[2/10] Error in content generation: {e}")
            raise

        article = result["article"]
        tweet = result["tweet"]
        tweets: List[str] = [tweet]

        logger.info("[5/7] Enriching with images")
        articles_for_images = [article]
        enriched_articles = self._enrich_with_images(articles_for_images)
        enriched_article = enriched_articles[0]

        wordpress_url: Optional[str] = None
        if not self.no_publish:
            logger.info("[8/10] Publishing to WordPress")
            wordpress_url = self._publish_to_wordpress(enriched_article, tema)
            if wordpress_url:
                enriched_article["wp_url"] = wordpress_url

        logger.info("[9/10] Publishing to social media")
        social_results = self._publish_to_social(enriched_article, tweet, url)

        logger.info("[10/10] Cleaning up temporary files")
        self._cleanup_temp_files()

        return self.build_result(
            url=url,
            transcript=transcript,
            article=enriched_article,
            article_file=result.get("article_file", ""),
            tweets=tweets,
            wordpress_url=wordpress_url,
            social_results=social_results,
        )
