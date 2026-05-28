import logging
from datetime import datetime, timedelta
from typing import Optional, List, Literal
from src.news.domain.ports.metrics_repository_port import MetricsRepositoryPort
from src.news.domain.entities.processing_metric import (
    ProcessingMetric,
    StepMetric,
    PipelineType,
    StepStatus,
)
from config.logging_config import get_logger

logger = get_logger("news_bot.infra.metrics")


class MongoMetricsRepository(MetricsRepositoryPort):
    """MongoDB adapter for metrics persistence."""

    COLLECTION_NAME = "pipeline_metrics"

    def __init__(self, db=None):
        if db is None:
            from src.shared.adapters.mongo_db import get_database

            db = get_database()
        self._db = db
        self._collection = self._db[self.COLLECTION_NAME]
        self._ensure_indices()

    def _ensure_indices(self) -> None:
        """Create necessary database indices."""
        try:
            # Compound index for efficient range queries
            self._collection.create_index(
                [("pipeline_type", 1), ("created_at", -1)],
                name="pipeline_type_created_at",
            )
            # Index for date range queries
            self._collection.create_index(
                [("created_at", -1)], name="created_at"
            )
        except Exception as e:
            logger.warning(f"Could not create indices: {e}")

    def save(self, metric: ProcessingMetric) -> None:
        """Persist a pipeline execution metric (synchronous, non-blocking)."""
        try:
            doc = {
                "execution_id": metric.execution_id,
                "pipeline_type": metric.pipeline_type.value,
                "steps": [
                    {
                        "name": step.name,
                        "status": step.status.value,
                        "duration_ms": step.duration_ms,
                        "error": step.error,
                    }
                    for step in metric.steps
                ],
                "total_duration_ms": metric.total_duration_ms,
                "success": metric.success,
                "error_count": metric.error_count(),
                "success_count": metric.success_count(),
                "step_count": metric.step_count(),
                "created_at": metric.created_at,
            }
            self._collection.insert_one(doc)
            logger.debug(
                f"Saved metrics for {metric.pipeline_type.value} "
                f"execution {metric.execution_id}"
            )
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")
            raise

    def get_by_date_range(
        self,
        start: datetime,
        end: datetime,
        pipeline_type: Optional[PipelineType] = None,
    ) -> List[ProcessingMetric]:
        """Retrieve metrics for a date range (synchronous)."""
        try:
            query = {"created_at": {"$gte": start, "$lte": end}}
            if pipeline_type:
                query["pipeline_type"] = pipeline_type.value

            results = list(
                self._collection.find(query, {"_id": 0}).sort(
                    "created_at", -1
                )
            )
            metrics = []
            for doc in results:
                metric = self._doc_to_metric(doc)
                metrics.append(metric)
            return metrics
        except Exception as e:
            logger.error(f"Error retrieving metrics by date range: {e}")
            return []

    def get_aggregated(
        self,
        pipeline_type: PipelineType,
        period: Literal["hourly", "daily", "weekly"],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[dict]:
        """Get aggregated metrics with percentiles (synchronous)."""
        try:
            if end is None:
                end = datetime.now()
            if start is None:
                start = end - timedelta(days=7)

            # Determine date format for MongoDB $dateToString
            date_formats = {
                "hourly": "%Y-%m-%d %H:00",
                "daily": "%Y-%m-%d",
                "weekly": "%Y-W%U",
            }
            date_format = date_formats.get(period, "%Y-%m-%d")

            pipeline = [
                {
                    "$match": {
                        "pipeline_type": pipeline_type.value,
                        "created_at": {"$gte": start, "$lte": end},
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": date_format,
                                "date": "$created_at",
                            }
                        },
                        "durations": {"$push": "$total_duration_ms"},
                        "count": {"$sum": 1},
                        "error_count": {
                            "$sum": {
                                "$cond": [{"$eq": ["$success", False]}, 1, 0]
                            }
                        },
                    }
                },
                {"$sort": {"_id": 1}},
            ]

            results = list(self._collection.aggregate(pipeline))

            # Calculate percentiles
            aggregated = []
            for doc in results:
                durations = sorted(doc["durations"])
                count = len(durations)

                p50_idx = int(count * 0.50) - 1 if count > 0 else 0
                p95_idx = int(count * 0.95) - 1 if count > 0 else 0
                p99_idx = int(count * 0.99) - 1 if count > 0 else 0

                # Clamp indices
                p50_idx = max(0, min(p50_idx, count - 1)) if count > 0 else 0
                p95_idx = max(0, min(p95_idx, count - 1)) if count > 0 else 0
                p99_idx = max(0, min(p99_idx, count - 1)) if count > 0 else 0

                success_rate = (
                    1.0 - (doc["error_count"] / doc["count"])
                    if doc["count"] > 0
                    else 1.0
                )

                aggregated.append(
                    {
                        "timestamp": doc["_id"],
                        "p50": durations[p50_idx] if count > 0 else 0,
                        "p95": durations[p95_idx] if count > 0 else 0,
                        "p99": durations[p99_idx] if count > 0 else 0,
                        "count": doc["count"],
                        "error_count": doc["error_count"],
                        "success_rate": round(success_rate, 3),
                    }
                )

            logger.debug(
                f"Retrieved {len(aggregated)} aggregated metrics for "
                f"{pipeline_type.value} ({period})"
            )
            return aggregated
        except Exception as e:
            logger.error(f"Error retrieving aggregated metrics: {e}")
            return []

    def _doc_to_metric(self, doc: dict) -> ProcessingMetric:
        """Convert MongoDB document to ProcessingMetric value object."""
        steps = [
            StepMetric(
                name=step["name"],
                status=StepStatus(step["status"]),
                duration_ms=step["duration_ms"],
                error=step.get("error"),
            )
            for step in doc["steps"]
        ]
        return ProcessingMetric(
            execution_id=doc["execution_id"],
            pipeline_type=PipelineType(doc["pipeline_type"]),
            steps=steps,
            total_duration_ms=doc["total_duration_ms"],
            success=doc["success"],
            created_at=doc["created_at"],
        )
