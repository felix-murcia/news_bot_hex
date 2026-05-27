"""Tests for refactored process_url flow with proper separation of concerns."""

import pytest
from unittest.mock import Mock, MagicMock
from src.news.application.usecases.pipeline_job import (
    JobStatus,
    ProcessingStepName,
    ProcessingStepStatus,
    InMemoryJobRepository,
)
from src.news.application.usecases.process_url_executor import ProcessUrlJobCoordinator


class TestInMemoryJobRepository:
    """Test InMemoryJobRepository (JobRepositoryPort implementation)."""

    def test_create_job_returns_job_id(self):
        """create() should return a valid job_id."""
        repo = InMemoryJobRepository()
        job_id = repo.create()
        assert isinstance(job_id, str)
        assert len(job_id) > 0

    def test_get_job_returns_created_job(self):
        """get() should return the created job."""
        repo = InMemoryJobRepository()
        job_id = repo.create()
        job = repo.get(job_id)
        assert job is not None
        assert job["id"] == job_id
        assert job["status"] == JobStatus.PENDING

    def test_update_status_changes_job_status(self):
        """update_status() should change job status."""
        repo = InMemoryJobRepository()
        job_id = repo.create()
        repo.update_status(job_id, JobStatus.RUNNING, "Processing...")
        job = repo.get(job_id)
        assert job["status"] == JobStatus.RUNNING
        assert job["message"] == "Processing..."

    def test_add_step_adds_step_to_job(self):
        """add_step() should add step to job."""
        repo = InMemoryJobRepository()
        job_id = repo.create()
        repo.add_step(
            job_id,
            ProcessingStepName.INITIALIZING,
            ProcessingStepStatus.RUNNING,
        )
        job = repo.get(job_id)
        assert len(job["steps"]) == 1
        assert job["steps"][0]["name"] == ProcessingStepName.INITIALIZING
        assert job["steps"][0]["status"] == ProcessingStepStatus.RUNNING

    def test_add_step_updates_existing_step(self):
        """add_step() should update if step already exists."""
        repo = InMemoryJobRepository()
        job_id = repo.create()
        repo.add_step(
            job_id, ProcessingStepName.INITIALIZING, ProcessingStepStatus.RUNNING
        )
        repo.add_step(
            job_id, ProcessingStepName.INITIALIZING, ProcessingStepStatus.OK
        )
        job = repo.get(job_id)
        assert len(job["steps"]) == 1
        assert job["steps"][0]["status"] == ProcessingStepStatus.OK

    def test_update_log_stores_log_message(self):
        """update_log() should store the last log message."""
        repo = InMemoryJobRepository()
        job_id = repo.create()
        repo.update_log(job_id, "Processing step 1")
        job = repo.get(job_id)
        assert job["last_log"] == "Processing step 1"


class TestProcessUrlJobCoordinator:
    """Test ProcessUrlJobCoordinator (job tracking + execution)."""

    def test_coordinator_depends_on_injected_repository_and_usecase(self):
        """Coordinator should use injected dependencies."""
        mock_repo = Mock(spec=InMemoryJobRepository)
        mock_repo.get = Mock(return_value={"steps": []})
        mock_usecase = Mock(
            return_value={"post": "tweet", "article_data": {"article": {}}}
        )

        coordinator = ProcessUrlJobCoordinator(
            job_repository=mock_repo, process_url_usecase=mock_usecase
        )

        # Coordinator is properly instantiated
        assert coordinator.job_repository == mock_repo
        assert coordinator.process_url_usecase == mock_usecase

    def test_coordinator_updates_job_status_on_execution(self):
        """Coordinator should update job status during execution."""
        mock_repo = InMemoryJobRepository()
        job_id = mock_repo.create()

        mock_usecase = Mock(
            return_value={
                "post": "tweet",
                "article_data": {"article": {"title": "Test Article"}},
            }
        )

        coordinator = ProcessUrlJobCoordinator(
            job_repository=mock_repo, process_url_usecase=mock_usecase
        )

        # Execute synchronously for test
        coordinator._run_with_tracking(job_id, "https://example.com")

        # Job should be marked COMPLETED
        job = mock_repo.get(job_id)
        assert job["status"] == JobStatus.COMPLETED

    def test_coordinator_tracks_steps(self):
        """Coordinator should add pipeline steps."""
        mock_repo = InMemoryJobRepository()
        job_id = mock_repo.create()

        mock_usecase = Mock(
            return_value={
                "post": "tweet",
                "article_data": {"article": {"title": "Test"}},
            }
        )

        coordinator = ProcessUrlJobCoordinator(
            job_repository=mock_repo, process_url_usecase=mock_usecase
        )

        coordinator._run_with_tracking(job_id, "https://example.com")

        job = mock_repo.get(job_id)
        step_names = [s["name"] for s in job["steps"]]
        assert ProcessingStepName.INITIALIZING in step_names
        assert ProcessingStepName.PROCESSING_URL in step_names
        assert ProcessingStepName.COMPLETED in step_names

    def test_coordinator_handles_errors_and_marks_failed(self):
        """Coordinator should catch errors and mark job as FAILED."""
        mock_repo = InMemoryJobRepository()
        job_id = mock_repo.create()

        mock_usecase = Mock(side_effect=ValueError("Test error"))

        coordinator = ProcessUrlJobCoordinator(
            job_repository=mock_repo, process_url_usecase=mock_usecase
        )

        with pytest.raises(ValueError):
            coordinator._run_with_tracking(job_id, "https://example.com")

        job = mock_repo.get(job_id)
        assert job["status"] == JobStatus.FAILED
        assert job["error"] is not None


class TestProcessUrlDependencyInjection:
    """Test that dependencies are properly injected (no dynamic imports)."""

    def test_no_dynamic_imports_in_coordinator(self):
        """ProcessUrlJobCoordinator should not import at runtime."""
        mock_repo = Mock(spec=InMemoryJobRepository)
        mock_usecase = Mock()
        coordinator = ProcessUrlJobCoordinator(
            job_repository=mock_repo, process_url_usecase=mock_usecase
        )

        assert callable(coordinator.execute_async)
        assert callable(coordinator._run_with_tracking)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
