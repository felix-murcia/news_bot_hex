"""Async pipeline executor with job tracking and metrics collection."""

import threading
import time
from datetime import datetime
from config.logging_config import get_logger
from src.news.domain.entities.pipeline_job import (
    JobStatus,
    ProcessingStepName,
    ProcessingStepStatus,
    PipelineStepResult,
    PipelineResult,
)
from src.news.application.usecases.pipeline_job import (
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


def _execute_step(
    job_id: str,
    step_name: ProcessingStepName,
    step_func,
    metrics_steps: list,
    step_results: list,
) -> tuple[bool, str | None]:
    """
    Execute a single pipeline step.

    Returns:
        tuple: (success, error_message)
    """
    is_critical = step_name.is_critical()
    add_step(job_id, step_name, ProcessingStepStatus.RUNNING)
    step_start_ns = time.time_ns()

    try:
        step_func()
        step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
        add_step(job_id, step_name, ProcessingStepStatus.OK)
        record_step_metric(metrics_steps, step_name.value, "OK", step_duration_ms)
        step_results.append(PipelineStepResult(
            name=step_name,
            status=ProcessingStepStatus.OK,
            critical=is_critical,
        ))
        logger.info(f"[PIPELINE-JOB] {job_id} {step_name.value} completado ({_format_duration(step_duration_ms)})")
        return True, None
    except Exception as e:
        step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
        error_msg = str(e)
        logger.error(f"[PIPELINE-JOB] {job_id} Error en {step_name.value}: {e}")
        add_step(job_id, step_name, ProcessingStepStatus.ERROR)
        record_step_metric(metrics_steps, step_name.value, "FAILED", step_duration_ms, error_msg)
        step_results.append(PipelineStepResult(
            name=step_name,
            status=ProcessingStepStatus.ERROR,
            error=error_msg,
            critical=is_critical,
        ))
        return False, error_msg


def record_step_metric(metrics_steps: list, step_name: str, status: str, duration_ms: int, error: str = None):
    """Record a step metric."""
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


def execute_pipeline_async(
    job_id: str,
    generated_articles_repo,
    metrics_repo,
) -> bool:
    """
    Execute pipeline in background thread with job tracking and metrics collection.

    Enrichment steps (images, audio, video) don't abort on failure - they mark PARTIAL.
    Critical steps (RSS, verification, posts, articles, WordPress, social) abort on failure.

    Args:
        job_id: Unique job identifier
        generated_articles_repo: Repository for generated articles (injected)
        metrics_repo: Repository for metrics (injected)

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
        log_handler = None
        try:
            # Setup logging handler to capture real-time feedback for UI
            log_handler = setup_pipeline_logging(job_id)
        except Exception as e:
            logger.error(f"[PIPELINE-JOB] {job_id} Error setup logging: {e}", exc_info=True)
            update_job_status(job_id, JobStatus.FAILED, f"Error en logging: {str(e)}", error=str(e))
            _execution_lock.release()
            return

        # Initialize metrics collection
        metrics_steps = []
        step_results = []
        pipeline_start_ns = time.time_ns()

        try:
            update_job_status(job_id, JobStatus.RUNNING, "Pipeline iniciado")
            logger.info(f"[PIPELINE-JOB] {job_id} iniciado")

            # Step 1: Fetch RSS (CRITICAL)
            success, error = _execute_step(
                job_id,
                ProcessingStepName.RSS_FETCH,
                lambda: __import__('src.news.entrypoints.cli', fromlist=['main_rss']).main_rss(),
                metrics_steps,
                step_results,
            )
            if not success:
                raise RuntimeError(f"Fallo crítico en RSS: {error}")

            # Step 2: Full Verification (CRITICAL)
            success, error = _execute_step(
                job_id,
                ProcessingStepName.FULL_VERIFICATION,
                lambda: __import__('src.news.entrypoints.cli', fromlist=['main_full_verify']).main_full_verify(),
                metrics_steps,
                step_results,
            )
            if not success:
                raise RuntimeError(f"Fallo crítico en Verification: {error}")

            # Step 3: Generate Posts (CRITICAL)
            success, error = _execute_step(
                job_id,
                ProcessingStepName.GENERATE_POSTS,
                lambda: __import__('src.news.application.usecases.content', fromlist=['run_content']).run_content(use_gemini=True, mode="news"),
                metrics_steps,
                step_results,
            )
            if not success:
                raise RuntimeError(f"Fallo crítico en Posts: {error}")

            # Step 4: Generate Articles (CRITICAL)
            success, error = _execute_step(
                job_id,
                ProcessingStepName.GENERATE_ARTICLES,
                lambda: __import__('src.news.application.usecases.article', fromlist=['run']).run(use_gemini=True),
                metrics_steps,
                step_results,
            )
            if not success:
                raise RuntimeError(f"Fallo crítico en Articles: {error}")

            # Step 5: Fetch Images (ENRICHMENT)
            success, error = _execute_step(
                job_id,
                ProcessingStepName.FETCH_IMAGES,
                lambda: (
                    __import__('src.shared.infrastructure.composition_root', fromlist=['run_image_unsplash']).run_image_unsplash(),
                    __import__('src.shared.infrastructure.composition_root', fromlist=['run_image_google']).run_image_google(),
                ),
                metrics_steps,
                step_results,
            )
            # Continue on failure (enrichment)

            # Step 6: Enrich Images (ENRICHMENT)
            success, error = _execute_step(
                job_id,
                ProcessingStepName.ENRICH_IMAGES,
                lambda: __import__('src.shared.infrastructure.composition_root', fromlist=['run_image_enricher']).run_image_enricher(),
                metrics_steps,
                step_results,
            )
            # Continue on failure (enrichment)

            # Step 7: Generate Audio (ENRICHMENT)
            def _run_audio():
                from src.shared.application.usecases.tts_from_article import run_tts_from_articles

                articles = generated_articles_repo.load_all()

                if articles:
                    updated = run_tts_from_articles(articles)
                    for article in updated:
                        if article.get("tts_audio_path"):
                            article_id = article.get("_id")
                            if article_id:
                                generated_articles_repo.update_tts_audio_path(str(article_id), article["tts_audio_path"])
                    logger.info(f"[PIPELINE-JOB] {job_id} Audio generado")

            success, error = _execute_step(
                job_id,
                ProcessingStepName.GENERATE_AUDIO,
                _run_audio,
                metrics_steps,
                step_results,
            )
            # Continue on failure (enrichment)

            # Step 8: Generate Video (ENRICHMENT)
            def _run_video():
                from src.shared.infrastructure.composition_root import create_video_generator
                import os

                articles = generated_articles_repo.load_all()

                video_gen = create_video_generator()
                if video_gen.is_available():
                    for article in articles:
                        audio_path = article.get("tts_audio_path")
                        if audio_path and os.path.exists(audio_path):
                            video_path = video_gen.create_video_from_audio(
                                audio_path=audio_path,
                                image=article.get("image_url"),
                            )
                            if video_path:
                                article_id = article.get("_id")
                                if article_id:
                                    generated_articles_repo.update_generated_video_path(str(article_id), video_path)
                    logger.info(f"[PIPELINE-JOB] {job_id} Videos generados")

            success, error = _execute_step(
                job_id,
                ProcessingStepName.GENERATE_VIDEO,
                _run_video,
                metrics_steps,
                step_results,
            )
            # Continue on failure (enrichment)

            # Step 9: WordPress (CRITICAL)
            success, error = _execute_step(
                job_id,
                ProcessingStepName.PUBLISH_WORDPRESS,
                lambda: __import__('src.shared.infrastructure.composition_root', fromlist=['run_wordpress']).run_wordpress(),
                metrics_steps,
                step_results,
            )
            if not success:
                raise RuntimeError(f"Fallo crítico en WordPress: {error}")

            # Step 10: Social Networks (CRITICAL)
            def _run_social():
                from src.shared.infrastructure.composition_root import run_bluesky, run_facebook, run_mastodon
                social_ok = 0

                run_bluesky()
                social_ok += 1

                run_facebook()
                social_ok += 1

                run_mastodon()
                social_ok += 1

                logger.info(f"[PIPELINE-JOB] {job_id} Redes sociales completadas ({social_ok}/3)")

            success, error = _execute_step(
                job_id,
                ProcessingStepName.PUBLISH_SOCIAL,
                _run_social,
                metrics_steps,
                step_results,
            )
            if not success:
                raise RuntimeError(f"Fallo crítico en Social: {error}")

            # All steps completed - determine final status
            failed_critical = [s for s in step_results if s.status == ProcessingStepStatus.ERROR and s.critical]
            failed_enrichment = [s for s in step_results if s.status == ProcessingStepStatus.ERROR and not s.critical]

            if failed_critical:
                final_status = JobStatus.FAILED
                error_msg = f"Fallo crítico: {', '.join(s.name.value for s in failed_critical)}"
                failed_steps = [s.name.value for s in failed_critical] + [s.name.value for s in failed_enrichment]
            elif failed_enrichment:
                final_status = JobStatus.PARTIAL
                error_msg = f"Fallo en enriquecimiento: {', '.join(s.name.value for s in failed_enrichment)}"
                failed_steps = [s.name.value for s in failed_enrichment]
            else:
                final_status = JobStatus.COMPLETED
                error_msg = None
                failed_steps = []

            update_job_status(job_id, final_status, error_msg or "Pipeline completado", error=error_msg)
            logger.info(f"[PIPELINE-JOB] {job_id} {final_status.value.upper()}")

            # Save metrics to database
            try:
                pipeline_duration_ms = (time.time_ns() - pipeline_start_ns) // 1_000_000
                has_failures = any(step.status == StepStatus.FAILED for step in metrics_steps)
                success = not has_failures

                metric = ProcessingMetric(
                    execution_id=job_id,
                    pipeline_type=PipelineType.NEWS,
                    steps=metrics_steps,
                    total_duration_ms=pipeline_duration_ms,
                    success=success,
                    created_at=datetime.now(),
                )

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

                metrics_repo.save(metric)
                logger.debug(f"[PIPELINE-JOB] {job_id} Métricas de error guardadas")
            except Exception as metric_err:
                logger.warning(f"[PIPELINE-JOB] {job_id} No se pudieron guardar métricas de error: {metric_err}")

        finally:
            # Cleanup logging handler
            if log_handler:
                teardown_pipeline_logging(log_handler)

            # Release execution lock
            _execution_lock.release()
            logger.info(f"[PIPELINE-JOB] {job_id} Ejecución completada - Lock liberado")

    # Run in background thread
    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()
    return True
