from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Optional, List


class PipelineType(str, Enum):
    """Pipeline execution type."""
    NEWS = "NEWS"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"


class StepStatus(str, Enum):
    """Pipeline step execution status."""
    OK = "OK"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class StepMetric:
    """Value object representing a single pipeline step's execution metrics."""
    name: str
    status: StepStatus
    duration_ms: int
    error: Optional[str] = None

    def __post_init__(self):
        if self.duration_ms < 0:
            raise ValueError(f"duration_ms must be non-negative, got {self.duration_ms}")


@dataclass(frozen=True)
class ProcessingMetric:
    """Value object representing complete pipeline execution metrics."""
    execution_id: str
    pipeline_type: PipelineType
    steps: List[StepMetric]
    total_duration_ms: int
    success: bool
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if self.total_duration_ms < 0:
            raise ValueError(f"total_duration_ms must be non-negative, got {self.total_duration_ms}")

        if not self.steps:
            raise ValueError("ProcessingMetric requires at least one step")

        # Validate total duration >= sum of step durations
        steps_total = sum(step.duration_ms for step in self.steps)
        if self.total_duration_ms < steps_total:
            raise ValueError(
                f"total_duration_ms ({self.total_duration_ms}) cannot be less than "
                f"sum of step durations ({steps_total})"
            )

        # Validate success flag consistency
        step_statuses = {step.status for step in self.steps}
        has_failures = StepStatus.FAILED in step_statuses
        if self.success and has_failures:
            raise ValueError("success=True but steps contain FAILED status")

    def error_count(self) -> int:
        """Count of failed steps."""
        return sum(1 for step in self.steps if step.status == StepStatus.FAILED)

    def success_count(self) -> int:
        """Count of successful steps."""
        return sum(1 for step in self.steps if step.status == StepStatus.OK)

    def step_count(self) -> int:
        """Total number of steps."""
        return len(self.steps)
