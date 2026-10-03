"""Pipeline for processing a concrete URL.

Extracts content from the URL, inserts it as a VerifiedArticle, then runs
the exact same steps as the automatic pipeline (run_content → run_article →
images → audio → video → WordPress → social). No duplicate prompts or logic.
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor
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

        # ── Step 3: Generate Posts (same as automatic pipeline) ─────────────
        def generate_posts():
            from src.news.application.usecases.content import run_content
            run_content(use_gemini=True, mode="news")

        run_step("Generate Posts", generate_posts, critical=True)

        # ── Steps 4-5: Generate Articles ‖ Fetch Images (parallel) ─────────
        # F4: Generate Articles (writes generated_articles) and Fetch Images
        # (reads/writes generated_posts) are independent: Fetch Images does NOT
        # read generated_articles. Run them in parallel and join before
        # Enrich Images. Both are critical: exceptions propagate via .result().
        def generate_articles():
            from src.news.application.usecases.article import run as run_article
            run_article(use_gemini=True)

        def fetch_images():
            from src.shared.infrastructure.composition_root import run_image_unsplash, run_image_google
            run_image_unsplash()
            run_image_google()

        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_articles = executor.submit(run_step, "Generate Articles", generate_articles, True)
            fut_images = executor.submit(run_step, "Fetch Images", fetch_images, True)
            # Join: wait for both. Articles first to preserve the original
            # priority (if both fail, the articles error is the one raised).
            fut_articles.result()
            fut_images.result()

        # ── Step 6: Enrich Images ───────────────────────────────────────────
        def enrich_images():
            from src.shared.infrastructure.composition_root import run_image_enricher
            run_image_enricher()

        run_step("Enrich Images", enrich_images, critical=True)

        # ── F12: read generated_articles ONCE (stable after enrich) ────────
        # Reused by Generate Audio, Generate Video and the final read, instead
        # of re-querying MongoDB at each step.
        from src.shared.adapters.mongo_db import get_database
        db = get_database()
        articles_list = list(db["generated_articles"].find({}))

        # ── Step 7: Generate Audio ──────────────────────────────────────────
        def generate_audio():
            from src.shared.application.usecases.tts_from_article import run_tts_from_articles
            coll = db["generated_articles"]
            if articles_list:
                updated = run_tts_from_articles(articles_list)
                for article in updated:
                    if article.get("tts_audio_path"):
                        coll.update_one(
                            {"_id": article["_id"]},
                            {"$set": {"tts_audio_path": article["tts_audio_path"]}},
                        )

        run_step("Generate Audio", generate_audio, critical=True)

        # ── Step 8: Generate Video ──────────────────────────────────────────
        def generate_video():
            from src.shared.infrastructure.composition_root import create_video_generator
            coll = db["generated_articles"]
            posts_coll = db["generated_posts"]
            video_gen = create_video_generator()
            if video_gen.is_available():
                for article in articles_list:
                    audio_path = article.get("tts_audio_path")
                    if audio_path and os.path.exists(audio_path):
                        video_path = video_gen.create_video_from_audio(audio_path=audio_path)
                        if video_path:
                            coll.update_one(
                                {"_id": article["_id"]},
                                {"$set": {"generated_video_path": video_path}},
                            )
                            # F3: propagate video_path to generated_posts so
                            # Facebook (which reads post["video_path"]) can
                            # publish the video in the URL/API flow.
                            original_url = article.get("original_url")
                            if original_url:
                                posts_coll.update_one(
                                    {"url": original_url},
                                    {"$set": {"video_path": video_path}},
                                )

        run_step("Generate Video", generate_video, critical=True)

        # ── Step 9: Publish WordPress ───────────────────────────────────────
        def publish_wordpress():
            from src.shared.infrastructure.composition_root import run_wordpress
            run_wordpress()

        run_step("Publish WordPress", publish_wordpress, critical=True)

        # ── Step 10: Publish Social ─────────────────────────────────────────
        def publish_social():
            from src.shared.infrastructure.composition_root import run_bluesky, run_mastodon, run_facebook
            for fn in (run_bluesky, run_mastodon, run_facebook):
                try:
                    fn()
                except Exception as e:
                    logger.error(f"[PROCESS_URL] Social publisher error: {e}")
                    raise RuntimeError(f"Social publisher crítico falló: {e}")

        run_step("Publish Social", publish_social, critical=True)

        if metrics:
            try:
                metrics.flush()
            except Exception as e:
                logger.warning(f"[PROCESS_URL] Could not flush metrics: {e}")

        # Return compatible dict for ProcessUrlJobCoordinator
        # F12: reuse articles_list (already enriched with tts_audio_path and
        # generated_video_path by the steps above) instead of re-reading.
        article = dict(articles_list[0]) if articles_list else {}
        article.pop("_id", None)
        post = db["generated_posts"].find_one({}, {"_id": 0}) or {}

        logger.info("[PROCESS_URL] ✅ Pipeline completed")
        return {
            "article_data": {"article": article},
            "post": post.get("tweet", ""),
            "mode": "gemini",
            "publish_results": [],
        }
