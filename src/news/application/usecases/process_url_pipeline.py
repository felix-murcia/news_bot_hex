"""Pipeline for processing a concrete URL.

Extracts content from the URL, inserts it as a VerifiedArticle, then runs
the exact same steps as the automatic pipeline (run_content → run_article →
images → audio → video → WordPress → social). No duplicate prompts or logic.
"""

import os
import time
from datetime import datetime
from typing import Optional

from config.logging_config import get_logger
from src.news.application.usecases.metrics_collector import MetricsCollector
from src.news.domain.entities.processing_metric import PipelineType
from src.news.domain.ports.metrics_repository_port import MetricsRepositoryPort

logger = get_logger("news_bot.pipeline.process_url")


class ProcessUrlPipeline:

    def __init__(self, content_extractor, metrics_repo: Optional[MetricsRepositoryPort] = None):
        self.content_extractor = content_extractor
        self.metrics_repo = metrics_repo

    def execute(self, url: str, job_id: Optional[str] = None) -> dict:
        logger.info(f"[PROCESS_URL] Starting pipeline for: {url}")

        metrics = None
        if self.metrics_repo and job_id:
            metrics = MetricsCollector(
                execution_id=job_id,
                pipeline_type=PipelineType.NEWS,
                metrics_repo=self.metrics_repo,
            )

        def run_step(name: str, fn, critical: bool = False):
            t = time.time_ns()
            try:
                fn()
                ms = (time.time_ns() - t) // 1_000_000
                if metrics:
                    metrics.record_step(name, "OK", ms)
                logger.info(f"[PROCESS_URL] ✅ {name} ({ms}ms)")
            except Exception as e:
                ms = (time.time_ns() - t) // 1_000_000
                if metrics:
                    metrics.record_step(name, "FAILED", ms, str(e))
                if critical:
                    raise
                logger.warning(f"[PROCESS_URL] ⚠️ {name} falló (no crítico): {e}")

        # ── Step 1: Extract content ─────────────────────────────────────────
        t = time.time_ns()
        content, _ = self.content_extractor.extract(url)
        if not content or len(content) < 100:
            raise ValueError(f"No se pudo extraer contenido suficiente de: {url}")
        ms = (time.time_ns() - t) // 1_000_000
        if metrics:
            metrics.record_step("Extract Content", "OK", ms)
        logger.info(f"[PROCESS_URL] ✅ Extract Content ({len(content)} chars, {ms}ms)")

        # ── Step 2: Save as VerifiedArticle → verified_news ────────────────
        def save_verified():
            from src.news.domain.entities.verified_article import VerifiedArticle
            from src.news.infrastructure.adapters import MongoVerifiedNewsRepository

            title = next((l.strip() for l in content.splitlines() if l.strip()), url)[:200]

            article = VerifiedArticle(
                title=title,
                desc=content[:500],
                source="web",
                origin="URL directa",
                url=url,
                publishedAt=datetime.now(),
                tema="Noticias",
                resumen=content[:500],
                score=10,
                model_prediction="real",
                confidence=0.95,
                verification={"verified": True},
                content=content,
                original_url=url,
                title_es=title,
                source_url=url,
            )

            repo = MongoVerifiedNewsRepository()
            repo.delete_all_news()
            repo.insert_news([article])

        run_step("Save Verified Article", save_verified, critical=True)

        # ── Steps 3-4: Same generation as automatic pipeline ───────────────
        def generate_posts():
            from src.news.application.usecases.content import run_content
            run_content(use_gemini=True, mode="news")

        def generate_articles():
            from src.news.application.usecases.article import run as run_article
            run_article(use_gemini=True)

        run_step("Generate Posts", generate_posts, critical=True)
        run_step("Generate Articles", generate_articles, critical=True)

        # ── Steps 5-10: Same publishing as automatic pipeline ──────────────
        def fetch_images():
            from src.shared.adapters.unsplash_fetcher import run as run_unsplash
            from src.shared.adapters.google_images_fetcher import run as run_google
            run_unsplash()
            run_google()

        def enrich_images():
            from src.shared.adapters.image_enricher import run as run_enricher
            run_enricher()

        def generate_audio():
            from src.shared.application.usecases.tts_from_article import run_tts_from_articles
            from src.shared.adapters.mongo_db import get_database
            db = get_database()
            coll = db["generated_articles"]
            articles = list(coll.find({}))
            if articles:
                updated = run_tts_from_articles(articles)
                for article in updated:
                    if article.get("tts_audio_path"):
                        coll.update_one(
                            {"_id": article["_id"]},
                            {"$set": {"tts_audio_path": article["tts_audio_path"]}},
                        )

        def generate_video():
            from src.shared.adapters.video_generator import get_video_generator
            from src.shared.adapters.mongo_db import get_database
            db = get_database()
            coll = db["generated_articles"]
            video_gen = get_video_generator()
            if video_gen.is_available():
                for article in list(coll.find({})):
                    audio_path = article.get("tts_audio_path")
                    if audio_path and os.path.exists(audio_path):
                        video_path = video_gen.create_video_from_audio(audio_path=audio_path)
                        if video_path:
                            coll.update_one(
                                {"_id": article["_id"]},
                                {"$set": {"generated_video_path": video_path}},
                            )

        def publish_wordpress():
            from src.shared.adapters.wordpress_publisher import run as run_wordpress
            run_wordpress()

        def publish_social():
            from src.shared.adapters.bluesky_publisher import run as run_bluesky
            from src.shared.adapters.mastodon_publisher import run as run_mastodon
            from src.shared.adapters.facebook_publisher import run as run_facebook
            for fn in (run_bluesky, run_mastodon, run_facebook):
                try:
                    fn()
                except Exception as e:
                    logger.warning(f"[PROCESS_URL] Social publisher error: {e}")

        run_step("Fetch Images", fetch_images)
        run_step("Enrich Images", enrich_images)
        run_step("Generate Audio", generate_audio)
        run_step("Generate Video", generate_video)
        run_step("Publish WordPress", publish_wordpress)
        run_step("Publish Social", publish_social)

        if metrics:
            try:
                metrics.flush()
            except Exception as e:
                logger.warning(f"[PROCESS_URL] Could not flush metrics: {e}")

        # Return compatible dict for ProcessUrlJobCoordinator
        from src.shared.adapters.mongo_db import get_database
        db = get_database()
        article = db["generated_articles"].find_one({}, {"_id": 0}) or {}
        post = db["generated_posts"].find_one({}, {"_id": 0}) or {}

        logger.info("[PROCESS_URL] ✅ Pipeline completed")
        return {
            "article_data": {"article": article},
            "post": post.get("tweet", ""),
            "mode": "gemini",
            "publish_results": [],
        }
