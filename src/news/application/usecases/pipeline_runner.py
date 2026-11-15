"""PipelineRunner: ejecuta el pipeline completo (10 pasos) con estado, logging y métricas.

Extraído de execute_pipeline_async (B2). Mantiene toda la lógica original sin cambios.
"""

import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional

from src.news.domain.ports import ContentExtractor
from src.shared.domain.ports.video_generator_port import VideoGeneratorPort
from src.shared.domain.services.ai_providers import AiProviders

import logging
from src.news.application.usecases.pipeline_log_handler import (
    setup_pipeline_logging,
    teardown_pipeline_logging,
)
from src.news.application.usecases.pipeline_job import add_step, update_job_status
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
    wp_url: Optional[str] = None


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
    """Execute a single pipeline step. Returns (success, error_message).

    Detects both exceptions and error dict returns (e.g., {"status": "error", ...}).
    """
    is_critical = step_name.is_critical()
    add_step(job_id, step_name, ProcessingStepStatus.RUNNING)
    step_start_ns = time.time_ns()

    try:
        logger.info(f"[PIPELINE-JOB] {job_id} Ejecutando paso {step_name.value}...")
        result = step_func()
        step_duration_ms = (time.time_ns() - step_start_ns) // 1_000_000
        logger.info(f"[PIPELINE-JOB] {job_id} Paso {step_name.value} retornó en {step_duration_ms}ms")

        # Check if result is an error dict (e.g., {"status": "error", ...})
        if isinstance(result, dict) and result.get("status") == "error":
            error_msg = result.get("message", "Unknown error")
            logger.error(f"[PIPELINE-JOB] {job_id} {step_name.value} falló: {error_msg}")
            add_step(job_id, step_name, ProcessingStepStatus.ERROR)
            record_step_metric(metrics_steps, step_name.value, "FAILED", step_duration_ms, error_msg)
            step_results.append(PipelineStepResult(
                name=step_name,
                status=ProcessingStepStatus.ERROR,
                error=error_msg,
                critical=is_critical,
            ))
            return False, error_msg

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
        prepare_articles_runner: Callable[[], dict],
        full_verify_runner: Callable[[], dict],
        metrics_repo,
        social_publisher,
        tts_usecase,
        image_unsplash_runner: Callable[[], None],
        image_google_runner: Callable[[], None],
        image_enricher_runner: Callable[[], None],
        wordpress_runner: Callable[[dict, dict], Optional[dict]],
        video_generator_factory: Callable[[], VideoGeneratorPort],
        *,
        social_truncator: Callable[..., str],
        post_editor: Callable[..., str],
        cache_loader: Callable[..., tuple[Optional[str], str]],
        seo_helpers,
        ai_providers: AiProviders,
        content_extractor: Optional[ContentExtractor] = None,
    ):
        self._generated_articles_repo = generated_articles_repo
        self._generated_posts_repo = generated_posts_repo
        self._verified_news_repo = verified_news_repo
        self._rss_fetch_runner = rss_fetch_runner
        self._prepare_articles_runner = prepare_articles_runner
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
        self._cache_loader = cache_loader
        self._seo_helpers = seo_helpers
        self._ai_providers = ai_providers
        self._content_extractor = content_extractor

    def run(self, ctx: PipelineContext) -> None:
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

                # Step 2: Prepare Articles (CRITICAL) - transform raw_news -> generated_articles
                success, error = _execute_step(
                    ctx.job_id,
                    ProcessingStepName.PREPARE_ARTICLES,
                    self._prepare_articles_runner,
                    metrics_steps,
                    step_results,
                )
                if not success:
                    raise RuntimeError(f"Fallo crítico en Prepare Articles: {error}")

                # Step 3: Full Verification (CRITICAL)
                logger.info(f"[PIPELINE-JOB] {ctx.job_id} Iniciando FULL_VERIFICATION...")
                success, error = _execute_step(
                    ctx.job_id,
                    ProcessingStepName.FULL_VERIFICATION,
                    self._full_verify_runner,
                    metrics_steps,
                    step_results,
                )
                logger.info(f"[PIPELINE-JOB] {ctx.job_id} FULL_VERIFICATION terminó (success={success}, error={error})")
                if not success:
                    raise RuntimeError(f"Fallo crítico en Verification: {error}")

                # Step 4: Generate Posts (ENRICHMENT) - calls LLM, may take 30-60s
                logger.info(f"[PIPELINE-JOB] {ctx.job_id} Iniciando GENERATE_POSTS (llamadas a LLM)...")
                posts_result: List[Dict] = []

                def _run_posts():
                    posts = run_content(
                        use_gemini=True,
                        mode="news",
                        ai_providers=self._ai_providers,
                        generated_posts_repo=self._generated_posts_repo,
                        verified_news_repo=self._verified_news_repo,
                        social_truncator=self._social_truncator,
                        post_editor=self._post_editor,
                        cache_loader=self._cache_loader,
                    )
                    if isinstance(posts, list):
                        posts_result.extend(posts)
                    elif posts:
                        posts_result.append(posts)
                    return None

                success, error = _execute_step(
                    ctx.job_id,
                    ProcessingStepName.GENERATE_POSTS,
                    _run_posts,
                    metrics_steps,
                    step_results,
                )
                logger.info(f"[PIPELINE-JOB] {ctx.job_id} GENERATE_POSTS terminó (success={success}, error={error})")
                ctx.post = posts_result[0] if posts_result else None
                if ctx.post:
                    logger.info(
                        f"[PIPELINE-JOB] {ctx.job_id} Post ganador capturado: url={ctx.post.get('url')}"
                    )
                if not success:
                    raise RuntimeError(f"Fallo en Posts: {error}")

                # Step 5: Generate Articles (CRITICAL) - calls LLM, may take 60-120s
                logger.info(f"[PIPELINE-JOB] {ctx.job_id} Iniciando GENERATE_ARTICLES (llamadas a LLM)...")
                articles_result: List[Dict] = []

                def _run_articles():
                    articles = run_articles(
                        use_gemini=True,
                        ai_providers=self._ai_providers,
                        generated_articles_repo=self._generated_articles_repo,
                        generated_posts_repo=self._generated_posts_repo,
                        verified_news_repo=self._verified_news_repo,
                        seo_helpers=self._seo_helpers,
                        content_extractor=self._content_extractor,
                    )
                    if isinstance(articles, list):
                        articles_result.extend(articles)
                    elif articles:
                        articles_result.append(articles)
                    return None

                success, error = _execute_step(
                    ctx.job_id,
                    ProcessingStepName.GENERATE_ARTICLES,
                    _run_articles,
                    metrics_steps,
                    step_results,
                )
                logger.info(f"[PIPELINE-JOB] {ctx.job_id} GENERATE_ARTICLES terminó (success={success}, error={error})")
                ctx.article = articles_result[0] if articles_result else None
                if ctx.article:
                    logger.info(
                        f"[PIPELINE-JOB] {ctx.job_id} Artículo ganador capturado: original_url={ctx.article.get('original_url')}"
                    )
                if not success:
                    raise RuntimeError(f"Fallo crítico en Articles: {error}")

                # Determinar la noticia ganadora: las imágenes solo se buscan/enriquecen para ella.
                winning_url = ""
                try:
                    verified_news = self._verified_news_repo.get_all_news()
                    if verified_news and isinstance(verified_news, list) and verified_news:
                        first = verified_news[0]
                        winning_url = getattr(first, "url", "") or ""
                        logger.info(
                            f"[PIPELINE-JOB] {ctx.job_id} Noticia ganadora para imágenes: {winning_url}"
                        )
                    else:
                        logger.warning(
                            f"[PIPELINE-JOB] {ctx.job_id} No hay noticia ganadora; pasos de imagen se omiten"
                        )
                except Exception as e:
                    logger.warning(
                        f"[PIPELINE-JOB] {ctx.job_id} No se pudo obtener la noticia ganadora: {e}"
                    )

                # Step 6: Fetch Images (ENRICHMENT) - solo noticia ganadora
                def _run_fetch_images():
                    if not winning_url:
                        logger.warning(
                            f"[PIPELINE-JOB] {ctx.job_id} FETCH_IMAGES omitido: no hay noticia ganadora"
                        )
                        return None
                    return (
                        self._image_unsplash_runner(url=winning_url),
                        self._image_google_runner(url=winning_url),
                    )

                success, error = _execute_step(
                    ctx.job_id,
                    ProcessingStepName.FETCH_IMAGES,
                    _run_fetch_images,
                    metrics_steps,
                    step_results,
                )

                # Step 7: Enrich Images (ENRICHMENT) - solo noticia ganadora
                def _run_enrich_images():
                    if not winning_url:
                        logger.warning(
                            f"[PIPELINE-JOB] {ctx.job_id} ENRICH_IMAGES omitido: no hay noticia ganadora"
                        )
                        return None
                    return self._image_enricher_runner(url=winning_url)

                success, error = _execute_step(
                    ctx.job_id,
                    ProcessingStepName.ENRICH_IMAGES,
                    _run_enrich_images,
                    metrics_steps,
                    step_results,
                )

                # Step 8: Generate Audio (ENRICHMENT) - single-item para la noticia ganadora
                def _run_audio():
                    if not ctx.article:
                        logger.warning(
                            f"[PIPELINE-JOB] {ctx.job_id} AUDIO omitido: no hay artículo ganador"
                        )
                        return None
                    # Obtener el artículo desde Mongo (tiene _id) usando la URL original del ganador
                    article = self._generated_articles_repo.get_by_original_url(
                        ctx.article.get("original_url", "")
                    )
                    if not article:
                        logger.warning(
                            f"[PIPELINE-JOB] {ctx.job_id} AUDIO omitido: artículo no encontrado en Mongo "
                            f"(original_url={ctx.article.get('original_url')})"
                        )
                        return None
                    updated = self._tts_usecase.execute(article)
                    audio_path = updated.get("tts_audio_path")
                    if audio_path:
                        article_id = article.get("_id")
                        if article_id:
                            self._generated_articles_repo.update_tts_audio_path(str(article_id), audio_path)
                            logger.info(
                                f"[PIPELINE-JOB] {ctx.job_id} Audio generado para artículo ganador: {audio_path}"
                            )
                    else:
                        logger.warning(
                            f"[PIPELINE-JOB] {ctx.job_id} No se generó audio para el artículo ganador"
                        )
                    return None

                success, error = _execute_step(
                    ctx.job_id,
                    ProcessingStepName.GENERATE_AUDIO,
                    _run_audio,
                    metrics_steps,
                    step_results,
                )

                # Step 9: Generate Video (ENRICHMENT) - single-item para la noticia ganadora
                def _run_video():
                    if not ctx.article:
                        logger.warning(
                            f"[PIPELINE-JOB] {ctx.job_id} VIDEO omitido: no hay artículo ganador"
                        )
                        return None
                    article = self._generated_articles_repo.get_by_original_url(
                        ctx.article.get("original_url", "")
                    )
                    if not article:
                        logger.warning(
                            f"[PIPELINE-JOB] {ctx.job_id} VIDEO omitido: artículo no encontrado en Mongo "
                            f"(original_url={ctx.article.get('original_url')})"
                        )
                        return None
                    audio_path = article.get("tts_audio_path")
                    if not audio_path or not os.path.exists(audio_path):
                        logger.warning(
                            f"[PIPELINE-JOB] {ctx.job_id} VIDEO omitido: no hay audio para el artículo ganador"
                        )
                        return None
                    video_gen = self._video_generator_factory()
                    if video_gen.is_available():
                        video_path = video_gen.create_video_from_audio(
                            audio_path=audio_path,
                            image=article.get("image_url"),
                        )
                        if video_path:
                            article_id = article.get("_id")
                            if article_id:
                                self._generated_articles_repo.update_generated_video_path(str(article_id), video_path)
                                logger.info(
                                    f"[PIPELINE-JOB] {ctx.job_id} Video generado para artículo ganador: {video_path}"
                                )
                    return None

                success, error = _execute_step(
                    ctx.job_id,
                    ProcessingStepName.GENERATE_VIDEO,
                    _run_video,
                    metrics_steps,
                    step_results,
                )

                # Step 10: WordPress (CRITICAL) - single-item para la noticia ganadora
                def _run_wordpress():
                    if not ctx.article or not ctx.post:
                        logger.warning(
                            f"[PIPELINE-JOB] {ctx.job_id} WORDPRESS omitido: no hay artículo/post ganador"
                        )
                        return None
                    result = self._wordpress_runner(ctx.article, ctx.post)
                    # Capturar la URL de WordPress devuelta por publish_article()
                    if isinstance(result, dict):
                        wp_url = result.get("url") or ""
                        if wp_url:
                            ctx.wp_url = wp_url
                            logger.info(
                                f"[PIPELINE-JOB] {ctx.job_id} URL WordPress capturada (paso 10): {wp_url}"
                            )
                    return result

                success, error = _execute_step(
                    ctx.job_id,
                    ProcessingStepName.PUBLISH_WORDPRESS,
                    _run_wordpress,
                    metrics_steps,
                    step_results,
                )
                if not success:
                    raise RuntimeError(f"Fallo crítico en WordPress: {error}")

                # Step 11: Social Networks (CRITICAL) - single-item para la noticia ganadora
                def _run_social():
                    if not ctx.post:
                        logger.warning(
                            f"[PIPELINE-JOB] {ctx.job_id} SOCIAL omitido: no hay post ganador"
                        )
                        return None
                    # Reemplazar la URL original por la de WordPress en el texto del post
                    # antes de publicar en redes sociales (paso 11).
                    tweet = ctx.post.get("tweet", "")
                    wp_url = ctx.wp_url or ""
                    original_url = (
                        ctx.post.get("url")
                        or ctx.post.get("original_url")
                        or ""
                    )
                    if wp_url and original_url and original_url in tweet:
                        ctx.post["tweet"] = tweet.replace(original_url, wp_url)
                        logger.info(
                            f"[PIPELINE-JOB] {ctx.job_id} URL original reemplazada por WP en tweet"
                        )
                    elif wp_url and "http" not in tweet:
                        # Añadir "Más info: <url_wordpress>" respetando el límite de 280 caracteres
                        suffix = f" Más info: {wp_url}"
                        if len(tweet) + len(suffix) <= 280:
                            ctx.post["tweet"] = tweet + suffix
                            logger.info(
                                f"[PIPELINE-JOB] {ctx.job_id} URL de WordPress añadida al tweet"
                            )
                    # Exponer wp_url también como metadata del post (social.py la usa)
                    if wp_url:
                        ctx.post["wp_url"] = wp_url
                    self._social_publisher.publish(ctx.post)
                    logger.info(f"[PIPELINE-JOB] {ctx.job_id} Redes sociales completadas (single post)")

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
