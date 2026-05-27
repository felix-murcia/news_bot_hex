"""End-to-end tests for process_url flow: create job → get status → execute."""

import pytest
from unittest.mock import Mock
from src.news.application.usecases.pipeline_job import (
    InMemoryJobRepository,
    JobStatus,
    ProcessingStepName,
)
from src.news.application.usecases.process_url_executor import ProcessUrlJobCoordinator
from src.news.application.usecases.process_url_with_publishing import (
    ProcessUrlWithPublishingUseCase,
)


class TestProcessUrlE2EFlow:
    """End-to-end flow: create job → execute → fetch status"""

    def test_complete_flow_create_job_execute_fetch_status(self):
        """Full flow: create job, execute processing, fetch status"""
        # Setup
        repo = InMemoryJobRepository()
        mock_processor = Mock(
            return_value={
                "post": "Test article",
                "article_data": {"article": {"title": "Test Title"}},
            }
        )
        mock_publisher = Mock(return_value={"twitter": "ok"})

        usecase = ProcessUrlWithPublishingUseCase(
            content_processor=mock_processor,
            social_publisher=mock_publisher,
            publish_to_social=True,
        )

        coordinator = ProcessUrlJobCoordinator(
            job_repository=repo, process_url_usecase=usecase.execute
        )

        # Step 1: Create job
        job_id = repo.create()
        assert job_id is not None

        # Step 2: Fetch job (before execution)
        job_before = repo.get(job_id)
        assert job_before["status"] == JobStatus.PENDING
        assert len(job_before["steps"]) == 0

        # Step 3: Execute processing
        url = "https://example.com/news"
        coordinator._run_with_tracking(job_id, url)

        # Step 4: Fetch job (after execution)
        job_after = repo.get(job_id)

        # Assertions
        assert job_after["status"] == JobStatus.COMPLETED
        assert job_after["progress"] == 100
        assert len(job_after["steps"]) == 3  # INITIALIZING, PROCESSING_URL, COMPLETED
        assert job_after["steps"][0]["name"] == ProcessingStepName.INITIALIZING
        assert job_after["steps"][1]["name"] == ProcessingStepName.PROCESSING_URL
        assert job_after["steps"][2]["name"] == ProcessingStepName.COMPLETED
        assert job_after["result"]["title"] == "Test Title"
        assert job_after["result"]["post"] == "Test article"
        assert "publish_results" in job_after["result"]

    def test_flow_error_handling(self):
        """Flow with error: create job → execute (fails) → fetch status"""
        # Setup
        repo = InMemoryJobRepository()
        mock_processor = Mock(side_effect=ValueError("URL parsing failed"))

        usecase = ProcessUrlWithPublishingUseCase(
            content_processor=mock_processor, social_publisher=None
        )

        coordinator = ProcessUrlJobCoordinator(
            job_repository=repo, process_url_usecase=usecase.execute
        )

        # Step 1: Create job
        job_id = repo.create()

        # Step 2: Execute (will fail)
        with pytest.raises(ValueError):
            coordinator._run_with_tracking(job_id, "https://invalid.com")

        # Step 3: Fetch job after error
        job = repo.get(job_id)

        # Assertions
        assert job["status"] == JobStatus.FAILED
        assert job["error"] is not None
        assert "URL parsing failed" in job["error"]
        # Error step should be marked
        error_step = next((s for s in job["steps"] if s["name"] == ProcessingStepName.PROCESSING_URL), None)
        assert error_step is not None
        assert error_step["status"] == "error"

    def test_multiple_jobs_independent(self):
        """Multiple jobs should be tracked independently"""
        repo = InMemoryJobRepository()

        # Create 3 jobs
        job_id_1 = repo.create()
        job_id_2 = repo.create()
        job_id_3 = repo.create()

        # Verify they're different
        assert job_id_1 != job_id_2
        assert job_id_2 != job_id_3

        # Update only job_id_2
        repo.update_status(job_id_2, JobStatus.RUNNING, "Processing...")
        repo.add_step(job_id_2, ProcessingStepName.INITIALIZING, "ok")

        # Verify independence
        job_1 = repo.get(job_id_1)
        job_2 = repo.get(job_id_2)
        job_3 = repo.get(job_id_3)

        assert job_1["status"] == JobStatus.PENDING
        assert job_2["status"] == JobStatus.RUNNING
        assert job_3["status"] == JobStatus.PENDING

        assert len(job_1["steps"]) == 0
        assert len(job_2["steps"]) == 1
        assert len(job_3["steps"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
