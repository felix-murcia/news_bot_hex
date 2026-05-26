"""Async pipeline executor with job tracking."""

import threading
from config.logging_config import get_logger
from src.news.application.usecases.pipeline_job import (
    JobStatus,
    update_job_status,
    add_step,
)
from src.news.application.usecases.pipeline_log_handler import (
    setup_pipeline_logging,
    teardown_pipeline_logging,
)

logger = get_logger("news_bot.pipeline.executor")


def execute_pipeline_async(job_id: str) -> None:
    """Execute pipeline in background thread with job tracking."""

    def run_pipeline():
        # Setup logging handler to capture real-time feedback for UI
        log_handler = setup_pipeline_logging(job_id)

        try:
            update_job_status(job_id, JobStatus.RUNNING, "Pipeline iniciado")
            logger.info(f"[PIPELINE-JOB] {job_id} iniciado")

            # Step 1: Fetch RSS
            add_step(job_id, "RSS Fetch", "running")
            try:
                from src.news.entrypoints.cli import main_rss

                main_rss()
                add_step(job_id, "RSS Fetch", "ok")
                logger.info(f"[PIPELINE-JOB] {job_id} RSS completado")
            except Exception as e:
                logger.error(f"[PIPELINE-JOB] {job_id} Error en RSS: {e}")
                add_step(job_id, "RSS Fetch", "error")
                # Abort the pipeline on any error, especially AI provider failures
                raise

            # Step 2: Full Verification
            add_step(job_id, "Full Verification", "running")
            try:
                from src.news.entrypoints.cli import main_full_verify

                main_full_verify()
                add_step(job_id, "Full Verification", "ok")
                logger.info(f"[PIPELINE-JOB] {job_id} Verification completada")
            except Exception as e:
                logger.error(f"[PIPELINE-JOB] {job_id} Error en Verification: {e}")
                add_step(job_id, "Full Verification", "error")
                raise

            # Step 3: Generate Posts
            add_step(job_id, "Generate Posts", "running")
            try:
                from src.news.application.usecases.content import run_content

                run_content(use_gemini=True, mode="news")
                add_step(job_id, "Generate Posts", "ok")
                logger.info(f"[PIPELINE-JOB] {job_id} Posts generados")
            except Exception as e:
                logger.error(f"[PIPELINE-JOB] {job_id} Error en Posts: {e}")
                add_step(job_id, "Generate Posts", "error")
                raise

            # Step 4: Generate Articles
            add_step(job_id, "Generate Articles", "running")
            try:
                from src.news.application.usecases.article import run as run_article

                run_article(use_gemini=True)
                add_step(job_id, "Generate Articles", "ok")
                logger.info(f"[PIPELINE-JOB] {job_id} Artículos generados")
            except Exception as e:
                logger.error(f"[PIPELINE-JOB] {job_id} Error en Articles: {e}")
                add_step(job_id, "Generate Articles", "error")
                raise

            # Step 5: Fetch Images
            add_step(job_id, "Fetch Images", "running")
            try:
                from src.shared.adapters.unsplash_fetcher import run as run_unsplash
                from src.shared.adapters.google_images_fetcher import run as run_google

                run_unsplash()
                run_google()
                add_step(job_id, "Fetch Images", "ok")
                logger.info(f"[PIPELINE-JOB] {job_id} Imágenes descargadas")
            except Exception as e:
                logger.error(f"[PIPELINE-JOB] {job_id} Error en Images: {e}")
                add_step(job_id, "Fetch Images", "error")
                raise

            # Step 6: Enrich Images
            add_step(job_id, "Enrich Images", "running")
            try:
                from src.shared.adapters.image_enricher import run as run_enricher

                run_enricher()
                add_step(job_id, "Enrich Images", "ok")
                logger.info(f"[PIPELINE-JOB] {job_id} Imágenes enriquecidas")
            except Exception as e:
                logger.error(f"[PIPELINE-JOB] {job_id} Error en Enrichment: {e}")
                add_step(job_id, "Enrich Images", "error")
                raise

            # Step 7: Generate Audio (TTS)
            add_step(job_id, "Generate Audio", "running")
            try:
                from src.shared.application.usecases.tts_from_article import (
                    run_tts_from_articles,
                )
                from src.shared.adapters.mongo_db import get_database

                db = get_database()
                articles_coll = db["generated_articles"]
                articles = list(articles_coll.find({}))

                if articles:
                    updated = run_tts_from_articles(articles)
                    for article in updated:
                        if article.get("tts_audio_path"):
                            articles_coll.update_one(
                                {"_id": article["_id"]},
                                {"$set": {"tts_audio_path": article["tts_audio_path"]}},
                            )
                    logger.info(f"[PIPELINE-JOB] {job_id} Audio generado")
                add_step(job_id, "Generate Audio", "ok")
            except Exception as e:
                logger.warning(f"[PIPELINE-JOB] {job_id} Warning en Audio: {e}")
                add_step(job_id, "Generate Audio", "skipped")
                raise

            # Step 8: Generate Video
            add_step(job_id, "Generate Video", "running")
            try:
                from src.shared.adapters.video_generator import get_video_generator
                import os

                db = get_database()
                articles_coll = db["generated_articles"]
                articles = list(articles_coll.find({}))

                video_gen = get_video_generator()
                if video_gen.is_available():
                    for article in articles:
                        audio_path = article.get("tts_audio_path")
                        if audio_path and os.path.exists(audio_path):
                            try:
                                video_path = video_gen.create_video_from_audio(
                                    audio_path=audio_path
                                )
                                if video_path:
                                    articles_coll.update_one(
                                        {"_id": article["_id"]},
                                        {"$set": {"generated_video_path": video_path}},
                                    )
                            except Exception as e:
                                logger.warning(f"Error generando video: {e}")
                    logger.info(f"[PIPELINE-JOB] {job_id} Videos generados")
                add_step(job_id, "Generate Video", "ok")
            except Exception as e:
                logger.warning(f"[PIPELINE-JOB] {job_id} Warning en Video: {e}")
                add_step(job_id, "Generate Video", "skipped")
                raise

            # Step 9: WordPress
            add_step(job_id, "Publish WordPress", "running")
            try:
                from src.shared.adapters.wordpress_publisher import run as run_wordpress

                run_wordpress()
                add_step(job_id, "Publish WordPress", "ok")
                logger.info(f"[PIPELINE-JOB] {job_id} WordPress publicado")
            except Exception as e:
                logger.error(f"[PIPELINE-JOB] {job_id} Error en WordPress: {e}")
                add_step(job_id, "Publish WordPress", "error")
                raise

            # Step 10: Social Networks
            add_step(job_id, "Publish Social", "running")
            social_ok = 0
            try:
                from src.shared.adapters.bluesky_publisher import run as run_bluesky

                run_bluesky()
                social_ok += 1
            except Exception as e:
                logger.warning(f"[PIPELINE-JOB] {job_id} Warning en Bluesky: {e}")

            try:
                from src.shared.adapters.facebook_publisher import run as run_facebook

                run_facebook()
                social_ok += 1
            except Exception as e:
                logger.warning(f"[PIPELINE-JOB] {job_id} Warning en Facebook: {e}")

            try:
                from src.shared.adapters.mastodon_publisher import run as run_mastodon

                run_mastodon()
                social_ok += 1
            except Exception as e:
                logger.warning(f"[PIPELINE-JOB] {job_id} Warning en Mastodon: {e}")

            add_step(job_id, "Publish Social", "ok")
            logger.info(
                f"[PIPELINE-JOB] {job_id} Redes sociales completadas ({social_ok}/3)"
            )

            update_job_status(job_id, JobStatus.COMPLETED, "Pipeline completado exitosamente")
            logger.info(f"[PIPELINE-JOB] {job_id} COMPLETADO")

        except Exception as e:
            logger.error(f"[PIPELINE-JOB] {job_id} Error general: {e}", exc_info=True)
            update_job_status(job_id, JobStatus.FAILED, f"Error: {str(e)}", error=str(e))

        finally:
            # Cleanup logging handler
            teardown_pipeline_logging(log_handler)

    # Run in background thread
    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()
