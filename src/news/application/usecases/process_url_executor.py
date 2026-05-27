"""Async executor for process_url with job tracking.

Responsibilities:
- Job lifecycle management (status, progress, steps)
- Thread management for background execution
- Error handling and logging

Delegates to:
- ProcessUrlWithPublishingUseCase: business logic (processing + publishing)
"""

import threading
from config.logging_config import get_logger
from src.news.application.usecases.pipeline_job import (
    JobStatus,
    update_job_status,
    add_step,
    _jobs_store,
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

            # Step 1: Initialize
            add_step(job_id, "Inicializando", "running")
            try:
                from src.news.entrypoints.api.dependencies import get_content_extractor
                from src.news.application.usecases.process_url_with_publishing import (
                    ProcessUrlWithPublishingUseCase,
                )

                extractor = get_content_extractor()
                usecase = ProcessUrlWithPublishingUseCase(
                    content_extractor=extractor,
                    use_ai=use_ai,
                    model_provider=model_provider,
                    publish_to_social=True,
                )
                add_step(job_id, "Inicializando", "ok")
            except Exception as e:
                logger.error(f"[PROCESS_URL_JOB] {job_id} Error inicializando: {e}")
                add_step(job_id, "Inicializando", "error")
                raise

            # Step 2: Process URL and publish (orchestrated by usecase)
            add_step(job_id, "Procesando URL", "running")
            try:
                logger.info(f"[PROCESS_URL_JOB] {job_id} Procesando {url}")
                result = usecase.execute(url)
                add_step(job_id, "Procesando URL", "ok")
                logger.info(f"[PROCESS_URL_JOB] {job_id} Procesamiento completado")

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

            # Step 3: Success - store result and update status
            add_step(job_id, "Completado", "ok")

            title = result.get("article_data", {}).get("article", {}).get("title", "")
            post = result.get("post", "")[:200] if result.get("post") else ""

            _jobs_store[job_id]["result"] = {
                "title": title,
                "post": post,
                "mode": result.get("mode", ""),
                "publish_results": result.get("publish_results"),
            }

            update_job_status(
                job_id,
                JobStatus.COMPLETED,
                f"✅ Procesado y publicado: {title[:50]}...",
            )

        except Exception as e:
            logger.error(f"[PROCESS_URL_JOB] {job_id} Fallo general: {e}")
            if job_id in _jobs_store:
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
