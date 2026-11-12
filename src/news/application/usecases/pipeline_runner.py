"""PipelineRunner: ejecuta el pipeline completo (10 pasos) con estado, logging y métricas.

Extraído de execute_pipeline_async (B2). Mantiene toda la lógica original sin cambios.
"""

import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from src.shared.domain.ports.video_generator_port import VideoGeneratorPort

import logging
from src.news.application.usecases.pipeline_log_handler import (
    setup_pipeline_logging,
    teardown_pipeline_logging,
)
from src.news.application.usecases.content import run_content
from src.news.application.usecases.article import run as run_articles
from src.news.domain.entities.pipeline_job import (
    JobStatus,
    PipelineStepResult,
    ProcessingStepName,
    ProcessingStepStatus,
)
from src.news.domain.entities.processing_metric import (
    PipelineType,
    ProcessingMetric,
    StepMetric,
    StepStatus,
)

logger = logging.getLogger(__name__)
@dataclass
class PipelineContext:
    """Contexto compartido entre los pasos del pipeline. Se pasa por parámetro, no se guarda en self."""

    job_id: str
    provider: Optional[str] = None
    article: Optional[dict] = None
    post: Optional[dict] = None
    images: Optional[list] = None
    audio_path: Optional[str] = None
    video_path: Optional[str] = None


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
    """Execute a single pipeline step. Returns (success, error_message)."""
    from src.news.application.usecases.pipeline_executor import add_step

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


