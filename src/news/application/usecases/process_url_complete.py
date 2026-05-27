"""UseCase: Complete URL processing pipeline (matches automatic pipeline).

Single Responsibility: Orchestrates the 9-step pipeline.
Reuses existing pipeline adapters and services (DRY principle).
"""

from typing import Dict, Any
from config.logging_config import get_logger
from src.shared.adapters.mongo_db import get_database

logger = get_logger("news_bot.usecase.process_url_complete")


class ProcessUrlCompleteUseCase:
    """Orchestrates complete URL processing pipeline - reuses pipeline adapters."""

    def __init__(self):
        """Pure orchestrator - no dependencies to inject."""
        self.db = get_database()

    def execute(self, url: str) -> Dict[str, Any]:
        """Execute 9-step pipeline: process → fetch images → enrich → audio → video → wordpress → social."""
        logger.info(f"[PROCESS_URL_COMPLETE] Starting complete flow: {url}")

        try:
            # Step 1: Process URL (content extraction)
            logger.info("[PROCESS_URL_COMPLETE] Step 1: Processing URL")
            result = self._process_url(url)

            # Step 2: Save article and post
            self.db["generated_articles"].insert_one(result.get("article_data", {}))
            self.db["generated_posts"].insert_one(result.get("post", {}))

            # Step 3: Fetch images from Unsplash + Google
            logger.info("[PROCESS_URL_COMPLETE] Step 2: Fetching images")
            from src.shared.adapters.unsplash_fetcher import run as run_unsplash
            from src.shared.adapters.google_images_fetcher import run as run_google
            run_unsplash()
            run_google()

            # Step 4: Enrich images with metadata
            logger.info("[PROCESS_URL_COMPLETE] Step 3: Enriching images")
            from src.shared.adapters.image_enricher import run as run_enricher
            run_enricher()

            # Step 5: Generate audio (TTS)
            logger.info("[PROCESS_URL_COMPLETE] Step 4: Generating audio")
            from src.shared.application.usecases.tts_from_article import (
                run_tts_from_articles,
            )
            articles_coll = self.db["generated_articles"]
            articles = list(articles_coll.find({}))
            if articles:
                updated = run_tts_from_articles(articles)
                for article in updated:
                    if article.get("tts_audio_path"):
                        articles_coll.update_one(
                            {"_id": article["_id"]},
                            {"$set": {"tts_audio_path": article["tts_audio_path"]}},
                        )

            # Step 6: Generate video
            logger.info("[PROCESS_URL_COMPLETE] Step 5: Generating video")
            from src.shared.adapters.video_generator import get_video_generator
            articles = list(articles_coll.find({}))
            video_gen = get_video_generator()
            if video_gen and video_gen.is_available():
                for article in articles:
                    audio_path = article.get("tts_audio_path")
                    if audio_path:
                        video_gen.generate(audio_path)

            # Step 7: Publish to WordPress
            logger.info("[PROCESS_URL_COMPLETE] Step 6: Publishing to WordPress")
            from src.shared.adapters.wordpress_publisher import run as run_wordpress
            wordpress_result = run_wordpress()
            wordpress_url = wordpress_result.get("url", "")

            # Step 8: Publish to social networks with image and WordPress URL
            logger.info("[PROCESS_URL_COMPLETE] Step 7: Publishing to social networks")
            from src.shared.adapters.publishers.social import SocialMediaPublisher
            publisher = SocialMediaPublisher(enable_bluesky=True, enable_mastodon=True)

            posts_coll = self.db["generated_posts"]
            posts = list(posts_coll.find({}))
            if posts:
                post = posts[-1]
                post_data = {
                    "tweet": result.get("post", ""),
                    "url": result.get("article_data", {}).get("article", {}).get("url", ""),
                    "wp_url": wordpress_url,
                    "image_url": post.get("image_url", ""),
                }
                publish_results = publisher.publish(post_data)
            else:
                publish_results = {}

            result["wordpress_url"] = wordpress_url
            result["publish_results"] = publish_results

            logger.info("[PROCESS_URL_COMPLETE] ✅ Complete flow finished")
            return result

        except Exception as e:
            logger.error(f"[PROCESS_URL_COMPLETE] Error in flow: {e}")
            raise

    def _process_url(self, url: str) -> Dict[str, Any]:
        """Process URL to extract content, generate article and post."""
        from src.news.application.usecases.news_to_news import process_news_url
        from config.settings import Settings

        return process_news_url(
            url=url,
            content_extractor=None,
            model_provider=Settings.AI_PROVIDER,
            use_ai=True,
            ai_config={},
            force_extract=True,
        )
