import time
import logging
from datetime import datetime
from typing import Optional, List
from src.news.domain.entities.processing_metric import (
    ProcessingMetric,
    StepMetric,
    PipelineType,
    StepStatus,
)
from src.news.domain.ports.metrics_repository_port import MetricsRepositoryPort
from config.logging_config import get_logger

logger = get_logger("news_bot.metrics")


class MetricsCollector:
    """Collects step-level timing data and flushes complete metrics to repository."""

    def __init__(
        self,
        execution_id: str,
        pipeline_type: PipelineType,
        metrics_repo: MetricsRepositoryPort,
    ):
        """
        Initialize metrics collector.

        Args:
            execution_id: Unique identifier for this execution (job ID)
            pipeline_type: Type of pipeline (NEWS, AUDIO, VIDEO)
            metrics_repo: Repository for persisting metrics
        """
        self.execution_id = execution_id
        self.pipeline_type = pipeline_type
        self.metrics_repo = metrics_repo
        self.steps: List[StepMetric] = []
        self.start_time_ns = time.time_ns()

    def record_step(
        self,
        name: str,
        status: str,
        duration_ms: int,
        error: Optional[str] = None,
    ) -> None:
        """
        Record a pipeline step execution.

        Args:
            name: Step name (e.g., "Process URL", "Fetch Images")
            status: Step status - "OK", "FAILED", or "SKIPPED"
            duration_ms: Execution duration in milliseconds
            error: Error message if status is FAILED
        """
        try:
            step_status = StepStatus(status)
        except ValueError:
            logger.warning(
                f"Invalid step status '{status}', using FAILED. Error: {error}"
            )
            step_status = StepStatus.FAILED

        step_metric = StepMetric(
            name=name,
            status=step_status,
            duration_ms=duration_ms,
            error=error,
        )
        self.steps.append(step_metric)
        logger.debug(
            f"[{self.pipeline_type.value}] Recorded step: {name} "
            f"({status}, {duration_ms}ms)"
        )

    def flush(self) -> bool:
        """
        Create and persist the complete execution metric (synchronous, non-blocking).

        Returns:
            True if flush succeeded, False otherwise
        """
        try:
            total_duration_ns = time.time_ns() - self.start_time_ns
            total_duration_ms = total_duration_ns // 1_000_000

            # Determine success: all steps are OK or SKIPPED (no FAILED steps)
            has_failures = any(
                step.status == StepStatus.FAILED for step in self.steps
            )
            success = not has_failures

            metric = ProcessingMetric(
                execution_id=self.execution_id,
                pipeline_type=self.pipeline_type,
                steps=self.steps,
                total_duration_ms=total_duration_ms,
                success=success,
                created_at=datetime.now(),
            )

            self.metrics_repo.save(metric)
            logger.info(
                f"[{self.pipeline_type.value}] Metrics flushed for {self.execution_id}: "
                f"{total_duration_ms}ms, {len(self.steps)} steps, success={success}"
            )
            return True
        except Exception as e:
            logger.error(
                f"[{self.pipeline_type.value}] Failed to flush metrics: {e}",
                exc_info=True,
            )
            # Don't raise - metrics failure should not crash the pipeline
            return False

    def step_count(self) -> int:
        """Get number of recorded steps."""
        return len(self.steps)

    def error_count(self) -> int:
        """Get number of failed steps."""
        return sum(1 for step in self.steps if step.status == StepStatus.FAILED)

    def skipped_count(self) -> int:
        """Get number of skipped steps."""
        return sum(1 for step in self.steps if step.status == StepStatus.SKIPPED)
