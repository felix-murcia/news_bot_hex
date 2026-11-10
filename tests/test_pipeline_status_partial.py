"""Tests TDD para B18: estados PARTIAL/FAILED en PipelineResult."""
import pytest
from src.news.application.usecases.pipeline_job import (
    JobStatus,
    PipelineResult,
    PipelineStepResult,
    ProcessingStepName,
    ProcessingStepStatus,
)


class TestPipelineStatusEnum:
    """PARTIAL debe existir en el enum."""

    def test_partial_exists(self):
        assert hasattr(JobStatus, "PARTIAL")
        assert JobStatus.PARTIAL.value == "partial"

    def test_three_states(self):
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.PARTIAL.value == "partial"
        assert JobStatus.FAILED.value == "failed"


class TestPipelineResultContracts:
    """Contratos de PipelineResult con PARTIAL."""

    def test_success_all_ok(self):
        steps = [
            PipelineStepResult(
                name=ProcessingStepName.RSS_FETCH,
                status=ProcessingStepStatus.OK,
                critical=False,
            ),
            PipelineStepResult(
                name=ProcessingStepName.PUBLISH_WORDPRESS,
                status=ProcessingStepStatus.OK,
                critical=True,
            ),
        ]
        result = PipelineResult(job_id="job-1", status=JobStatus.COMPLETED, steps=steps)
        assert result.status == JobStatus.COMPLETED
        assert result.error is None
        assert result.failed_steps == []

    def test_partial_audio_fails(self):
        steps = [
            PipelineStepResult(
                name=ProcessingStepName.RSS_FETCH,
                status=ProcessingStepStatus.OK,
                critical=False,
            ),
            PipelineStepResult(
                name=ProcessingStepName.GENERATE_AUDIO,
                status=ProcessingStepStatus.ERROR,
                error="Connection refused to ffmpeg-api",
                critical=False,
            ),
            PipelineStepResult(
                name=ProcessingStepName.PUBLISH_WORDPRESS,
                status=ProcessingStepStatus.OK,
                critical=True,
            ),
        ]
        result = PipelineResult(
            job_id="job-2",
            status=JobStatus.PARTIAL,
            steps=steps,
            error="Fallo en enriquecimiento: audio",
            failed_steps=["GENERATE_AUDIO"],
        )
        assert result.status == JobStatus.PARTIAL
        assert result.error is not None
        assert "audio" in result.error.lower()
        assert result.failed_steps == ["GENERATE_AUDIO"]

    def test_failed_publish_fails(self):
        steps = [
            PipelineStepResult(
                name=ProcessingStepName.RSS_FETCH,
                status=ProcessingStepStatus.OK,
                critical=False,
            ),
            PipelineStepResult(
                name=ProcessingStepName.GENERATE_AUDIO,
                status=ProcessingStepStatus.ERROR,
                error="Connection refused to ffmpeg-api",
                critical=False,
            ),
            PipelineStepResult(
                name=ProcessingStepName.PUBLISH_WORDPRESS,
                status=ProcessingStepStatus.ERROR,
                error="WordPress auth failed",
                critical=True,
            ),
        ]
        result = PipelineResult(
            job_id="job-3",
            status=JobStatus.FAILED,
            steps=steps,
            error="Fallo crítico: publicación WordPress",
            failed_steps=["GENERATE_AUDIO", "PUBLISH_WORDPRESS"],
        )
        assert result.status == JobStatus.FAILED
        assert result.error is not None
        assert "publicación" in result.error.lower() or "wordpress" in result.error.lower()
        assert set(result.failed_steps) == {"GENERATE_AUDIO", "PUBLISH_WORDPRESS"}


class TestPipelineStepResultCriticalFlag:
    """critical: bool distingue enriquecimiento vs crítico."""

    def test_enrichment_step_not_critical(self):
        step = PipelineStepResult(
            name=ProcessingStepName.GENERATE_AUDIO,
            status=ProcessingStepStatus.OK,
            critical=False,
        )
        assert step.critical is False

    def test_publish_step_critical(self):
        step = PipelineStepResult(
            name=ProcessingStepName.PUBLISH_WORDPRESS,
            status=ProcessingStepStatus.OK,
            critical=True,
        )
        assert step.critical is True