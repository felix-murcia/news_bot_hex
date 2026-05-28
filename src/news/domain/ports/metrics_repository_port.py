from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Literal
from src.news.domain.entities.processing_metric import ProcessingMetric, PipelineType


class MetricsRepositoryPort(ABC):
    """Port for persisting and querying pipeline execution metrics."""

    @abstractmethod
    async def save(self, metric: ProcessingMetric) -> None:
        """
        Persist a pipeline execution metric.

        Args:
            metric: ProcessingMetric value object to persist

        Raises:
            Exception: If persistence fails (implementation-dependent)
        """
        pass

    @abstractmethod
    async def get_by_date_range(
        self,
        start: datetime,
        end: datetime,
        pipeline_type: Optional[PipelineType] = None,
    ) -> List[ProcessingMetric]:
        """
        Retrieve metrics for a date range.

        Args:
            start: Start datetime (inclusive)
            end: End datetime (inclusive)
            pipeline_type: Filter by pipeline type (None = all types)

        Returns:
            List of ProcessingMetric objects ordered by created_at descending
        """
        pass

    @abstractmethod
    async def get_aggregated(
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
