"""Pipeline job tracking for async execution."""

import uuid
import time
from typing import Dict, Optional, Protocol
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod

# In-memory job store (en producción usar Redis o DB)
_jobs_store: Dict[str, Dict] = {}


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStepName(str, Enum):
    """Valid pipeline step names to avoid magic strings"""
    INITIALIZING = "Inicializando"
    PROCESSING_URL = "Procesando URL"
    COMPLETED = "Completado"


class ProcessingStepStatus(str, Enum):
    """Valid step status values"""
    PENDING = "pending"
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"
    SKIPPED = "skipped"


class JobRepositoryPort(ABC):
    """Port (abstraction) for job persistence - decouple from _jobs_store"""

    @abstractmethod
    def create(self) -> str:
        """Create job, return job_id"""
        pass

    @abstractmethod
    def get(self, job_id: str) -> Optional[Dict]:
        """Get job by ID"""
        pass

    @abstractmethod
    def update_status(self, job_id: str, status: JobStatus, message: str = "", error: str = None) -> None:
        """Update job status"""
        pass

    @abstractmethod
    def add_step(self, job_id: str, step_name: str, status: str = "running") -> None:
        """Add/update step"""
        pass

    @abstractmethod
    def update_log(self, job_id: str, log_message: str) -> None:
        """Update last log message"""
        pass


class InMemoryJobRepository(JobRepositoryPort):
    """Adapter: in-memory job storage (implementation of JobRepositoryPort)"""

    def __init__(self, store: Dict[str, Dict] = None):
        self.store = store or {}

    def create(self) -> str:
        job_id = str(uuid.uuid4())
        self.store[job_id] = {
            "id": job_id,
            "status": JobStatus.PENDING,
            "progress": 0,
            "message": "Job creado",
            "steps": [],
            "last_log": None,
            "created_at": datetime.utcnow().isoformat(),
            "started_at": None,
            "completed_at": None,
            "error": None,
        }
        return job_id

    def get(self, job_id: str) -> Optional[Dict]:
        return self.store.get(job_id)

    def update_status(self, job_id: str, status: JobStatus, message: str = "", error: str = None) -> None:
        if job_id not in self.store:
            return

        job = self.store[job_id]
        job["status"] = status
        if message:
            job["message"] = message
        if error:
            job["error"] = error

        if status == JobStatus.RUNNING and not job["started_at"]:
            job["started_at"] = datetime.utcnow().isoformat()
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED):
            job["completed_at"] = datetime.utcnow().isoformat()

    def add_step(self, job_id: str, step_name: str, status: str = "running") -> None:
        if job_id not in self.store:
            return

        job = self.store[job_id]
        step = {
            "name": step_name,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
        }

        existing = next((s for s in job["steps"] if s["name"] == step_name), None)
        if existing:
            existing.update(step)
        else:
            job["steps"].append(step)

        total_steps = len(job["steps"])
        completed = len([s for s in job["steps"] if s["status"] in (ProcessingStepStatus.OK, "ok")])
        job["progress"] = int((completed / total_steps * 100)) if total_steps > 0 else 0

    def update_log(self, job_id: str, log_message: str) -> None:
        if job_id not in self.store:
            return

        job = self.store[job_id]
        log_text = str(log_message).strip()
        job["last_log"] = log_text


# Global singleton repository instance (shared across all requests)
_default_repo = InMemoryJobRepository(_jobs_store)


def create_job() -> str:
    """Create a new pipeline job and return its ID."""
    return _default_repo.create()


def get_job(job_id: str) -> Optional[Dict]:
    """Get job status and progress."""
    return _default_repo.get(job_id)


def update_job_status(job_id: str, status: JobStatus, message: str = "", error: str = None) -> None:
    """Update job status."""
    _default_repo.update_status(job_id, status, message, error)


def add_step(job_id: str, step_name: str, status: str = "running") -> None:
    """Add/update a pipeline step."""
    _default_repo.add_step(job_id, step_name, status)


def update_job_log(job_id: str, log_message: str) -> None:
    """Update the last log message for real-time feedback in UI."""
    _default_repo.update_log(job_id, log_message)


def cleanup_old_jobs(hours: int = 24) -> None:
    """Remove completed jobs older than specified hours."""
    cutoff = time.time() - (hours * 3600)
    jobs_to_delete = []

    for job_id, job in _jobs_store.items():
        if job["completed_at"]:
            completed_ts = datetime.fromisoformat(job["completed_at"]).timestamp()
            if completed_ts < cutoff:
                jobs_to_delete.append(job_id)

    for job_id in jobs_to_delete:
        del _jobs_store[job_id]
