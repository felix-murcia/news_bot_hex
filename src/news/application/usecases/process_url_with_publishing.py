"""UseCase: Process URL and publish to social media.

Orchestrates:
1. Content processing (delegated to content_processor)
2. Social media publishing (delegated to social_publisher)

Separation of concerns:
- This class only orchestrates, doesn't know implementation details
- Dependencies injected, not created inside
"""

from typing import Dict, Any, Optional, Callable

from config.logging_config import get_logger

logger = get_logger("news_bot.usecase.process_url_with_publishing")


class ProcessUrlWithPublishingUseCase:
    """Process a URL and optionally publish to social networks."""

    def __init__(
        self,
        content_processor: Callable[[str], Dict[str, Any]],
        social_publisher: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        publish_to_social: bool = True,
    ):
        """
        Args:
            content_processor: Function that processes URL → returns Dict with content/article/post
            social_publisher: Function that publishes result → returns Dict with publish results
            publish_to_social: Whether to publish (allows disabling without changing code)
        """
        self.content_processor = content_processor
        self.social_publisher = social_publisher
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
        logger.info("[PROCESS_URL_WITH_PUB] Step 1: Processing URL")
        result = self.content_processor(url)

        # Step 2: Publish to social media (if enabled)
        if self.publish_to_social and self.social_publisher:
            logger.info("[PROCESS_URL_WITH_PUB] Step 2: Publishing to social networks")
            publish_results = self.social_publisher(result)
            result["publish_results"] = publish_results
        else:
            logger.info("[PROCESS_URL_WITH_PUB] Publishing disabled, skipping")

        logger.info("[PROCESS_URL_WITH_PUB] ✅ Completed")
        return result
