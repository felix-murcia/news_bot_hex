"""Integration tests for metrics API endpoints.

Tests the complete flow:
- Request parsing
- Dependency injection
- Response formatting
- Error handling
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from src.news.entrypoints.api.metrics_router import router
from fastapi import FastAPI
from src.news.domain.entities.processing_metric import PipelineType


# Create a test app with the metrics router
def create_test_app():
    """Create a FastAPI test application."""
    app = FastAPI()

    def mock_get_metrics_repo():
        """Provide mock repository."""
        return Mock()

    # Override dependency
    from src.news.entrypoints.api.dependencies import get_metrics_repository
    app.dependency_overrides[get_metrics_repository] = mock_get_metrics_repo

    app.include_router(router, prefix="/metrics")
    return app


@pytest.fixture
def client():
    """Create test client."""
    app = create_test_app()
    return TestClient(app)


@pytest.fixture
def mock_repo():
    """Create mock repository."""
    return Mock()


class TestDailyAverageEndpoint:
    """Test GET /metrics/daily-average endpoint."""

    def test_daily_average_default_params(self, client):
        """GET /metrics/daily-average with default parameters."""
        with patch('src.news.entrypoints.api.metrics_router.get_metrics_repository') as mock_dep:
            mock_repo = Mock()
            mock_repo.get_aggregated.return_value = [
                {"timestamp": "2026-05-28", "p50": 1000, "p95": 2000, "p99": 3000, "count": 10, "error_count": 1, "success_rate": 0.9}
            ]
            mock_dep.return_value = mock_repo

            response = client.get("/metrics/daily-average")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["pipeline_type"] == "NEWS"  # default
            assert data["days"] == 7  # default

    def test_daily_average_custom_params(self, client):
        """GET /metrics/daily-average with custom pipeline_type and days."""
        with patch('src.news.entrypoints.api.metrics_router.get_metrics_repository') as mock_dep:
            mock_repo = Mock()
            mock_repo.get_aggregated.return_value = []
            mock_dep.return_value = mock_repo

            response = client.get("/metrics/daily-average?pipeline_type=AUDIO&days=14")

            assert response.status_code == 200
            data = response.json()
            assert data["pipeline_type"] == "AUDIO"
            assert data["days"] == 14

    def test_daily_average_invalid_pipeline_type(self, client):
        """GET /metrics/daily-average with invalid pipeline_type should error."""
        with patch('src.news.entrypoints.api.metrics_router.get_metrics_repository') as mock_dep:
            mock_repo = Mock()
            mock_repo.get_aggregated.side_effect = ValueError("Invalid pipeline type")
            mock_dep.return_value = mock_repo

            response = client.get("/metrics/daily-average?pipeline_type=INVALID")

            assert response.status_code == 200  # FastAPI returns 200 even for error responses
            data = response.json()
            assert data["status"] == "error"

    def test_daily_average_days_validation(self, client):
        """GET /metrics/daily-average should validate days parameter."""
        response = client.get("/metrics/daily-average?days=0")
        assert response.status_code == 422  # Validation error

        response = client.get("/metrics/daily-average?days=91")
        assert response.status_code == 422  # Max is 90


class TestHourlyEndpoint:
    """Test GET /metrics/hourly endpoint."""

    def test_hourly_default_params(self, client):
        """GET /metrics/hourly with default parameters."""
        with patch('src.news.entrypoints.api.metrics_router.get_metrics_repository') as mock_dep:
            mock_repo = Mock()
            mock_repo.get_aggregated.return_value = []
            mock_dep.return_value = mock_repo

            response = client.get("/metrics/hourly")

            assert response.status_code == 200
            data = response.json()
            assert data["hours"] == 24  # default

    def test_hourly_custom_hours(self, client):
        """GET /metrics/hourly with custom hours."""
        with patch('src.news.entrypoints.api.metrics_router.get_metrics_repository') as mock_dep:
            mock_repo = Mock()
            mock_repo.get_aggregated.return_value = []
            mock_dep.return_value = mock_repo

            response = client.get("/metrics/hourly?hours=48&pipeline_type=VIDEO")

            assert response.status_code == 200
            data = response.json()
            assert data["hours"] == 48
            assert data["pipeline_type"] == "VIDEO"


class TestRecentExecutionsEndpoint:
    """Test GET /metrics/recent-executions endpoint."""

    def test_recent_executions_default(self, client):
        """GET /metrics/recent-executions with defaults."""
        with patch('src.news.entrypoints.api.metrics_router.get_metrics_repository') as mock_dep:
            mock_repo = Mock()
            mock_repo.get_recent_executions.return_value = [
                {
                    "execution_id": "exec-001",
                    "pipeline_type": "NEWS",
                    "timestamp": "2026-05-28T10:00:00",
                    "duration_ms": 3000,
                    "status": "OK",
                    "step_count": 5,
                },
            ]
            mock_dep.return_value = mock_repo

            response = client.get("/metrics/recent-executions")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert len(data["data"]) == 1
            assert data["data"][0]["status"] == "OK"

    def test_recent_executions_with_limit(self, client):
        """GET /metrics/recent-executions with custom limit."""
        with patch('src.news.entrypoints.api.metrics_router.get_metrics_repository') as mock_dep:
            mock_repo = Mock()
            mock_repo.get_recent_executions.return_value = []
            mock_dep.return_value = mock_repo

            response = client.get("/metrics/recent-executions?limit=20")

            assert response.status_code == 200
            # Verify get_recent_executions was called with limit
            mock_repo.get_recent_executions.assert_called()
            call_kwargs = mock_repo.get_recent_executions.call_args[1]
            assert call_kwargs.get("limit") == 20


class TestStepBreakdownEndpoint:
    """Test GET /metrics/step-breakdown endpoint."""

    def test_step_breakdown_default(self, client):
        """GET /metrics/step-breakdown with defaults."""
        with patch('src.news.entrypoints.api.metrics_router.get_metrics_repository') as mock_dep:
            mock_repo = Mock()
            mock_repo.get_step_breakdown.return_value = [
                {
                    "name": "Download",
                    "avg_duration_ms": 500,
                    "success_count": 10,
                    "error_count": 1,
                    "success_rate": 0.909,
                },
                {
                    "name": "Process",
                    "avg_duration_ms": 2000,
                    "success_count": 10,
                    "error_count": 0,
                    "success_rate": 1.0,
                },
            ]
            mock_dep.return_value = mock_repo

            response = client.get("/metrics/step-breakdown")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert len(data["data"]) == 2
            assert data["data"][0]["name"] == "Download"
            assert data["data"][0]["success_rate"] == 0.909

    def test_step_breakdown_custom_days(self, client):
        """GET /metrics/step-breakdown with custom days."""
        with patch('src.news.entrypoints.api.metrics_router.get_metrics_repository') as mock_dep:
            mock_repo = Mock()
            mock_repo.get_step_breakdown.return_value = []
            mock_dep.return_value = mock_repo

            response = client.get("/metrics/step-breakdown?pipeline_type=AUDIO&days=30")

            assert response.status_code == 200
            mock_repo.get_step_breakdown.assert_called()


class TestActivityHeatmapEndpoint:
    """Test GET /metrics/activity-heatmap endpoint."""

    def test_activity_heatmap_default(self, client):
        """GET /metrics/activity-heatmap with defaults."""
        with patch('src.news.entrypoints.api.metrics_router.get_metrics_repository') as mock_dep:
            mock_repo = Mock()
            # Return 24x7 grid
            mock_repo.get_activity_heatmap.return_value = [
                [0] * 7 for _ in range(24)
            ]
            mock_dep.return_value = mock_repo

            response = client.get("/metrics/activity-heatmap")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert len(data["data"]) == 24
            assert all(len(day) == 7 for day in data["data"])

    def test_activity_heatmap_with_data(self, client):
        """GET /metrics/activity-heatmap returns actual data."""
        with patch('src.news.entrypoints.api.metrics_router.get_metrics_repository') as mock_dep:
            mock_repo = Mock()
            heatmap = [[0] * 7 for _ in range(24)]
            heatmap[9][0] = 5  # 5 executions at 9am Monday
            heatmap[14][2] = 8  # 8 executions at 2pm Wednesday
            mock_repo.get_activity_heatmap.return_value = heatmap
            mock_dep.return_value = mock_repo

            response = client.get("/metrics/activity-heatmap")

            assert response.status_code == 200
            data = response.json()
            assert data["data"][9][0] == 5
            assert data["data"][14][2] == 8


class TestHealthEndpoint:
    """Test GET /metrics/health endpoint."""

    def test_health_endpoint(self, client):
        """GET /metrics/health returns health summary."""
        with patch('src.news.entrypoints.api.metrics_router.get_metrics_repository') as mock_dep:
            mock_repo = Mock()
            # Mock aggregated data for all pipeline types
            mock_repo.get_aggregated.return_value = [
                {"timestamp": "2026-05-28", "p50": 1000, "p95": 2000, "p99": 3000, "count": 10, "error_count": 1}
            ]
            mock_dep.return_value = mock_repo

            response = client.get("/metrics/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["period"] == "24h"
            assert "NEWS" in data["data"]
            assert "AUDIO" in data["data"]
            assert "VIDEO" in data["data"]

    def test_health_includes_error_rate(self, client):
        """GET /metrics/health includes error_rate calculation."""
        with patch('src.news.entrypoints.api.metrics_router.get_metrics_repository') as mock_dep:
            mock_repo = Mock()
            mock_repo.get_aggregated.return_value = [
                {"timestamp": "2026-05-28", "p50": 1000, "p95": 2000, "p99": 3000, "count": 100, "error_count": 5}
            ]
            mock_dep.return_value = mock_repo

            response = client.get("/metrics/health")

            assert response.status_code == 200
            data = response.json()
            # Each pipeline type should have metrics
            for pipeline_type in ["NEWS", "AUDIO", "VIDEO"]:
                assert "error_rate" in data["data"][pipeline_type]
                assert "p95_latency_ms" in data["data"][pipeline_type]
                assert "throughput_per_hour" in data["data"][pipeline_type]
                assert "total_executions" in data["data"][pipeline_type]


class TestErrorHandling:
    """Test error handling across endpoints."""

    def test_invalid_pipeline_type_error(self, client):
        """Invalid pipeline_type should return error response."""
        with patch('src.news.entrypoints.api.metrics_router.get_metrics_repository') as mock_dep:
            mock_repo = Mock()
            mock_repo.get_step_breakdown.side_effect = ValueError("Invalid pipeline type")
            mock_dep.return_value = mock_repo

            response = client.get("/metrics/step-breakdown?pipeline_type=INVALID")

            data = response.json()
            assert data["status"] == "error"

    def test_repository_error_graceful(self, client):
        """Repository errors should be caught and returned as error responses."""
        with patch('src.news.entrypoints.api.metrics_router.get_metrics_repository') as mock_dep:
            mock_repo = Mock()
            mock_repo.get_recent_executions.side_effect = Exception("DB connection failed")
            mock_dep.return_value = mock_repo

            response = client.get("/metrics/recent-executions")

            assert response.status_code == 200  # Still 200
            data = response.json()
            assert data["status"] == "error"
            assert data["data"] == []
