"""Pipeline job tracking value objects and enums (domain layer).

This module contains the core domain contracts for pipeline execution:
- JobStatus: lifecycle states including PARTIAL for enrichment failures
- ProcessingStepName: enum of valid pipeline steps with criticality logic
- ProcessingStepStatus: enum of step execution states
- PipelineStepResult: result of a single pipeline step
- PipelineResult: final result of a pipeline execution
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class JobStatus(str, Enum):
    """Job lifecycle states.

    PARTIAL indicates the pipeline completed but some enrichment steps failed.
    FAILED indicates a critical step failed and the pipeline aborted.
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ProcessingStepName(str, Enum):
    """Valid pipeline step names to avoid magic strings."""

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

    def is_critical(self) -> bool:
        """Return True if this step is critical (failure aborts the pipeline).

        Critical steps: RSS fetch, verification, article generation, WordPress/social publish.
        Enrichment steps (posts, images, audio, video): failure continues with PARTIAL.
        """
        return self in {
            ProcessingStepName.RSS_FETCH,
            ProcessingStepName.FULL_VERIFICATION,
            ProcessingStepName.GENERATE_ARTICLES,
            ProcessingStepName.PUBLISH_WORDPRESS,
            ProcessingStepName.PUBLISH_SOCIAL,
        }


class ProcessingStepStatus(str, Enum):
    """Valid step status values."""

    PENDING = "pending"
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class PipelineStepResult:
    """Result of a single pipeline step."""

    name: ProcessingStepName
    status: ProcessingStepStatus
    error: Optional[str] = None
    critical: bool = False


@dataclass(frozen=True)
class PipelineResult:
    """Final result of a pipeline execution."""

    job_id: str
    status: JobStatus
    steps: List[PipelineStepResult]
    error: Optional[str] = None
    failed_steps: List[str] = None

    def __post_init__(self):
        if self.failed_steps is None:
            object.__setattr__(self, 'failed_steps', [])