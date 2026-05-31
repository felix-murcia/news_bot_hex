"""Metrics API endpoints for pipeline execution observability."""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from src.news.entrypoints.api.dependencies import get_metrics_repository
from src.news.domain.entities.processing_metric import PipelineType

router = APIRouter()


@router.get("/recent-executions")
def get_recent_executions(
    pipeline_type: Optional[str] = Query(None, description="Filter by pipeline type (NEWS, AUDIO, VIDEO)"),
    limit: int = Query(10, ge=1, le=100, description="Number of recent executions to return"),
    metrics_repo=Depends(get_metrics_repository),
):
    """
    Get recent pipeline executions with their status and duration.

    Returns: List of recent executions with execution_id, timestamp, duration, status, step_count.
    """
    try:
        pipeline_type_enum = None
        if pipeline_type:
            pipeline_type_enum = PipelineType(pipeline_type.upper())

        executions = metrics_repo.get_recent_executions(
            pipeline_type=pipeline_type_enum,
            limit=limit
        )

        return {
            "status": "ok",
            "pipeline_type": pipeline_type or "ALL",
            "data": executions,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "data": [],
        }


@router.get("/step-breakdown")
def get_step_breakdown(
    pipeline_type: Optional[str] = Query(None, description="Filter by pipeline type (NEWS, AUDIO, VIDEO)"),
    days: int = Query(7, ge=1, le=90, description="Number of days to aggregate"),
    metrics_repo=Depends(get_metrics_repository),
):
    """
    Get average duration and success rate per pipeline step.

    Returns: List of steps with avg_duration_ms, success_count, error_count.
    """
    try:
        pipeline_type_enum = None
        if pipeline_type:
            pipeline_type_enum = PipelineType(pipeline_type.upper())

        end = datetime.now()
        start = end - timedelta(days=days)

        steps_data = metrics_repo.get_step_breakdown(
            pipeline_type=pipeline_type_enum or PipelineType.NEWS,
            start=start,
            end=end,
        )

        return {
            "status": "ok",
            "pipeline_type": pipeline_type or "NEWS",
            "days": days,
            "data": steps_data,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "data": [],
        }


@router.get("/activity-heatmap")
def get_activity_heatmap(
    pipeline_type: Optional[str] = Query(None, description="Filter by pipeline type (NEWS, AUDIO, VIDEO)"),
    days: int = Query(7, ge=1, le=30, description="Number of days to include (max 30)"),
    metrics_repo=Depends(get_metrics_repository),
):
    """
    Get execution activity count by hour and day for heatmap visualization.

    Returns: 2D array [hour][day] with execution counts.
    """
    try:
        pipeline_type_enum = None
        if pipeline_type:
            pipeline_type_enum = PipelineType(pipeline_type.upper())

        end = datetime.now()
        start = end - timedelta(days=days)

        heatmap_data = metrics_repo.get_activity_heatmap(
            pipeline_type=pipeline_type_enum or PipelineType.NEWS,
            start=start,
            end=end,
        )

        return {
            "status": "ok",
            "pipeline_type": pipeline_type or "NEWS",
            "days": days,
            "data": heatmap_data,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "data": [],
        }


@router.get("/daily-average")
def get_daily_average(
    pipeline_type: Optional[str] = Query(None, description="Filter by pipeline type (NEWS, AUDIO, VIDEO)"),
    days: int = Query(7, ge=1, le=90, description="Number of days to aggregate"),
    metrics_repo=Depends(get_metrics_repository),
):
    """
    Get average metrics aggregated daily.

    Returns metrics like P50, P95, P99 latencies, success rate, and throughput.
    """

    try:
        pipeline_type_enum = None
        if pipeline_type:
            pipeline_type_enum = PipelineType(pipeline_type.upper())

        end = datetime.now()
        start = end - timedelta(days=days)

        aggregated = metrics_repo.get_aggregated(
            pipeline_type=pipeline_type_enum or PipelineType.NEWS,
            period="daily",
            start=start,
            end=end,
        )

        return {
            "status": "ok",
            "pipeline_type": pipeline_type or "NEWS",
            "days": days,
            "data": aggregated,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "data": [],
        }


@router.get("/hourly")
def get_hourly_metrics(
    pipeline_type: Optional[str] = Query(None, description="Filter by pipeline type (NEWS, AUDIO, VIDEO)"),
    hours: int = Query(24, ge=1, le=240, description="Number of hours to aggregate"),
    metrics_repo=Depends(get_metrics_repository),
):
    """
    Get average metrics aggregated hourly.

    Useful for detailed time-series analysis of recent performance.
    """

    try:
        pipeline_type_enum = None
        if pipeline_type:
            pipeline_type_enum = PipelineType(pipeline_type.upper())

        end = datetime.now()
        start = end - timedelta(hours=hours)

        aggregated = metrics_repo.get_aggregated(
            pipeline_type=pipeline_type_enum or PipelineType.NEWS,
            period="hourly",
            start=start,
            end=end,
        )

        return {
            "status": "ok",
            "pipeline_type": pipeline_type or "NEWS",
            "hours": hours,
            "data": aggregated,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "data": [],
        }


@router.get("/health")
def get_health_metrics(
    period: str = Query("24h", description="Time period: 24h, 7d, 30d"),
    metrics_repo=Depends(get_metrics_repository),
):
    """
    Get health summary for the requested period (24h, 7d, 30d).
    """
    PERIOD_MAP = {"24h": 1, "7d": 7, "30d": 30}
    days = PERIOD_MAP.get(period, 1)
    hours = days * 24

    try:
        end = datetime.now()
        start = end - timedelta(days=days)

        results = {}
        for pipeline_type in [PipelineType.NEWS, PipelineType.AUDIO, PipelineType.VIDEO]:
            try:
                aggregated = metrics_repo.get_aggregated(
                    pipeline_type=pipeline_type,
                    period="hourly",
                    start=start,
                    end=end,
                )

                if aggregated:
                    total_count = sum(item.get("count", 0) for item in aggregated)
                    total_errors = sum(item.get("error_count", 0) for item in aggregated)
                    error_rate = (total_errors / total_count) if total_count > 0 else 0
                    p95_latencies = [item.get("p95", 0) for item in aggregated if item.get("p95")]
                    p95_latency = max(p95_latencies) if p95_latencies else 0
                    throughput = total_count / hours

                    results[pipeline_type.value] = {
                        "error_rate": round(error_rate, 3),
                        "p95_latency_ms": p95_latency,
                        "throughput_per_hour": round(throughput, 2),
                        "total_executions": total_count,
                        "failed_executions": total_errors,
                    }
            except Exception as e:
                results[pipeline_type.value] = {"error": str(e)}

        return {
            "status": "ok",
            "period": period,
            "data": results,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "data": {},
        }
