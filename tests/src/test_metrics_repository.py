"""Integration tests for MongoMetricsRepository.

Tests metrics persistence and retrieval:
- save() stores metrics correctly
- get_by_date_range() retrieves by date filter
- get_aggregated() calculates percentiles correctly
- Step breakdown and activity heatmap queries
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from src.news.infrastructure.adapters.mongo_metrics_repository import (
    MongoMetricsRepository,
)
from src.news.domain.entities.processing_metric import (
    ProcessingMetric,
    StepMetric,
    PipelineType,
    StepStatus,
)


class TestMongoMetricsRepositorySave:
    """Test saving metrics to MongoDB."""

    @pytest.fixture
    def repo(self):
        """Create repository with mock database."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.__getitem__.return_value = mock_collection
        repo = MongoMetricsRepository(db=mock_db)
        repo._collection = mock_collection
        return repo, mock_collection

    def test_save_creates_document(self, repo):
        """Save should insert document into collection."""
        repo_obj, mock_collection = repo

        metric = ProcessingMetric(
            execution_id="exec-001",
            pipeline_type=PipelineType.NEWS,
            steps=[
                StepMetric("Download", StepStatus.OK, 1000),
                StepMetric("Process", StepStatus.OK, 2000),
            ],
            total_duration_ms=3000,
            success=True,
            created_at=datetime.now(),
        )

        repo_obj.save(metric)

        # Verify insert_one was called
        mock_collection.insert_one.assert_called_once()

        # Get the document that was inserted
        call_args = mock_collection.insert_one.call_args
        doc = call_args[0][0]

        assert doc["execution_id"] == "exec-001"
        assert doc["pipeline_type"] == "NEWS"
        assert doc["total_duration_ms"] == 3000
        assert doc["success"] is True
        assert len(doc["steps"]) == 2

    def test_save_preserves_step_details(self, repo):
        """Save should preserve all step information."""
        repo_obj, mock_collection = repo

        metric = ProcessingMetric(
            execution_id="exec-002",
            pipeline_type=PipelineType.AUDIO,
            steps=[
                StepMetric("Download", StepStatus.OK, 500),
                StepMetric("Transcribe", StepStatus.FAILED, 200, "Timeout"),
            ],
            total_duration_ms=700,
            success=False,
            created_at=datetime.now(),
        )

        repo_obj.save(metric)

        call_args = mock_collection.insert_one.call_args
        doc = call_args[0][0]

        assert doc["steps"][0]["name"] == "Download"
        assert doc["steps"][0]["status"] == "OK"
        assert doc["steps"][0]["duration_ms"] == 500
        assert doc["steps"][0]["error"] is None

        assert doc["steps"][1]["name"] == "Transcribe"
        assert doc["steps"][1]["status"] == "FAILED"
        assert doc["steps"][1]["error"] == "Timeout"

    def test_save_calculates_error_and_success_counts(self, repo):
        """Save should calculate and store error/success counts."""
        repo_obj, mock_collection = repo

        metric = ProcessingMetric(
            execution_id="exec-003",
            pipeline_type=PipelineType.VIDEO,
            steps=[
                StepMetric("S1", StepStatus.OK, 100),
                StepMetric("S2", StepStatus.FAILED, 50),
                StepMetric("S3", StepStatus.OK, 100),
            ],
            total_duration_ms=250,
            success=False,
            created_at=datetime.now(),
        )

        repo_obj.save(metric)

        call_args = mock_collection.insert_one.call_args
        doc = call_args[0][0]

        assert doc["error_count"] == 1
        assert doc["success_count"] == 2
        assert doc["step_count"] == 3


