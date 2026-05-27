"""Async executor for process_url with job tracking."""

import threading
from config.logging_config import get_logger
from src.news.domain.ports import ContentExtractor
from src.news.application.usecases.pipeline_job import (
    JobStatus,
    update_job_status,
    add_step,
    update_job_log,
)
from src.news.application.usecases.pipeline_log_handler import (
    setup_pipeline_logging,
    teardown_pipeline_logging,
)

logger = get_logger("news_bot.process_url.executor")


def execute_process_url_async(
    job_id: str,
    url: str,
    model_provider: str,
    use_ai: bool,
) -> None:
    """Execute process_url in background thread with job tracking."""

    def run_process():
        # Setup logging handler to capture real-time feedback for UI
        log_handler = setup_pipeline_logging(job_id)

        try:
            update_job_status(job_id, JobStatus.RUNNING, "Procesando URL...")
            logger.info(f"[PROCESS_URL_JOB] {job_id} iniciado: {url}")

            # Step 1: Get content extractor
            add_step(job_id, "Inicializando", "running")
            try:
                from src.news.entrypoints.api.dependencies import get_content_extractor
                extractor = get_content_extractor()
                add_step(job_id, "Inicializando", "ok")
            except Exception as e:
                logger.error(f"[PROCESS_URL_JOB] {job_id} Error inicializando: {e}")
                add_step(job_id, "Inicializando", "error")
                raise

            # Step 2: Extract content
            add_step(job_id, "Extrayendo contenido", "running")
            try:
                from src.news.application.usecases.news_to_news import process_news_url

                logger.info(f"[PROCESS_URL_JOB] {job_id} Extrayendo contenido de {url}")
                update_job_log(job_id, f"Extrayendo contenido de {url}")

                result = process_news_url(
                    url=url,
                    content_extractor=extractor,
                    model_provider=model_provider,
                    use_ai=use_ai,
                    force_extract=True,
                )

                add_step(job_id, "Extrayendo contenido", "ok")
                logger.info(f"[PROCESS_URL_JOB] {job_id} Procesamiento completado")

                # Store result in job
                title = result.get("article_data", {}).get("article", {}).get("title", "")
                post = result.get("post", "")[:200] if result.get("post") else ""
                mode = result.get("mode", "")

                # Add final step
                add_step(job_id, "Procesamiento completado", "ok")

                # Step 3: Publish to social media
                add_step(job_id, "Publicando en redes sociales", "running")
                try:
                    from src.shared.adapters.publishers.social import SocialMediaPublisher

                    publisher = SocialMediaPublisher(enable_bluesky=True, enable_mastodon=True)
                    post_data = {
                        "tweet": post,
                        "url": url,
                        "wp_url": "",
                        "image_url": "",
                    }

                    publish_results = publisher.publish(post_data)
                    logger.info(f"[PROCESS_URL_JOB] {job_id} Publicación completada: {len(publish_results)} plataformas")

                    add_step(job_id, "Publicando en redes sociales", "ok")

                    # Update job with result
                    from src.news.application.usecases.pipeline_job import _jobs_store
                    _jobs_store[job_id]["result"] = {
                        "title": title,
                        "post": post,
                        "mode": mode,
                        "full_result": result,
                        "publish_results": publish_results,
                    }

                    update_job_status(
                        job_id,
                        JobStatus.COMPLETED,
                        f"✅ Procesado y publicado: {title[:50]}...",
                    )

                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"[PROCESS_URL_JOB] {job_id} Error publicando: {error_msg}")
                    add_step(job_id, "Publicando en redes sociales", "error")

                    # Still mark as completed but note the publication error
                    from src.news.application.usecases.pipeline_job import _jobs_store
                    _jobs_store[job_id]["result"] = {
                        "title": title,
                        "post": post,
                        "mode": mode,
                        "full_result": result,
                        "publish_error": error_msg,
                    }

                    update_job_status(
                        job_id,
                        JobStatus.COMPLETED,
                        f"✅ Procesado pero error en publicación: {error_msg[:50]}...",
                    )

            except ValueError as e:
                error_msg = str(e)
                logger.error(f"[PROCESS_URL_JOB] {job_id} ValueError: {error_msg}")
                add_step(job_id, "Procesamiento", "error")
                update_job_status(job_id, JobStatus.FAILED, f"Error: {error_msg}", str(e))
                raise

            except Exception as e:
                error_msg = str(e)
                logger.error(f"[PROCESS_URL_JOB] {job_id} Error: {error_msg}")
                add_step(job_id, "Procesamiento", "error")
                update_job_status(job_id, JobStatus.FAILED, f"Error: {error_msg}", str(e))
                raise

        except Exception as e:
            logger.error(f"[PROCESS_URL_JOB] {job_id} Fallo general: {e}")
            update_job_status(
                job_id,
                JobStatus.FAILED,
                "Error en procesamiento",
                str(e),
            )
        finally:
            teardown_pipeline_logging(log_handler)

    # Start in background thread
    thread = threading.Thread(target=run_process, daemon=True)
    thread.start()
