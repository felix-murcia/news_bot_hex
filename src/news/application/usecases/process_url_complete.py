"""UseCase: Complete URL processing pipeline (matches automatic pipeline).

Single Responsibility: Orchestrates the 9-step pipeline.
All dependencies injected via constructor (Dependency Inversion Principle).
"""

from typing import Dict, Any, Callable, List
from config.logging_config import get_logger
from src.shared.domain.ports.image_fetcher_port import ImageFetcherPort
from src.shared.domain.ports.image_enricher_port import ImageEnricherPort
from src.shared.domain.ports.wordpress_publisher_port import WordPressPublisherPort
from src.shared.domain.ports.social_publisher_port import SocialPublisherPort
from src.shared.domain.ports.video_generator_port import VideoGeneratorPort

logger = get_logger("news_bot.usecase.process_url_complete")


class ProcessUrlCompleteUseCase:
    """Orchestrates complete URL processing pipeline with all dependencies injected."""

    def __init__(
        self,
        content_processor: Callable[[str], Dict[str, Any]],
        image_fetcher_port: ImageFetcherPort,
        image_enricher_port: ImageEnricherPort,
        video_generator_port: VideoGeneratorPort,
        wordpress_publisher_port: WordPressPublisherPort,
        social_publishers: List[SocialPublisherPort],
        articles_repo,
        posts_repo,
        job_repo,
        db,
    ):
        """Initialize with all dependencies injected."""
        self.content_processor = content_processor
        self.image_fetcher_port = image_fetcher_port
        self.image_enricher_port = image_enricher_port
        self.video_generator_port = video_generator_port
        self.wordpress_publisher_port = wordpress_publisher_port
        self.social_publishers = social_publishers
        self.articles_repo = articles_repo
        self.posts_repo = posts_repo
        self.job_repo = job_repo
        self.db = db

    def execute(self, url: str) -> Dict[str, Any]:
        """Execute 9-step pipeline: process → fetch images → enrich → audio → video → wordpress → social."""
        logger.info(f"[PROCESS_URL_COMPLETE] Starting complete flow: {url}")

        try:
            # Step 1: Process URL (content extraction)
            logger.info("[PROCESS_URL_COMPLETE] Step 1: Processing URL")
            result = self.content_processor(url)

            # Step 2: Save article and post
            self.db["generated_articles"].insert_one(result.get("article_data", {}))
            self.db["generated_posts"].insert_one(result.get("post", {}))

            # Step 3: Fetch images from Unsplash + Google
            logger.info("[PROCESS_URL_COMPLETE] Step 2: Fetching images")
            posts_coll = self.db["generated_posts"]
            posts = list(posts_coll.find({}))
            self.image_fetcher_port.fetch(posts)

            # Step 4: Enrich images with metadata
            logger.info("[PROCESS_URL_COMPLETE] Step 3: Enriching images")
            articles_coll = self.db["generated_articles"]
            articles = list(articles_coll.find({}))
            self.image_enricher_port.enrich(posts, articles)

            # Step 5: Generate audio (TTS)
            logger.info("[PROCESS_URL_COMPLETE] Step 4: Generating audio")
            from src.shared.application.usecases.tts_from_article import (
                run_tts_from_articles,
            )
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
            articles = list(articles_coll.find({}))
            if self.video_generator_port.is_available():
                for article in articles:
                    audio_path = article.get("tts_audio_path")
                    if audio_path:
                        video_path = self.video_generator_port.create_video_from_audio(
                            audio_path=audio_path
                        )
                        if video_path:
                            articles_coll.update_one(
                                {"_id": article["_id"]},
                                {"$set": {"generated_video_path": video_path}},
                            )

            # Step 7: Publish to WordPress
            logger.info("[PROCESS_URL_COMPLETE] Step 6: Publishing to WordPress")
            wordpress_result = self.wordpress_publisher_port.publish()
            wordpress_url = wordpress_result.get("url", "")

            # Step 8: Publish to social networks
            logger.info("[PROCESS_URL_COMPLETE] Step 7: Publishing to social networks")
            posts = list(posts_coll.find({}))
            publish_results = []
            if posts:
                post = posts[-1]
                post_data = {
                    "tweet": result.get("post", ""),
                    "url": result.get("article_data", {}).get("article", {}).get("url", ""),
                    "wp_url": wordpress_url,
                    "image_url": post.get("image_url", ""),
                }
                for publisher in self.social_publishers:
                    try:
                        pub_result = publisher.publish(post_data)
                        publish_results.append(pub_result)
                    except Exception as e:
                        logger.warning(f"[PROCESS_URL_COMPLETE] Social publisher error: {e}")
                        publish_results.append({
                            "status": "error",
                            "error": str(e)
                        })

            result["wordpress_url"] = wordpress_url
            result["publish_results"] = publish_results

            logger.info("[PROCESS_URL_COMPLETE] ✅ Complete flow finished")
            return result

        except Exception as e:
            logger.error(f"[PROCESS_URL_COMPLETE] Error in flow: {e}")
            raise
