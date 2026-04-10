"""Audio pipeline orchestrator.

This use-case orchestrates the complete audio-to-article processing pipeline.
"""

import logging
from typing import Dict, Any, List, Optional

from src.audio.infrastructure.adapters.audio_fetcher import (
    download_audio,
    has_audio_stream,
)
from src.audio.infrastructure.adapters.audio_transcriber import transcribe_audio
from src.audio.application.usecases.article_from_audio import run_from_audio
from src.shared.application.usecases.base_pipeline import BasePipelineUseCase

logger = logging.getLogger("audio_bot")


class AudioPipelineUseCase(BasePipelineUseCase):
    """Orchestrates complete audio processing pipeline."""

    def __init__(self, no_publish: bool = False):
        super().__init__(mode="audio", no_publish=no_publish)

    def run(self, url: str, tema: str) -> Dict[str, Any]:
        logger.info("[1/10] Downloading audio")

        transcript = ""
        audio_path: Optional[str] = None

        try:
            audio_path = download_audio(url)
            if not audio_path or not has_audio_stream(audio_path):
                raise RuntimeError(f"Audio without valid stream: {url}")

            self._track_temp_file(audio_path)
            logger.info("[1/10] Audio downloaded, transcribing...")
            transcript = transcribe_audio(audio_path)
            logger.info(
                f"[1/10] Transcription completed: {len(transcript)} characters"
            )

        except Exception as e:
            logger.error(f"[1/10] Error downloading/transcribing audio: {e}")
            raise RuntimeError(f"Error in audio download/transcription: {e}") from e

        logger.info("[2/10] Generating article and posts")
        try:
            result = run_from_audio(
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
