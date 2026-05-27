"""Pipeline step value object for tracking execution stages."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any


class ProcessingStepName(str, Enum):
    """Valid pipeline step names."""
    INITIALIZING = "Inicializando"
    PROCESSING_URL = "Procesando URL"
    RSS_FETCH = "RSS Fetch"
    FULL_VERIFICATION = "Full Verification"
    GENERATE_POSTS = "Generate Posts"
    GENERATE_ARTICLES = "Generate Articles"
    FETCH_IMAGES = "Fetch Images"
    ENRICH_IMAGES = "Enrich Images"
    GENERATE_AUDIO = "Generate Audio"
    GENERATE_VIDEO = "Generate Video"
    PUBLISH_WORDPRESS = "Publish WordPress"
    PUBLISH_SOCIAL = "Publish Social"
    COMPLETED = "Completado"


class ProcessingStepStatus(str, Enum):
    """Valid step status values."""
    PENDING = "pending"
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class PipelineStep:
    """Value object for a single pipeline execution step."""

    name: ProcessingStepName
    status: ProcessingStepStatus
    timestamp: datetime
    duration_ms: Optional[int] = None
    error: Optional[str] = None

    def mark_running(self) -> "PipelineStep":
        """Transition to RUNNING state."""
        return PipelineStep(
            name=self.name,
            status=ProcessingStepStatus.RUNNING,
            timestamp=datetime.now(),
            duration_ms=None,
            error=None,
        )

    def mark_ok(self, duration_ms: Optional[int] = None) -> "PipelineStep":
        """Transition to OK state."""
        return PipelineStep(
            name=self.name,
            status=ProcessingStepStatus.OK,
            timestamp=self.timestamp,
            duration_ms=duration_ms,
            error=None,
        )

    def mark_error(self, error: str, duration_ms: Optional[int] = None) -> "PipelineStep":
        """Transition to ERROR state."""
        return PipelineStep(
            name=self.name,
            status=ProcessingStepStatus.ERROR,
            timestamp=self.timestamp,
            duration_ms=duration_ms,
            error=error,
        )

    def mark_skipped(self) -> "PipelineStep":
        """Transition to SKIPPED state."""
        return PipelineStep(
            name=self.name,
            status=ProcessingStepStatus.SKIPPED,
            timestamp=self.timestamp,
            duration_ms=None,
            error=None,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "name": self.name.value,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "error": self.error,
        }
