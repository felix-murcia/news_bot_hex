"""Unit tests for metrics domain entities.

Tests ProcessingMetric and StepMetric value objects:
- Immutability
- Validation (total_duration >= sum of steps)
- Helper methods (error_count, success_count, step_count)
"""

import pytest
from datetime import datetime
from src.news.domain.entities.processing_metric import (
    ProcessingMetric,
    StepMetric,
    StepStatus,
    PipelineType,
)


class TestStepMetric:
    """Test StepMetric value object."""

    def test_create_ok_step(self):
        """Create a successful step metric."""
        step = StepMetric(
            name="Download",
            status=StepStatus.OK,
            duration_ms=1000,
            error=None,
        )
        assert step.name == "Download"
        assert step.status == StepStatus.OK
        assert step.duration_ms == 1000
        assert step.error is None

    def test_create_failed_step_with_error(self):
        """Create a failed step with error message."""
        step = StepMetric(
            name="Download",
            status=StepStatus.FAILED,
            duration_ms=500,
            error="Connection timeout",
        )
        assert step.status == StepStatus.FAILED
        assert step.error == "Connection timeout"

    def test_step_metric_immutable(self):
        """StepMetric should be immutable (frozen dataclass)."""
        step = StepMetric(
            name="Download",
            status=StepStatus.OK,
            duration_ms=1000,
        )
        with pytest.raises(Exception):  # FrozenInstanceError or similar
            step.name = "Modified"

    def test_step_metric_zero_duration(self):
        """Step metric can have zero duration."""
        step = StepMetric(
            name="Noop",
            status=StepStatus.OK,
            duration_ms=0,
        )
        assert step.duration_ms == 0


class TestProcessingMetric:
    """Test ProcessingMetric value object."""

    @pytest.fixture
    def sample_steps(self):
        """Create sample steps for testing."""
        return [
            StepMetric("Download", StepStatus.OK, 1000),
            StepMetric("Transcribe", StepStatus.OK, 2000),
            StepMetric("Generate", StepStatus.OK, 3000),
        ]

    def test_create_processing_metric_success(self, sample_steps):
        """Create a successful processing metric."""
        metric = ProcessingMetric(
            execution_id="exec-123",
            pipeline_type=PipelineType.NEWS,
            steps=sample_steps,
            total_duration_ms=6000,
            success=True,
            created_at=datetime.now(),
        )
        assert metric.execution_id == "exec-123"
        assert metric.pipeline_type == PipelineType.NEWS
        assert len(metric.steps) == 3
        assert metric.success is True

    def test_create_processing_metric_with_failure(self):
        """Create a metric with a failed step."""
        steps = [
            StepMetric("Download", StepStatus.OK, 1000),
            StepMetric("Transcribe", StepStatus.FAILED, 500, "Timeout"),
        ]
        metric = ProcessingMetric(
            execution_id="exec-456",
            pipeline_type=PipelineType.AUDIO,
            steps=steps,
            total_duration_ms=1500,
            success=False,
            created_at=datetime.now(),
        )
        assert metric.success is False
        assert metric.step_count() == 2
        assert metric.error_count() == 1

    def test_total_duration_validation_exact_match(self, sample_steps):
        """Total duration must be >= sum of step durations."""
        total = sum(s.duration_ms for s in sample_steps)
        metric = ProcessingMetric(
            execution_id="exec-exact",
            pipeline_type=PipelineType.VIDEO,
            steps=sample_steps,
            total_duration_ms=total,
            success=True,
            created_at=datetime.now(),
        )
        assert metric.total_duration_ms == 6000

    def test_total_duration_validation_with_overhead(self, sample_steps):
        """Total duration can be greater than sum of steps (overhead)."""
        metric = ProcessingMetric(
            execution_id="exec-overhead",
            pipeline_type=PipelineType.NEWS,
            steps=sample_steps,
            total_duration_ms=7000,  # 1000ms overhead
            success=True,
            created_at=datetime.now(),
        )
        assert metric.total_duration_ms == 7000

    def test_total_duration_validation_fails_if_less(self, sample_steps):
        """Total duration must not be less than sum of steps."""
        with pytest.raises(ValueError):
            ProcessingMetric(
                execution_id="exec-invalid",
                pipeline_type=PipelineType.NEWS,
                steps=sample_steps,
                total_duration_ms=5000,  # Less than sum (6000)
                success=True,
                created_at=datetime.now(),
            )

    def test_success_count_all_ok(self, sample_steps):
        """Count successful steps."""
        metric = ProcessingMetric(
            execution_id="exec-success",
            pipeline_type=PipelineType.NEWS,
            steps=sample_steps,
            total_duration_ms=6000,
            success=True,
            created_at=datetime.now(),
        )
        assert metric.success_count() == 3

    def test_error_count_with_failures(self):
        """Count failed steps."""
        steps = [
            StepMetric("Step1", StepStatus.OK, 1000),
            StepMetric("Step2", StepStatus.FAILED, 500),
            StepMetric("Step3", StepStatus.OK, 800),
            StepMetric("Step4", StepStatus.FAILED, 200),
        ]
        metric = ProcessingMetric(
            execution_id="exec-errors",
            pipeline_type=PipelineType.AUDIO,
            steps=steps,
            total_duration_ms=2500,
            success=False,
            created_at=datetime.now(),
        )
        assert metric.error_count() == 2
        assert metric.success_count() == 2

    def test_step_count(self, sample_steps):
        """Count total steps."""
        metric = ProcessingMetric(
            execution_id="exec-count",
            pipeline_type=PipelineType.VIDEO,
            steps=sample_steps,
            total_duration_ms=6000,
            success=True,
            created_at=datetime.now(),
        )
        assert metric.step_count() == 3

    def test_step_count_empty_raises(self):
        """ProcessingMetric requires at least one step."""
        with pytest.raises(ValueError):
            ProcessingMetric(
                execution_id="exec-empty",
                pipeline_type=PipelineType.NEWS,
                steps=[],
                total_duration_ms=0,
                success=True,
                created_at=datetime.now(),
            )

    def test_metric_immutable(self, sample_steps):
        """ProcessingMetric should be immutable."""
        metric = ProcessingMetric(
            execution_id="exec-immutable",
            pipeline_type=PipelineType.NEWS,
            steps=sample_steps,
            total_duration_ms=6000,
            success=True,
            created_at=datetime.now(),
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            metric.execution_id = "modified"

    def test_all_pipeline_types(self):
        """Support all pipeline types."""
        for pipeline_type in [PipelineType.NEWS, PipelineType.AUDIO, PipelineType.VIDEO]:
            metric = ProcessingMetric(
                execution_id=f"exec-{pipeline_type.value}",
                pipeline_type=pipeline_type,
                steps=[StepMetric("Test", StepStatus.OK, 100)],
                total_duration_ms=100,
                success=True,
                created_at=datetime.now(),
            )
            assert metric.pipeline_type == pipeline_type

    def test_skipped_steps_not_counted_as_errors(self):
        """SKIPPED steps should not be counted as failures."""
        steps = [
            StepMetric("Step1", StepStatus.OK, 1000),
            StepMetric("Step2", StepStatus.SKIPPED, 0),
            StepMetric("Step3", StepStatus.FAILED, 500),
        ]
        metric = ProcessingMetric(
            execution_id="exec-skipped",
            pipeline_type=PipelineType.NEWS,
            steps=steps,
            total_duration_ms=1500,
            success=False,
            created_at=datetime.now(),
        )
        assert metric.error_count() == 1  # Only FAILED counts
        assert metric.success_count() == 1  # Only OK counts
        # SKIPPED is neither success nor error
