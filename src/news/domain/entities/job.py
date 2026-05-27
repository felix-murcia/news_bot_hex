"""Job value object for pipeline execution tracking."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class JobStatus(str, Enum):
    """Job lifecycle states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    """Value object for pipeline job with immutable state management."""

    id: str
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    message: str = ""
    error: Optional[str] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_log: Optional[str] = None

    def mark_running(self) -> "Job":
        """Transition to RUNNING state."""
        return Job(
            id=self.id,
            status=JobStatus.RUNNING,
            progress=self.progress,
            message="Ejecutando...",
            error=self.error,
            steps=self.steps,
            result=self.result,
            created_at=self.created_at,
            started_at=datetime.now() if not self.started_at else self.started_at,
            completed_at=self.completed_at,
            last_log=self.last_log,
        )

    def mark_completed(self, result: Optional[Dict[str, Any]] = None) -> "Job":
        """Transition to COMPLETED state."""
        return Job(
            id=self.id,
            status=JobStatus.COMPLETED,
            progress=100,
            message="Completado exitosamente",
            error=None,
            steps=self.steps,
            result=result or self.result,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=datetime.now(),
            last_log=self.last_log,
        )

    def mark_failed(self, error: str) -> "Job":
        """Transition to FAILED state."""
        return Job(
            id=self.id,
            status=JobStatus.FAILED,
            progress=self.progress,
            message=f"Error: {error}",
            error=error,
            steps=self.steps,
            result=self.result,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=datetime.now(),
            last_log=self.last_log,
        )

    def add_step(self, step: Dict[str, Any]) -> "Job":
        """Add/update a pipeline step."""
        updated_steps = list(self.steps)
        existing_idx = next(
            (i for i, s in enumerate(updated_steps) if s.get("name") == step.get("name")),
            None
        )

        if existing_idx is not None:
            updated_steps[existing_idx] = step
        else:
            updated_steps.append(step)

        # Recalculate progress
        total = len(updated_steps)
        completed = len([s for s in updated_steps if s.get("status") in ("ok", "OK")])
        progress = int((completed / total * 100)) if total > 0 else 0

        return Job(
            id=self.id,
            status=self.status,
            progress=progress,
            message=self.message,
            error=self.error,
            steps=updated_steps,
            result=self.result,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            last_log=self.last_log,
        )

    def update_log(self, log_message: str) -> "Job":
        """Update last log message."""
        return Job(
            id=self.id,
            status=self.status,
            progress=self.progress,
            message=self.message,
            error=self.error,
            steps=self.steps,
            result=self.result,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            last_log=log_message.strip() if log_message else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/serialization."""
        return {
            "id": self.id,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "steps": self.steps,
            "result": self.result,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "last_log": self.last_log,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Create Job from dictionary."""
        return cls(
            id=data["id"],
            status=JobStatus(data.get("status", "pending")),
            progress=data.get("progress", 0),
            message=data.get("message", ""),
            error=data.get("error"),
            steps=data.get("steps", []),
            result=data.get("result"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            last_log=data.get("last_log"),
        )
