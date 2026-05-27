"""UseCase: Process URL and publish to social media.

Orchestrates:
1. Content extraction and article generation (NewsToNewsUseCase)
2. Social media publishing (SocialMediaPublisher)

Separation of concerns:
- NewsToNewsUseCase handles URL → Article/Tweet/TTS/Video
- SocialMediaPublisher handles Tweet → Social Networks
- This class orchestrates both
"""

from typing import Dict, Any, Optional

from config.logging_config import get_logger
from config.settings import Settings
from src.news.domain.ports import ContentExtractor

logger = get_logger("news_bot.usecase.process_url_with_publishing")


class ProcessUrlWithPublishingUseCase:
    """Process a URL, generate content, and publish to social networks."""

    def __init__(
        self,
        content_extractor: ContentExtractor,
        use_ai: bool = True,
        model_provider: str = Settings.AI_PROVIDER,
        ai_config: Optional[dict] = None,
        publish_to_social: bool = True,
    ):
        self.content_extractor = content_extractor
        self.use_ai = use_ai
        self.model_provider = model_provider
        self.ai_config = ai_config or {}
        self.publish_to_social = publish_to_social

    def execute(self, url: str) -> Dict[str, Any]:
        """
        Process URL and optionally publish to social networks.

        Returns dict with:
            - source_content: extracted content
            - article: generated article
            - post: generated tweet
            - article_file: path to article file
            - publish_results: results from social publishing (if enabled)
        """
        logger.info(f"[PROCESS_URL_WITH_PUB] Starting: {url}")

        # Step 1: Process URL → Extract content + Generate article/tweet/TTS/video
        logger.info("[PROCESS_URL_WITH_PUB] Step 1: Processing URL with NewsToNewsUseCase")
        result = self._process_url_content(url)

        # Step 2: Publish to social media (if enabled)
        if self.publish_to_social:
            logger.info("[PROCESS_URL_WITH_PUB] Step 2: Publishing to social networks")
            publish_results = self._publish_to_social(result)
            result["publish_results"] = publish_results
        else:
            logger.info("[PROCESS_URL_WITH_PUB] Publishing disabled, skipping")

        logger.info("[PROCESS_URL_WITH_PUB] ✅ Completed")
        return result

    def _process_url_content(self, url: str) -> Dict[str, Any]:
        """Process URL: extract content, generate article, tweet, TTS, video."""
        from src.news.application.usecases.news_to_news import process_news_url

        result = process_news_url(
            url=url,
            content_extractor=self.content_extractor,
            model_provider=self.model_provider,
            use_ai=self.use_ai,
            ai_config=self.ai_config,
            force_extract=True,
        )
        return result

    def _publish_to_social(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Publish the generated tweet to all social networks."""
        from src.shared.adapters.publishers.social import SocialMediaPublisher

        try:
            post_text = result.get("post", "")
            url = result.get("article_data", {}).get("article", {}).get("url", "")

            post_data = {
                "tweet": post_text,
                "url": url,
                "wp_url": "",
                "image_url": "",
            }

            publisher = SocialMediaPublisher(enable_bluesky=True, enable_mastodon=True)
            publish_results = publisher.publish(post_data)

            logger.info(f"[PROCESS_URL_WITH_PUB] Published to {len(publish_results)} platforms")
            return publish_results

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[PROCESS_URL_WITH_PUB] Publishing error: {error_msg}")
            raise
