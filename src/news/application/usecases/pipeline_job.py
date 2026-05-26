"""Pipeline job tracking for async execution."""

import uuid
import time
from typing import Dict, Optional
from datetime import datetime
from enum import Enum

# In-memory job store (en producción usar Redis o DB)
_jobs_store: Dict[str, Dict] = {}


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


def create_job() -> str:
    """Create a new pipeline job and return its ID."""
    job_id = str(uuid.uuid4())
    _jobs_store[job_id] = {
        "id": job_id,
        "status": JobStatus.PENDING,
        "progress": 0,
        "message": "Job creado",
        "steps": [],
        "last_log": None,  # Última línea de log para feedback en tiempo real
        "created_at": datetime.utcnow().isoformat(),
        "started_at": None,
        "completed_at": None,
        "error": None,
    }
    return job_id


def get_job(job_id: str) -> Optional[Dict]:
    """Get job status and progress."""
    return _jobs_store.get(job_id)


def update_job_status(job_id: str, status: JobStatus, message: str = "", error: str = None) -> None:
    """Update job status."""
    if job_id not in _jobs_store:
        return

    job = _jobs_store[job_id]
    job["status"] = status
    if message:
        job["message"] = message
    if error:
        job["error"] = error

    if status == JobStatus.RUNNING and not job["started_at"]:
        job["started_at"] = datetime.utcnow().isoformat()
    elif status in (JobStatus.COMPLETED, JobStatus.FAILED):
        job["completed_at"] = datetime.utcnow().isoformat()


def add_step(job_id: str, step_name: str, status: str = "running") -> None:
    """Add/update a pipeline step."""
    if job_id not in _jobs_store:
        return

    job = _jobs_store[job_id]
    step = {
        "name": step_name,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Actualizar si el paso ya existe, sino agregar
    existing = next((s for s in job["steps"] if s["name"] == step_name), None)
    if existing:
        existing.update(step)
    else:
        job["steps"].append(step)

    # Actualizar progreso
    total_steps = len(job["steps"])
    completed = len([s for s in job["steps"] if s["status"] in ("completed", "ok")])
    job["progress"] = int((completed / total_steps * 100)) if total_steps > 0 else 0


def update_job_log(job_id: str, log_message: str) -> None:
    """Update the last log message for real-time feedback in UI."""
    if job_id not in _jobs_store:
        return

    job = _jobs_store[job_id]
    # Extraer solo la parte importante del mensaje de log
    # Eliminar timestamps, prefijos de logger, etc.
    log_text = str(log_message).strip()
    job["last_log"] = log_text


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
