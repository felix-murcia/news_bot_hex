"""Unit tests for MetricsCollector.

Tests the metrics collection workflow:
- Recording step timings
- Flushing to repository
- Non-blocking error handling
- Total duration calculation
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from src.news.application.usecases.metrics_collector import MetricsCollector
from src.news.domain.entities.processing_metric import (
    PipelineType,
    ProcessingMetric,
)


class TestMetricsCollector:
    """Test MetricsCollector."""

    @pytest.fixture
    def mock_repo(self):
        """Create a mock repository."""
        repo = Mock()
        repo.save = Mock()
        return repo

    def test_create_collector(self, mock_repo):
        """Create metrics collector instance."""
        collector = MetricsCollector(
            execution_id="exec-123",
            pipeline_type=PipelineType.NEWS,
            metrics_repo=mock_repo,
        )
        assert collector.execution_id == "exec-123"
        assert collector.pipeline_type == PipelineType.NEWS

    def test_record_single_step(self, mock_repo):
        """Record a single step metric."""
        collector = MetricsCollector(
            execution_id="exec-single",
            pipeline_type=PipelineType.AUDIO,
            metrics_repo=mock_repo,
        )
        collector.record_step("Download", "OK", 1000)

        assert len(collector.steps) == 1
        assert collector.steps[0]["name"] == "Download"
        assert collector.steps[0]["status"] == "OK"
        assert collector.steps[0]["duration_ms"] == 1000

    def test_record_multiple_steps(self, mock_repo):
        """Record multiple steps in sequence."""
        collector = MetricsCollector(
            execution_id="exec-multi",
            pipeline_type=PipelineType.VIDEO,
            metrics_repo=mock_repo,
        )
        collector.record_step("Download", "OK", 500)
        collector.record_step("Transcribe", "OK", 1500)
        collector.record_step("Generate", "FAILED", 200, "Timeout")

        assert len(collector.steps) == 3
        assert collector.steps[0]["name"] == "Download"
        assert collector.steps[1]["name"] == "Transcribe"
        assert collector.steps[2]["name"] == "Generate"
        assert collector.steps[2]["error"] == "Timeout"

    def test_record_step_with_error(self, mock_repo):
        """Record a failed step with error message."""
        collector = MetricsCollector(
            execution_id="exec-error",
            pipeline_type=PipelineType.NEWS,
            metrics_repo=mock_repo,
        )
        collector.record_step(
            "Download",
            "FAILED",
            300,
            "Connection refused",
        )

        assert collector.steps[0]["status"] == "FAILED"
        assert collector.steps[0]["error"] == "Connection refused"

    def test_flush_saves_to_repo(self, mock_repo):
        """Flush should save metric to repository."""
        collector = MetricsCollector(
            execution_id="exec-flush",
            pipeline_type=PipelineType.AUDIO,
            metrics_repo=mock_repo,
        )
        collector.record_step("Download", "OK", 1000)
        collector.record_step("Transcribe", "OK", 2000)

        collector.flush()

        # Verify save was called once
        mock_repo.save.assert_called_once()

        # Verify the saved metric
        call_args = mock_repo.save.call_args
        metric = call_args[0][0]  # First positional argument

        assert isinstance(metric, ProcessingMetric)
        assert metric.execution_id == "exec-flush"
        assert metric.pipeline_type == PipelineType.AUDIO
        assert len(metric.steps) == 2

    def test_flush_calculates_total_duration(self, mock_repo):
        """Flush should calculate total_duration_ms."""
        collector = MetricsCollector(
            execution_id="exec-duration",
            pipeline_type=PipelineType.NEWS,
            metrics_repo=mock_repo,
        )
        time.sleep(0.1)  # At least 100ms
        collector.record_step("Step1", "OK", 50)
        collector.record_step("Step2", "OK", 75)

        collector.flush()

        call_args = mock_repo.save.call_args
        metric = call_args[0][0]

        # Total duration should be >= sum of steps
        assert metric.total_duration_ms >= 125

    def test_flush_determines_success_status(self, mock_repo):
        """Flush should set success=True only if all steps are OK."""
        # Case 1: All OK
        collector1 = MetricsCollector(
            execution_id="exec-all-ok",
            pipeline_type=PipelineType.NEWS,
            metrics_repo=mock_repo,
        )
        collector1.record_step("Step1", "OK", 100)
        collector1.record_step("Step2", "OK", 100)
        collector1.flush()

        call_args = mock_repo.save.call_args
        metric = call_args[0][0]
        assert metric.success is True

    def test_flush_failure_on_any_failed_step(self, mock_repo):
        """Flush should set success=False if any step failed."""
        collector = MetricsCollector(
            execution_id="exec-with-failure",
            pipeline_type=PipelineType.AUDIO,
            metrics_repo=mock_repo,
        )
        collector.record_step("Step1", "OK", 100)
        collector.record_step("Step2", "FAILED", 50)
        collector.flush()

        call_args = mock_repo.save.call_args
        metric = call_args[0][0]
        assert metric.success is False

    def test_flush_handles_repo_error_gracefully(self, mock_repo):
        """Flush should not raise if repo.save fails."""
        mock_repo.save.side_effect = Exception("DB connection error")

        collector = MetricsCollector(
            execution_id="exec-error",
            pipeline_type=PipelineType.NEWS,
            metrics_repo=mock_repo,
        )
        collector.record_step("Step1", "OK", 100)

        # Should not raise
        collector.flush()

        # But repo.save should have been called (and failed)
        mock_repo.save.assert_called_once()

    def test_flush_with_empty_steps(self, mock_repo):
        """Flush with no recorded steps should still work."""
        collector = MetricsCollector(
            execution_id="exec-empty",
            pipeline_type=PipelineType.NEWS,
            metrics_repo=mock_repo,
        )

        collector.flush()

        call_args = mock_repo.save.call_args
        metric = call_args[0][0]

        assert metric.step_count() == 0
        assert metric.total_duration_ms >= 0

    def test_flush_creates_correct_step_metrics(self, mock_repo):
        """Flush should convert recorded steps to StepMetric objects."""
        collector = MetricsCollector(
            execution_id="exec-steps",
            pipeline_type=PipelineType.VIDEO,
            metrics_repo=mock_repo,
        )
        collector.record_step("Download", "OK", 1000)
        collector.record_step("Process", "FAILED", 500, "Error msg")

        collector.flush()

        call_args = mock_repo.save.call_args
        metric = call_args[0][0]

        assert metric.steps[0].name == "Download"
        assert metric.steps[0].status.value == "OK"
        assert metric.steps[0].duration_ms == 1000

        assert metric.steps[1].name == "Process"
        assert metric.steps[1].status.value == "FAILED"
        assert metric.steps[1].error == "Error msg"

    def test_multiple_flushes(self, mock_repo):
        """Can call flush multiple times (though typically only once)."""
        collector = MetricsCollector(
            execution_id="exec-multi-flush",
            pipeline_type=PipelineType.NEWS,
            metrics_repo=mock_repo,
        )
        collector.record_step("Step1", "OK", 100)

        collector.flush()
        assert mock_repo.save.call_count == 1

        # Record more steps
        collector.record_step("Step2", "OK", 200)
        collector.flush()
        assert mock_repo.save.call_count == 2

    def test_collector_with_none_repo(self):
        """Handle case where metrics_repo is None."""
        collector = MetricsCollector(
            execution_id="exec-no-repo",
            pipeline_type=PipelineType.AUDIO,
            metrics_repo=None,
        )
        collector.record_step("Step1", "OK", 100)

        # Should not raise even though repo is None
        collector.flush()

    def test_step_names_preserved(self, mock_repo):
        """Step names should be exactly as recorded."""
        collector = MetricsCollector(
            execution_id="exec-names",
            pipeline_type=PipelineType.NEWS,
            metrics_repo=mock_repo,
        )
        step_names = [
            "Download and Verify",
            "Generate Article",
            "Enrich Images",
            "Publish WordPress",
        ]
        for name in step_names:
            collector.record_step(name, "OK", 100)

        collector.flush()

        call_args = mock_repo.save.call_args
        metric = call_args[0][0]

        recorded_names = [s.name for s in metric.steps]
        assert recorded_names == step_names
