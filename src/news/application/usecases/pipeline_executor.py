"""Async pipeline executor with job tracking and metrics collection."""

import threading
import time
from datetime import datetime
from config.logging_config import get_logger
from src.news.application.usecases.pipeline_job import (
    JobStatus,
    ProcessingStepName,
    ProcessingStepStatus,
    update_job_status,
    add_step,
)
from src.news.application.usecases.pipeline_log_handler import (
    setup_pipeline_logging,
    teardown_pipeline_logging,
)
from src.news.domain.entities.processing_metric import (
    ProcessingMetric,
    StepMetric,
    PipelineType,
    StepStatus,
)

logger = get_logger("news_bot.pipeline.executor")

# Global execution lock - only one pipeline execution at a time
_execution_lock = threading.Lock()


def _format_duration(milliseconds: int) -> str:
    """Convert milliseconds to human-readable hh:mm:ss format."""
    total_seconds = milliseconds // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def execute_pipeline_async(job_id: str) -> bool:
    """
    Execute pipeline in background thread with job tracking and metrics collection.

    Returns:
        bool: True if execution started, False if another execution is in progress.
    """
    global _pipeline_running

    # Try to acquire lock without blocking
    if not _execution_lock.acquire(blocking=False):
        logger.warning(f"[PIPELINE-JOB] {job_id} Rejected: Pipeline already executing")
        return False

    logger.info(f"[PIPELINE-JOB] {job_id} Lock acquired - execution starting")

    def run_pipeline():
        try:
            # Setup logging handler to capture real-time feedback for UI
            log_handler = setup_pipeline_logging(job_id)
        except Exception as e:
            logger.error(f"[PIPELINE-JOB] {job_id} Error setup logging: {e}", exc_info=True)
            update_job_status(job_id, JobStatus.FAILED, f"Error en logging: {str(e)}", error=str(e))
            return

        # Initialize metrics collection
        metrics_steps = []
        pipeline_start_ns = time.time_ns()

        try:
            update_job_status(job_id, JobStatus.RUNNING, "Pipeline iniciado")
            logger.info(f"[PIPELINE-JOB] {job_id} iniciado")

            # Helper to record metrics for each step
            def record_step_metric(step_name: str, status: str, duration_ms: int, error: str = None):
                try:
                    step_status = StepStatus(status)
                except ValueError:
                    step_status = StepStatus.FAILED

                metrics_steps.append(StepMetric(
                    name=step_name,
                    status=step_status,
                    duration_ms=duration_ms,
                    error=error,
                ))

            # Step 1: Fetch RSS
            add_step(job_id, ProcessingStepName.RSS_FETCH, ProcessingStepStatus.RUNNING)
            step_start_ns = time.time_ns()
            try:
                from src.news.entrypoints.cli import main_rss

                main_rss()
                step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
                add_step(job_id, ProcessingStepName.RSS_FETCH, ProcessingStepStatus.OK)
                record_step_metric("RSS Fetch", "OK", step_duration_ms)
                logger.info(f"[PIPELINE-JOB] {job_id} RSS completado ({_format_duration(step_duration_ms)})")
            except Exception as e:
                step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
                logger.error(f"[PIPELINE-JOB] {job_id} Error en RSS: {e}")
                add_step(job_id, ProcessingStepName.RSS_FETCH, ProcessingStepStatus.ERROR)
                record_step_metric("RSS Fetch", "FAILED", step_duration_ms, str(e))
                # Abort the pipeline on any error, especially AI provider failures
                raise

            # Step 2: Full Verification
            add_step(job_id, ProcessingStepName.FULL_VERIFICATION, ProcessingStepStatus.RUNNING)
            step_start_ns = time.time_ns()
            try:
                from src.news.entrypoints.cli import main_full_verify

                main_full_verify()
                step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
                add_step(job_id, ProcessingStepName.FULL_VERIFICATION, ProcessingStepStatus.OK)
                record_step_metric("Full Verification", "OK", step_duration_ms)
                logger.info(f"[PIPELINE-JOB] {job_id} Verification completada ({_format_duration(step_duration_ms)})")
            except Exception as e:
                step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
                logger.error(f"[PIPELINE-JOB] {job_id} Error en Verification: {e}")
                add_step(job_id, ProcessingStepName.FULL_VERIFICATION, ProcessingStepStatus.ERROR)
                record_step_metric("Full Verification", "FAILED", step_duration_ms, str(e))
                raise

            # Step 3: Generate Posts
            add_step(job_id, ProcessingStepName.GENERATE_POSTS, ProcessingStepStatus.RUNNING)
            step_start_ns = time.time_ns()
            try:
                from src.news.application.usecases.content import run_content

                run_content(use_gemini=True, mode="news")
                step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
                add_step(job_id, ProcessingStepName.GENERATE_POSTS, ProcessingStepStatus.OK)
                record_step_metric("Generate Posts", "OK", step_duration_ms)
                logger.info(f"[PIPELINE-JOB] {job_id} Posts generados ({_format_duration(step_duration_ms)})")
            except Exception as e:
                step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
                logger.error(f"[PIPELINE-JOB] {job_id} Error en Posts: {e}")
                add_step(job_id, ProcessingStepName.GENERATE_POSTS, ProcessingStepStatus.ERROR)
                record_step_metric("Generate Posts", "FAILED", step_duration_ms, str(e))
                raise

            # Step 4: Generate Articles
            add_step(job_id, ProcessingStepName.GENERATE_ARTICLES, ProcessingStepStatus.RUNNING)
            step_start_ns = time.time_ns()
            try:
                from src.news.application.usecases.article import run as run_article

                run_article(use_gemini=True)
                step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
                add_step(job_id, ProcessingStepName.GENERATE_ARTICLES, ProcessingStepStatus.OK)
                record_step_metric("Generate Articles", "OK", step_duration_ms)
                logger.info(f"[PIPELINE-JOB] {job_id} Artículos generados ({_format_duration(step_duration_ms)})")
            except Exception as e:
                step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
                logger.error(f"[PIPELINE-JOB] {job_id} Error en Articles: {e}")
                add_step(job_id, ProcessingStepName.GENERATE_ARTICLES, ProcessingStepStatus.ERROR)
                record_step_metric("Generate Articles", "FAILED", step_duration_ms, str(e))
                raise

            # Step 5: Fetch Images
            add_step(job_id, ProcessingStepName.FETCH_IMAGES, ProcessingStepStatus.RUNNING)
            step_start_ns = time.time_ns()
            try:
                from src.shared.infrastructure.composition_root import run_image_unsplash, run_image_google

                run_image_unsplash()
                run_image_google()
                step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
                add_step(job_id, ProcessingStepName.FETCH_IMAGES, ProcessingStepStatus.OK)
                record_step_metric("Fetch Images", "OK", step_duration_ms)
                logger.info(f"[PIPELINE-JOB] {job_id} Imágenes descargadas ({_format_duration(step_duration_ms)})")
            except Exception as e:
                step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
                logger.error(f"[PIPELINE-JOB] {job_id} Error en Images: {e}")
                add_step(job_id, ProcessingStepName.FETCH_IMAGES, ProcessingStepStatus.ERROR)
                record_step_metric("Fetch Images", "FAILED", step_duration_ms, str(e))
                raise

            # Step 6: Enrich Images
            add_step(job_id, ProcessingStepName.ENRICH_IMAGES, ProcessingStepStatus.RUNNING)
            step_start_ns = time.time_ns()
            try:
                from src.shared.infrastructure.composition_root import run_image_enricher

                run_image_enricher()
                step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
                add_step(job_id, ProcessingStepName.ENRICH_IMAGES, ProcessingStepStatus.OK)
                record_step_metric("Enrich Images", "OK", step_duration_ms)
                logger.info(f"[PIPELINE-JOB] {job_id} Imágenes enriquecidas ({_format_duration(step_duration_ms)})")
            except Exception as e:
                step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
                logger.error(f"[PIPELINE-JOB] {job_id} Error en Enrichment: {e}")
                add_step(job_id, ProcessingStepName.ENRICH_IMAGES, ProcessingStepStatus.ERROR)
                record_step_metric("Enrich Images", "FAILED", step_duration_ms, str(e))
                raise

            # Step 7: Generate Audio (TTS)
            add_step(job_id, ProcessingStepName.GENERATE_AUDIO, ProcessingStepStatus.RUNNING)
            step_start_ns = time.time_ns()
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
                step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
                add_step(job_id, ProcessingStepName.GENERATE_AUDIO, ProcessingStepStatus.OK)
                record_step_metric("Generate Audio", "OK", step_duration_ms)
            except Exception as e:
                step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
                logger.warning(f"[PIPELINE-JOB] {job_id} Warning en Audio: {e}")
                add_step(job_id, ProcessingStepName.GENERATE_AUDIO, ProcessingStepStatus.SKIPPED)
                record_step_metric("Generate Audio", "SKIPPED", step_duration_ms, str(e))
                raise

            # Step 8: Generate Video
            add_step(job_id, ProcessingStepName.GENERATE_VIDEO, ProcessingStepStatus.RUNNING)
            step_start_ns = time.time_ns()
            try:
                from src.shared.infrastructure.composition_root import create_video_generator
                import os

                db = get_database()
                articles_coll = db["generated_articles"]
                articles = list(articles_coll.find({}))

                video_gen = create_video_generator()
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
                step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
                add_step(job_id, ProcessingStepName.GENERATE_VIDEO, ProcessingStepStatus.OK)
                record_step_metric("Generate Video", "OK", step_duration_ms)
            except Exception as e:
                step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
                logger.warning(f"[PIPELINE-JOB] {job_id} Warning en Video: {e}")
                add_step(job_id, ProcessingStepName.GENERATE_VIDEO, ProcessingStepStatus.SKIPPED)
                record_step_metric("Generate Video", "SKIPPED", step_duration_ms, str(e))
                raise

            # Step 9: WordPress
            add_step(job_id, ProcessingStepName.PUBLISH_WORDPRESS, ProcessingStepStatus.RUNNING)
            step_start_ns = time.time_ns()
            try:
                from src.shared.infrastructure.composition_root import run_wordpress

                run_wordpress()
                step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
                add_step(job_id, ProcessingStepName.PUBLISH_WORDPRESS, ProcessingStepStatus.OK)
                record_step_metric("Publish WordPress", "OK", step_duration_ms)
                logger.info(f"[PIPELINE-JOB] {job_id} WordPress publicado")
            except Exception as e:
                step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
                logger.error(f"[PIPELINE-JOB] {job_id} Error en WordPress: {e}")
                add_step(job_id, ProcessingStepName.PUBLISH_WORDPRESS, ProcessingStepStatus.ERROR)
                record_step_metric("Publish WordPress", "FAILED", step_duration_ms, str(e))
                raise

            # Step 10: Social Networks
            add_step(job_id, ProcessingStepName.PUBLISH_SOCIAL, ProcessingStepStatus.RUNNING)
            step_start_ns = time.time_ns()
            social_ok = 0
            from src.shared.infrastructure.composition_root import (
                run_bluesky, run_facebook, run_mastodon,
            )

            try:
                run_bluesky()
                social_ok += 1
            except Exception as e:
                logger.warning(f"[PIPELINE-JOB] {job_id} Warning en Bluesky: {e}")

            try:
                run_facebook()
                social_ok += 1
            except Exception as e:
                logger.warning(f"[PIPELINE-JOB] {job_id} Warning en Facebook: {e}")

            try:
                run_mastodon()
                social_ok += 1
            except Exception as e:
                logger.warning(f"[PIPELINE-JOB] {job_id} Warning en Mastodon: {e}")

            step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
            add_step(job_id, ProcessingStepName.PUBLISH_SOCIAL, ProcessingStepStatus.OK)
            record_step_metric("Publish Social Networks", "OK", step_duration_ms)
            logger.info(
                f"[PIPELINE-JOB] {job_id} Redes sociales completadas ({social_ok}/3)"
            )

            update_job_status(job_id, JobStatus.COMPLETED, "Pipeline completado exitosamente")
            logger.info(f"[PIPELINE-JOB] {job_id} COMPLETADO")

            # Save metrics to database
            try:
                pipeline_duration_ms = (time.time_ns() - pipeline_start_ns) // 1_000_000
                has_failures = any(
                    step.status == StepStatus.FAILED for step in metrics_steps
                )
                success = not has_failures

                metric = ProcessingMetric(
                    execution_id=job_id,
                    pipeline_type=PipelineType.NEWS,
                    steps=metrics_steps,
                    total_duration_ms=pipeline_duration_ms,
                    success=success,
                    created_at=datetime.now(),
                )

                from src.news.infrastructure.adapters.mongo_metrics_repository import MongoMetricsRepository
                from src.shared.adapters.mongo_db import get_database as get_metrics_db
                metrics_repo = MongoMetricsRepository(get_metrics_db())
                metrics_repo.save(metric)
                logger.info(
                    f"[PIPELINE-JOB] {job_id} Métricas guardadas: "
                    f"{pipeline_duration_ms}ms, {len(metrics_steps)} pasos, success={success}"
                )
            except Exception as e:
                logger.warning(f"[PIPELINE-JOB] {job_id} No se pudieron guardar métricas: {e}")

        except Exception as e:
            logger.error(f"[PIPELINE-JOB] {job_id} Error general: {e}", exc_info=True)
            update_job_status(job_id, JobStatus.FAILED, f"Error: {str(e)}", error=str(e))

            # Save failure metrics
            try:
                pipeline_duration_ms = (time.time_ns() - pipeline_start_ns) // 1_000_000
                metric = ProcessingMetric(
                    execution_id=job_id,
                    pipeline_type=PipelineType.NEWS,
                    steps=metrics_steps,
                    total_duration_ms=pipeline_duration_ms,
                    success=False,
                    created_at=datetime.now(),
                )

                from src.news.infrastructure.adapters.mongo_metrics_repository import MongoMetricsRepository
                from src.shared.adapters.mongo_db import get_database as get_metrics_db
                metrics_repo = MongoMetricsRepository(get_metrics_db())
                metrics_repo.save(metric)
                logger.debug(f"[PIPELINE-JOB] {job_id} Métricas de error guardadas")
            except Exception as metric_err:
                logger.warning(f"[PIPELINE-JOB] {job_id} No se pudieron guardar métricas de error: {metric_err}")

        finally:
            # Cleanup logging handler
            teardown_pipeline_logging(log_handler)

            # Release execution lock
            _execution_lock.release()
            logger.info(f"[PIPELINE-JOB] {job_id} Ejecución completada - Lock liberado")

    # Run in background thread
    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()
    return True
