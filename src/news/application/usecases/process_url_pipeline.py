"""Unified pipeline orchestrator for URL processing with pluggable steps."""

from typing import Callable, Dict, Any, List, Optional
from abc import ABC, abstractmethod
from config.logging_config import get_logger
from src.shared.domain.ports.image_fetcher_port import ImageFetcherPort
from src.shared.domain.ports.image_enricher_port import ImageEnricherPort
from src.shared.domain.ports.wordpress_publisher_port import WordPressPublisherPort
from src.shared.domain.ports.social_publisher_port import SocialPublisherPort
from src.shared.domain.ports.video_generator_port import VideoGeneratorPort

logger = get_logger("news_bot.pipeline.orchestrator")


class PipelineStep(ABC):
    """Base class for pipeline execution steps."""

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute step and mutate context.

        Args:
            context: Pipeline context dict (url, articles, posts, results, etc.)

        Returns:
            Updated context
        """
        pass

    @abstractmethod
    def name(self) -> str:
        """Return step name for logging."""
        pass


class ProcessURLStep(PipelineStep):
    """Step 1: Process URL and extract content."""

    def __init__(self, content_processor: Callable[[str], Dict[str, Any]]):
        self.content_processor = content_processor

    def name(self) -> str:
        return "Process URL"

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[PIPELINE] Step 1: {self.name()}")
        url = context.get("url")
        result = self.content_processor(url)
        context["content_result"] = result
        context["article_data"] = result.get("article_data", {})
        context["post"] = result.get("post", "")
        return context


class FetchImagesStep(PipelineStep):
    """Step 2: Fetch images from multiple sources."""

    def __init__(self, image_fetcher: ImageFetcherPort):
        self.image_fetcher = image_fetcher

    def name(self) -> str:
        return "Fetch Images"

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[PIPELINE] Step 2: {self.name()}")
        posts = context.get("posts", [])
        self.image_fetcher.fetch(posts)
        return context


class EnrichImagesStep(PipelineStep):
    """Step 3: Enrich images with metadata."""

    def __init__(self, image_enricher: ImageEnricherPort):
        self.image_enricher = image_enricher

    def name(self) -> str:
        return "Enrich Images"

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[PIPELINE] Step 3: {self.name()}")
        posts = context.get("posts", [])
        articles = context.get("articles", [])
        self.image_enricher.enrich(posts, articles)
        return context


class GenerateAudioStep(PipelineStep):
    """Step 4: Generate audio from articles (TTS)."""

    def __init__(self, db):
        self.db = db

    def name(self) -> str:
        return "Generate Audio"

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[PIPELINE] Step 4: {self.name()}")
        try:
            from src.shared.application.usecases.tts_from_article import run_tts_from_articles

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
            context["articles"] = articles
        except Exception as e:
            logger.warning(f"[PIPELINE] Step {self.name()} warning: {e}")
            # TTS is non-fatal
        return context


class GenerateVideoStep(PipelineStep):
    """Step 5: Generate video from audio."""

    def __init__(self, video_generator: VideoGeneratorPort, db):
        self.video_generator = video_generator
        self.db = db

    def name(self) -> str:
        return "Generate Video"

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[PIPELINE] Step 5: {self.name()}")
        try:
            if self.video_generator and self.video_generator.is_available():
                articles_coll = self.db["generated_articles"]
                articles = list(articles_coll.find({}))
                for article in articles:
                    audio_path = article.get("tts_audio_path")
                    if audio_path:
                        import os
                        if os.path.exists(audio_path):
                            video_path = self.video_generator.create_video_from_audio(
                                audio_path=audio_path
                            )
                            if video_path:
                                articles_coll.update_one(
                                    {"_id": article["_id"]},
                                    {"$set": {"generated_video_path": video_path}},
                                )
        except Exception as e:
            logger.warning(f"[PIPELINE] Step {self.name()} warning: {e}")
            # Video generation is non-fatal
        return context


class PublishWordPressStep(PipelineStep):
    """Step 6: Publish to WordPress."""

    def __init__(self, wp_publisher: WordPressPublisherPort):
        self.wp_publisher = wp_publisher

    def name(self) -> str:
        return "Publish WordPress"

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[PIPELINE] Step 6: {self.name()}")
        result = self.wp_publisher.publish()
        context["wordpress_url"] = result.get("url", "")
        context["wordpress_result"] = result
        return context


class PublishSocialStep(PipelineStep):
    """Step 7: Publish to social networks."""

    def __init__(self, social_publishers: List[SocialPublisherPort]):
        self.social_publishers = social_publishers

    def name(self) -> str:
        return "Publish Social"

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[PIPELINE] Step 7: {self.name()}")
        wp_url = context.get("wordpress_url", "")
        post_content = context.get("post", "")
        url = context.get("url", "")

        post_data = {
            "tweet": post_content,
            "url": url,
            "wp_url": wp_url,
            "image_url": "",  # Would come from posts collection
        }

        results = []
        for publisher in self.social_publishers:
            try:
                result = publisher.publish(post_data)
                results.append(result)
            except Exception as e:
                logger.warning(f"[PIPELINE] Social publisher error: {e}")
                results.append({"status": "error", "error": str(e)})

        context["publish_results"] = results
        return context


class ProcessUrlPipeline:
    """Unified pipeline orchestrator for complete URL processing."""

    def __init__(
        self,
        content_processor: Callable[[str], Dict[str, Any]],
        image_fetcher: ImageFetcherPort,
        image_enricher: ImageEnricherPort,
        video_generator: VideoGeneratorPort,
        wp_publisher: WordPressPublisherPort,
        social_publishers: List[SocialPublisherPort],
        db,
    ):
        """Initialize with all dependencies."""
        self.steps: List[PipelineStep] = [
            ProcessURLStep(content_processor),
            FetchImagesStep(image_fetcher),
            EnrichImagesStep(image_enricher),
            GenerateAudioStep(db),
            GenerateVideoStep(video_generator, db),
            PublishWordPressStep(wp_publisher),
            PublishSocialStep(social_publishers),
        ]
        self.db = db

    def execute(self, url: str) -> Dict[str, Any]:
        """Execute complete pipeline for a URL."""
        logger.info(f"[PIPELINE] Starting pipeline for: {url}")

        context = {
            "url": url,
            "content_result": None,
            "article_data": {},
            "post": "",
            "posts": [],
            "articles": [],
            "wordpress_url": "",
            "publish_results": [],
        }

        try:
            # Save article and post to database
            posts_coll = self.db["generated_posts"]
            articles_coll = self.db["generated_articles"]

            for step in self.steps:
                try:
                    context = step.execute(context)
                except Exception as e:
                    logger.error(f"[PIPELINE] Step {step.name()} failed: {e}", exc_info=True)
                    # For critical steps (ProcessURL, Publish), re-raise
                    if step.name() in ["Process URL", "Publish WordPress"]:
                        raise
                    # For non-critical steps, continue
                    logger.warning(f"[PIPELINE] Continuing after {step.name()} error")

            logger.info("[PIPELINE] ✅ Pipeline completed successfully")
            return context

        except Exception as e:
            logger.error(f"[PIPELINE] Pipeline failed: {e}", exc_info=True)
            raise
