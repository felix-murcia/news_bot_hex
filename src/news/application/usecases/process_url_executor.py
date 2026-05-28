"""Async executor for process_url with job tracking.

Single Responsibility:
- Job lifecycle management (status, progress, steps)
- Thread management for background execution
- Error handling and logging

Does NOT handle:
- Business logic (delegated to ProcessUrlWithPublishingUseCase)
- Dependency creation (injected)
"""

import threading
from typing import Callable, Dict, Any

from config.logging_config import get_logger
from src.news.application.usecases.pipeline_job import (
    JobStatus,
    ProcessingStepName,
    ProcessingStepStatus,
    JobRepositoryPort,
)
from src.news.application.usecases.pipeline_log_handler import (
    setup_pipeline_logging,
    teardown_pipeline_logging,
)

logger = get_logger("news_bot.process_url.executor")


class ProcessUrlJobCoordinator:
    """Coordinates job lifecycle for URL processing (job tracking + execution)."""

    def __init__(
        self,
        job_repository: JobRepositoryPort,
        process_url_usecase: Callable[[str], Dict[str, Any]],
    ):
        """
        Args:
            job_repository: Port for job persistence (status, steps, etc.)
            process_url_usecase: Pipeline executor that processes URL
        """
        self.job_repository = job_repository
        self.process_url_usecase = process_url_usecase

    def execute_async(self, job_id: str, url: str) -> None:
        """Execute process_url in background thread with job tracking."""

        def run_process():
            log_handler = setup_pipeline_logging(job_id)

            try:
                self._run_with_tracking(job_id, url)
            except Exception as e:
                logger.error(f"[PROCESS_URL_JOB] {job_id} Unexpected error: {e}")
                if self.job_repository.get(job_id):
                    self.job_repository.update_status(
                        job_id,
                        JobStatus.FAILED,
                        "Error en procesamiento",
                        str(e),
                    )
            finally:
                teardown_pipeline_logging(log_handler)

        thread = threading.Thread(target=run_process, daemon=True)
        thread.start()

    def _run_with_tracking(self, job_id: str, url: str) -> None:
        """Execute with job tracking (status updates, steps, error handling)."""
        self.job_repository.update_status(job_id, JobStatus.RUNNING, "Procesando URL...")
        logger.info(f"[PROCESS_URL_JOB] {job_id} iniciado: {url}")

        try:
            # Step 1: Initialize
            self.job_repository.add_step(job_id, ProcessingStepName.INITIALIZING, ProcessingStepStatus.RUNNING)

            logger.info(f"[PROCESS_URL_JOB] {job_id} Inicializando")
            self.job_repository.add_step(job_id, ProcessingStepName.INITIALIZING, ProcessingStepStatus.OK)

            # Step 2: Process URL (usecase handles content extraction + publishing)
            self.job_repository.add_step(job_id, ProcessingStepName.PROCESSING_URL, ProcessingStepStatus.RUNNING)

            try:
                logger.info(f"[PROCESS_URL_JOB] {job_id} Procesando {url}")
                result = self.process_url_usecase(url, job_id=job_id)
                self.job_repository.add_step(job_id, ProcessingStepName.PROCESSING_URL, ProcessingStepStatus.OK)
                logger.info(f"[PROCESS_URL_JOB] {job_id} Procesamiento completado")
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[PROCESS_URL_JOB] {job_id} Error procesando: {error_msg}")
                self.job_repository.add_step(job_id, ProcessingStepName.PROCESSING_URL, ProcessingStepStatus.ERROR)
                self.job_repository.update_status(job_id, JobStatus.FAILED, f"Error: {error_msg}", str(e))
                raise

            # Step 3: Success
            self.job_repository.add_step(job_id, ProcessingStepName.COMPLETED, ProcessingStepStatus.OK)

            title = result.get("article_data", {}).get("article", {}).get("title", "")
            post = result.get("post", "")[:200] if result.get("post") else ""

            # Store result in job (for client to retrieve)
            job = self.job_repository.get(job_id)
            if job:
                job["result"] = {
                    "title": title,
                    "post": post,
                    "mode": result.get("mode", ""),
                    "publish_results": result.get("publish_results"),
                }

            self.job_repository.update_status(
                job_id,
                JobStatus.COMPLETED,
                f"✅ Procesado y publicado: {title[:50]}...",
            )

        except Exception:
            # Error already logged and status updated above
            raise