class TestMongoMetricsRepositoryRetrieval:
    """Test retrieving metrics from MongoDB."""

    @pytest.fixture
    def sample_metrics(self):
        """Create sample metrics for testing."""
        now = datetime.now()
        return [
            {
                "execution_id": "exec-001",
                "pipeline_type": "NEWS",
                "steps": [
                    {"name": "Download", "status": "OK", "duration_ms": 1000, "error": None},
                    {"name": "Process", "status": "OK", "duration_ms": 2000, "error": None},
                ],
                "total_duration_ms": 3000,
                "success": True,
                "error_count": 0,
                "success_count": 2,
                "step_count": 2,
                "created_at": now - timedelta(hours=2),
            },
            {
                "execution_id": "exec-002",
                "pipeline_type": "AUDIO",
                "steps": [
                    {"name": "Download", "status": "OK", "duration_ms": 500, "error": None},
                    {"name": "Transcribe", "status": "FAILED", "duration_ms": 200, "error": "Timeout"},
                ],
                "total_duration_ms": 700,
                "success": False,
                "error_count": 1,
                "success_count": 1,
                "step_count": 2,
                "created_at": now - timedelta(hours=1),
            },
        ]

    def test_get_recent_executions(self, sample_metrics):
        """Get recent executions should return formatted list."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.__getitem__.return_value = mock_collection
        mock_collection.find.return_value.sort.return_value.limit.return_value = sample_metrics

        repo = MongoMetricsRepository(db=mock_db)
        repo._collection = mock_collection

        result = repo.get_recent_executions(
            pipeline_type=PipelineType.NEWS,
            limit=10,
        )

        assert len(result) == 2
        assert result[0]["execution_id"] == "exec-001"
        assert result[0]["status"] == "OK"
        assert result[1]["status"] == "FAILED"

    def test_get_step_breakdown_aggregates_steps(self):
        """Get step breakdown should aggregate by step name."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.__getitem__.return_value = mock_collection

        # Mock aggregation result
        aggregation_result = [
            {
                "name": "Download",
                "avg_duration_ms": 750,
                "success_count": 2,
                "error_count": 0,
                "success_rate": 1.0,
            },
            {
                "name": "Process",
                "avg_duration_ms": 1500,
                "success_count": 1,
                "error_count": 1,
                "success_rate": 0.5,
            },
        ]
        mock_collection.aggregate.return_value = aggregation_result

        repo = MongoMetricsRepository(db=mock_db)
        repo._collection = mock_collection

        result = repo.get_step_breakdown(
            pipeline_type=PipelineType.NEWS,
            start=datetime.now() - timedelta(days=7),
            end=datetime.now(),
        )

        assert len(result) == 2
        assert result[0]["name"] == "Download"
        assert result[0]["avg_duration_ms"] == 750
        assert result[0]["success_rate"] == 1.0

    def test_get_activity_heatmap_returns_grid(self):
        """Get activity heatmap should return 24x7 grid."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.__getitem__.return_value = mock_collection

        # Mock aggregation for heatmap
        aggregation_result = [
            {"_id": {"hour": 9, "day_of_week": 2}, "count": 5},  # Monday 9am
            {"_id": {"hour": 14, "day_of_week": 3}, "count": 8},  # Tuesday 2pm
        ]
        mock_collection.aggregate.return_value = aggregation_result

        repo = MongoMetricsRepository(db=mock_db)
        repo._collection = mock_collection

        result = repo.get_activity_heatmap(
            pipeline_type=PipelineType.NEWS,
            start=datetime.now() - timedelta(days=7),
            end=datetime.now(),
        )

        # Should be 24 hours x 7 days
        assert len(result) == 24
        assert all(len(day) == 7 for day in result)

        # Check that mock data was placed in grid
        # Note: This test assumes specific day_of_week conversion logic
        assert result[9][0] == 5  # 9am on Monday (day 0)
        assert result[14][1] == 8  # 2pm on Tuesday (day 1)

    def test_get_activity_heatmap_handles_empty_data(self):
        """Get activity heatmap should handle case with no executions."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.__getitem__.return_value = mock_collection
        mock_collection.aggregate.return_value = []

        repo = MongoMetricsRepository(db=mock_db)
        repo._collection = mock_collection

        result = repo.get_activity_heatmap(
            pipeline_type=PipelineType.NEWS,
            start=datetime.now() - timedelta(days=7),
            end=datetime.now(),
        )

        # Should return empty grid (all zeros)
        assert len(result) == 24
        assert all(len(day) == 7 for day in result)
        assert all(count == 0 for hour in result for count in hour)

    def test_get_activity_heatmap_handles_error(self):
        """Get activity heatmap should return empty grid on error."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.__getitem__.return_value = mock_collection
        mock_collection.aggregate.side_effect = Exception("DB error")

        repo = MongoMetricsRepository(db=mock_db)
        repo._collection = mock_collection

        result = repo.get_activity_heatmap(
            pipeline_type=PipelineType.NEWS,
            start=datetime.now() - timedelta(days=7),
            end=datetime.now(),
        )

        # Should return empty grid (graceful fallback)
        assert len(result) == 24
        assert all(len(day) == 7 for day in result)
        assert all(count == 0 for hour in result for count in hour)


class TestMongoMetricsRepositoryAggregation:
    """Test aggregation functionality."""

    def test_get_aggregated_daily(self):
        """Test daily aggregation with percentile calculation."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.__getitem__.return_value = mock_collection

        # Mock aggregation result
        aggregation_result = [
            {
                "_id": "2026-05-28",
                "durations": [1000, 1500, 2000, 2500, 3000],
                "count": 5,
                "error_count": 1,
            },
        ]
        mock_collection.aggregate.return_value = aggregation_result

        repo = MongoMetricsRepository(db=mock_db)
        repo._collection = mock_collection

        result = repo.get_aggregated(
            pipeline_type=PipelineType.NEWS,
            period="daily",
            start=datetime.now() - timedelta(days=7),
            end=datetime.now(),
        )

        assert len(result) == 1
        assert result[0]["timestamp"] == "2026-05-28"
        assert result[0]["count"] == 5
        assert result[0]["error_count"] == 1
        assert "p50" in result[0]
        assert "p95" in result[0]
        assert "p99" in result[0]
        assert result[0]["success_rate"] == 0.8  # 4 successful out of 5

    def test_percentile_calculation(self):
        """Test that percentiles are calculated correctly."""
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.__getitem__.return_value = mock_collection

        # Test data: [100, 200, 300, 400, 500] (sorted)
        aggregation_result = [
            {
                "_id": "2026-05-28",
                "durations": [100, 200, 300, 400, 500],
                "count": 5,
                "error_count": 0,
            },
        ]
        mock_collection.aggregate.return_value = aggregation_result

        repo = MongoMetricsRepository(db=mock_db)
        repo._collection = mock_collection

        result = repo.get_aggregated(
            pipeline_type=PipelineType.NEWS,
            period="daily",
        )

        # With 5 elements:
        # p50 @ index 2 (50% of 5 = 2.5) → 300
        # p95 @ index 4 (95% of 5 = 4.75) → 500
        # p99 @ index 4 (99% of 5 = 4.95) → 500
        assert result[0]["p50"] == 300
        assert result[0]["p95"] == 500
        assert result[0]["p99"] == 500