class PipelineRunner:
    def __init__(
        self,
        generated_articles_repo,
        generated_posts_repo,
        verified_news_repo,
        rss_fetch_runner: Callable[[], dict],
        full_verify_runner: Callable[[], dict],
        metrics_repo,
        social_publisher,
        tts_usecase,
        image_unsplash_runner: Callable[[], None],
        image_google_runner: Callable[[], None],
        image_enricher_runner: Callable[[], None],
        wordpress_runner: Callable[[], None],
        video_generator_factory: Callable[[], VideoGeneratorPort],
        *,
        social_truncator: Callable[..., str],
        post_editor: Callable[..., str],
    ):
        self._generated_articles_repo = generated_articles_repo
        self._generated_posts_repo = generated_posts_repo
        self._verified_news_repo = verified_news_repo
        self._rss_fetch_runner = rss_fetch_runner
        self._full_verify_runner = full_verify_runner
        self._metrics_repo = metrics_repo
        self._social_publisher = social_publisher
        self._tts_usecase = tts_usecase
        self._image_unsplash_runner = image_unsplash_runner
        self._image_google_runner = image_google_runner
        self._image_enricher_runner = image_enricher_runner
        self._wordpress_runner = wordpress_runner
        self._video_generator_factory = video_generator_factory
        self._social_truncator = social_truncator
        self._post_editor = post_editor

    def run(self, ctx: PipelineContext) -> None:
        from src.news.application.usecases.pipeline_executor import update_job_status

        log_handler = None
        try:
            try:
                log_handler = setup_pipeline_logging(ctx.job_id)
            except Exception as e:
                logger.error(f"[PIPELINE-JOB] {ctx.job_id} Error setup logging: {e}", exc_info=True)
                update_job_status(ctx.job_id, JobStatus.FAILED, f"Error en logging: {str(e)}", error=str(e))
                return

            metrics_steps = []
            step_results = []
            pipeline_start_ns = time.time_ns()

            try:
                update_job_status(ctx.job_id, JobStatus.RUNNING, "Pipeline iniciado")
                logger.info(f"[PIPELINE-JOB] {ctx.job_id} iniciado")

                # Step 1: Fetch RSS (CRITICAL)
                success, error = _execute_step(
                    ctx.job_id,
                    ProcessingStepName.RSS_FETCH,
                    self._rss_fetch_runner,
                    metrics_steps,
                    step_results,
                )
                if not success:
                    raise RuntimeError(f"Fallo crítico en RSS: {error}")

                # Step 2: Full Verification (CRITICAL)
                success, error = _execute_step(
                    ctx.job_id,
                    ProcessingStepName.FULL_VERIFICATION,
                    self._full_verify_runner,
                    metrics_steps,
                    step_results,
                )
                if not success:
                    raise RuntimeError(f"Fallo crítico en Verification: {error}")

                # Step 3: Generate Posts (CRITICAL)
                success, error = _execute_step(
                    ctx.job_id,
                    ProcessingStepName.GENERATE_POSTS,
                    lambda: run_content(
                        use_gemini=True,
                        mode="news",
                        generated_posts_repo=self._generated_posts_repo,
                        verified_news_repo=self._verified_news_repo,
                        social_truncator=self._social_truncator,
                        post_editor=self._post_editor,
                    ),
                    metrics_steps,
                    step_results,
                )
                if not success:
                    raise RuntimeError(f"Fallo crítico en Posts: {error}")

                # Step 4: Generate Articles (CRITICAL)
                success, error = _execute_step(
                    ctx.job_id,
                    ProcessingStepName.GENERATE_ARTICLES,
                    lambda: run_articles(
                        use_gemini=True,
                        generated_articles_repo=self._generated_articles_repo,
                        generated_posts_repo=self._generated_posts_repo,
                        verified_news_repo=self._verified_news_repo,
                    ),
                    metrics_steps,
                    step_results,
                )
                if not success:
                    raise RuntimeError(f"Fallo crítico en Articles: {error}")

                # Step 5: Fetch Images (ENRICHMENT)
                success, error = _execute_step(
                    ctx.job_id,
                    ProcessingStepName.FETCH_IMAGES,
                    lambda: (
                        self._image_unsplash_runner(),
                        self._image_google_runner(),
                    ),
                    metrics_steps,
                    step_results,
                )

                # Step 6: Enrich Images (ENRICHMENT)
                success, error = _execute_step(
                    ctx.job_id,
                    ProcessingStepName.ENRICH_IMAGES,
                    lambda: self._image_enricher_runner(),
                    metrics_steps,
                    step_results,
                )

                # Step 7: Generate Audio (ENRICHMENT)
                def _run_audio():
                    articles = self._generated_articles_repo.load_all()

                    if articles:
                        updated = self._tts_usecase.execute_batch(articles)
                        for article in updated:
                            if article.get("tts_audio_path"):
                                article_id = article.get("_id")
                                if article_id:
                                    self._generated_articles_repo.update_tts_audio_path(str(article_id), article["tts_audio_path"])
                        logger.info(f"[PIPELINE-JOB] {ctx.job_id} Audio generado")

                success, error = _execute_step(
                    ctx.job_id,
                    ProcessingStepName.GENERATE_AUDIO,
                    _run_audio,
                    metrics_steps,
                    step_results,
                )

                # Step 8: Generate Video (ENRICHMENT)
                def _run_video():
                    articles = self._generated_articles_repo.load_all()

                    video_gen = self._video_generator_factory()
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
                                        self._generated_articles_repo.update_generated_video_path(str(article_id), video_path)
                        logger.info(f"[PIPELINE-JOB] {ctx.job_id} Videos generados")

                success, error = _execute_step(
                    ctx.job_id,
                    ProcessingStepName.GENERATE_VIDEO,
                    _run_video,
                    metrics_steps,
                    step_results,
                )

                # Step 9: WordPress (CRITICAL)
                success, error = _execute_step(
                    ctx.job_id,
                    ProcessingStepName.PUBLISH_WORDPRESS,
                    lambda: self._wordpress_runner(),
                    metrics_steps,
                    step_results,
                )
                if not success:
                    raise RuntimeError(f"Fallo crítico en WordPress: {error}")

                # Step 10: Social Networks (CRITICAL)
                def _run_social():
                    self._social_publisher.publish_all()
                    logger.info(f"[PIPELINE-JOB] {ctx.job_id} Redes sociales completadas (facade)")

                success, error = _execute_step(
                    ctx.job_id,
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

                update_job_status(ctx.job_id, final_status, error_msg or "Pipeline completado", error=error_msg)
                logger.info(f"[PIPELINE-JOB] {ctx.job_id} {final_status.value.upper()}")

                # Save metrics to database
                try:
                    pipeline_duration_ms = (time.time_ns() - pipeline_start_ns) // 1_000_000
                    has_failures = any(step.status == StepStatus.FAILED for step in metrics_steps)
                    success = not has_failures

                    metric = ProcessingMetric(
                        execution_id=ctx.job_id,
                        pipeline_type=PipelineType.NEWS,
                        steps=metrics_steps,
                        total_duration_ms=pipeline_duration_ms,
                        success=success,
                        created_at=datetime.now(),
                    )

                    self._metrics_repo.save(metric)
                    logger.info(
                        f"[PIPELINE-JOB] {ctx.job_id} Métricas guardadas: "
                        f"{pipeline_duration_ms}ms, {len(metrics_steps)} pasos, success={success}"
                    )
                except Exception as e:
                    logger.warning(f"[PIPELINE-JOB] {ctx.job_id} No se pudieron guardar métricas: {e}")

            except Exception as e:
                logger.error(f"[PIPELINE-JOB] {ctx.job_id} Error general: {e}", exc_info=True)
                update_job_status(ctx.job_id, JobStatus.FAILED, f"Error: {str(e)}", error=str(e))

                try:
                    pipeline_duration_ms = (time.time_ns() - pipeline_start_ns) // 1_000_000
                    metric = ProcessingMetric(
                        execution_id=ctx.job_id,
                        pipeline_type=PipelineType.NEWS,
                        steps=metrics_steps,
                        total_duration_ms=pipeline_duration_ms,
                        success=False,
                        created_at=datetime.now(),
                    )

                    self._metrics_repo.save(metric)
                    logger.debug(f"[PIPELINE-JOB] {ctx.job_id} Métricas de error guardadas")
                except Exception as metric_err:
                    logger.warning(f"[PIPELINE-JOB] {ctx.job_id} No se pudieron guardar métricas de error: {metric_err}")

        finally:
            # Cleanup logging handler
            if log_handler:
                teardown_pipeline_logging(log_handler)
