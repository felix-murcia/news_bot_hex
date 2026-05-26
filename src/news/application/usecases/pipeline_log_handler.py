"""Custom logging handler for pipeline job feedback."""

import logging
from typing import Optional


class PipelineJobLogHandler(logging.Handler):
    """
    Custom logging handler that captures logs for pipeline jobs.

    Updates the job's last_log field in real-time so the frontend can
    show live feedback about what's happening in each pipeline step.
    """

    def __init__(self, job_id: str):
        """
        Initialize handler with job ID.

        Args:
            job_id: The pipeline job ID to update with log messages
        """
        super().__init__()
        self.job_id = job_id

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record by updating the job's last_log field.

        Args:
            record: LogRecord to process
        """
        try:
            from src.news.application.usecases.pipeline_job import update_job_log

            # Format the log message
            msg = self.format(record)

            # Extract just the message part, removing timestamps and redundant prefixes
            # Format: [COMPONENT] Message text
            if "] " in msg:
                # Take everything after the first "]"
                msg = msg.split("] ", 1)[-1] if "] " in msg else msg

            # Update the job with this log message
            update_job_log(self.job_id, msg)
        except Exception:
            # Don't let logging errors break the pipeline
            pass


def setup_pipeline_logging(job_id: str) -> Optional[PipelineJobLogHandler]:
    """
    Setup logging handler for a specific pipeline job.

    Attaches a custom handler to the root logger and returns it so it can
    be removed later.

    Args:
        job_id: The pipeline job ID

    Returns:
        The handler instance (for later removal)
    """
    handler = PipelineJobLogHandler(job_id)

    # Use simple format for live feedback
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    # Attach to root logger to capture all logs
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    return handler


def teardown_pipeline_logging(handler: Optional[PipelineJobLogHandler]) -> None:
    """
    Remove logging handler after pipeline completes.

    Args:
        handler: The handler to remove
    """
    if handler:
        root_logger = logging.getLogger()
        root_logger.removeHandler(handler)
