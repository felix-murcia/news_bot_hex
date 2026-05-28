from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Literal
from src.news.domain.entities.processing_metric import ProcessingMetric, PipelineType


class MetricsRepositoryPort(ABC):
    """Port for persisting and querying pipeline execution metrics."""

    @abstractmethod
    def save(self, metric: ProcessingMetric) -> None:
        """
        Persist a pipeline execution metric (synchronous, non-blocking).

        Args:
            metric: ProcessingMetric value object to persist

        Raises:
            Exception: If persistence fails (implementation-dependent)
        """
        pass

    @abstractmethod
    def get_by_date_range(
        self,
        start: datetime,
        end: datetime,
        pipeline_type: Optional[PipelineType] = None,
    ) -> List[ProcessingMetric]:
        """
        Retrieve metrics for a date range (synchronous).

        Args:
            start: Start datetime (inclusive)
            end: End datetime (inclusive)
            pipeline_type: Filter by pipeline type (None = all types)

        Returns:
            List of ProcessingMetric objects ordered by created_at descending
        """
        pass

    @abstractmethod
    def get_aggregated(
        self,
        pipeline_type: PipelineType,
        period: Literal["hourly", "daily", "weekly"],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[dict]:
        """
        Get aggregated metrics with percentiles.

        Args:
            pipeline_type: Pipeline type to aggregate
            period: Aggregation period
            start: Start datetime (defaults to 7 days ago)
            end: End datetime (defaults to now)

        Returns:
            List of aggregated metric dicts:
            [
                {
                    "timestamp": datetime,
                    "p50": int (milliseconds),
                    "p95": int (milliseconds),
                    "p99": int (milliseconds),
                    "count": int,
                    "error_count": int,
                    "success_rate": float (0.0-1.0),
                }
            ]
        """
        pass

    @abstractmethod
    def get_recent_executions(
        self,
        pipeline_type: Optional[PipelineType] = None,
        limit: int = 10,
    ) -> List[dict]:
        """
        Get recent pipeline executions.

        Args:
            pipeline_type: Filter by pipeline type (None = all types)
            limit: Maximum number of executions to return

        Returns:
            List of recent execution dicts:
            [
                {
                    "execution_id": str,
                    "pipeline_type": str,
                    "timestamp": datetime,
                    "duration_ms": int,
                    "status": "OK" | "FAILED",
                    "step_count": int,
                }
            ]
        """
        pass

    @abstractmethod
    def get_step_breakdown(
        self,
        pipeline_type: PipelineType,
        start: datetime,
        end: datetime,
    ) -> List[dict]:
        """
        Get average duration and success rate per pipeline step.

        Args:
            pipeline_type: Pipeline type to analyze
            start: Start datetime
            end: End datetime

        Returns:
            List of step breakdown dicts:
            [
                {
                    "name": str (step name),
                    "avg_duration_ms": float,
                    "success_count": int,
                    "error_count": int,
                    "success_rate": float (0.0-1.0),
                }
            ]
        """
        pass

    @abstractmethod
    def get_activity_heatmap(
        self,
        pipeline_type: PipelineType,
        start: datetime,
        end: datetime,
    ) -> List[List[int]]:
        """
        Get execution count by hour and day for heatmap visualization.

        Args:
            pipeline_type: Pipeline type to analyze
            start: Start datetime
            end: End datetime

        Returns:
            2D array [hour (0-23)][day (0-6)]:
            [[count_h0_d0, count_h0_d1, ...], [count_h1_d0, ...], ...]
        """
        pass
