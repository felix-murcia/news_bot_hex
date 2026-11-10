"""B18 — PARTIAL step status semantics in the pipeline executor.

Contract under test: the pipeline distinguishes CRITICAL vs ENRICHMENT steps.
- CRITICAL steps (RSS, verification, posts, articles, WordPress, social): failure aborts, status=FAILED
- ENRICHMENT steps (images, audio, video): failure records ERROR but continues, status=PARTIAL if any enrichment fails

These tests drive ``execute_pipeline_async`` with every collaborator stubbed so
that step 7 (audio) or step 8 (video) raises, then assert on the recorded job
state.
"""

import contextlib
import os
import sys
import time
import types
from unittest.mock import patch

from src.news.application.usecases import pipeline_executor
from src.news.domain.entities.pipeline_job import (
    JobStatus,
    ProcessingStepName,
    ProcessingStepStatus,
)

AUDIO = ProcessingStepName.GENERATE_AUDIO
VIDEO = ProcessingStepName.GENERATE_VIDEO


@contextlib.contextmanager
def _stub_cli_package():
    """Replace ``src.news.entrypoints.cli`` with a stub module.

    The real package transitively imports the social publishers, which raise at
    import time when their credentials are absent. That is a pre-existing
    condition unrelated to the contract under test, so the CLI is
    stubbed out to keep this test focused on step-status semantics.
    """
    fake = types.ModuleType("src.news.entrypoints.cli")
    fake.main_rss = lambda *a, **k: None
    fake.main_full_verify = lambda *a, **k: None
    with patch.dict(sys.modules, {"src.news.entrypoints.cli": fake}):
        yield


class _Boom(RuntimeError):
    pass


class _FakeCollection:
    def __init__(self, docs=None):
        self._docs = docs or []

    def find(self, *a, **k):
        return list(self._docs)

    def update_one(self, *a, **k):
        return None


class _FakeDb(dict):
    """Minimal stand-in for a Mongo database handle."""


@contextlib.contextmanager
def _audio_fails():
    """Steps 1-6 succeed; step 7 (audio) raises. Pipeline should continue to video."""
    with contextlib.ExitStack() as stack:
        stack.enter_context(_stub_cli_package())
        p = lambda *a, **k: stack.enter_context(patch(*a, **k))  # noqa: E731

        p("src.news.application.usecases.content.run_content")
        p("src.news.application.usecases.article.run")
        p("src.shared.infrastructure.composition_root.run_image_unsplash")
        p("src.shared.infrastructure.composition_root.run_image_google")
        p("src.shared.infrastructure.composition_root.run_image_enricher")
        p(
            "src.shared.application.usecases.tts_from_article.run_tts_from_articles",
            side_effect=_Boom("TTS exploded"),
        )
        p(
            "src.shared.adapters.mongo_db.get_database",
            return_value=_FakeDb({"generated_articles": _FakeCollection([{"_id": 1}])}),
        )
        # Patch video, WordPress and social to avoid real DB access
        p(
            "src.shared.infrastructure.composition_root.create_video_generator",
            return_value=types.SimpleNamespace(
                is_available=lambda: True,
                create_video_from_audio=lambda *a, **k: None,
            ),
        )
        p("src.shared.infrastructure.composition_root.run_wordpress")
        p("src.shared.infrastructure.composition_root.run_bluesky")
        p("src.shared.infrastructure.composition_root.run_facebook")
        p("src.shared.infrastructure.composition_root.run_mastodon")
        yield


@contextlib.contextmanager
def _video_fails():
    """Steps 1-7 succeed; step 8 (video) raises. Pipeline should continue to WordPress."""

    class _Gen:
        def is_available(self):
            return True

        def create_video_from_audio(self, audio_path, output_path=None, image=None):
            raise _Boom("ffmpeg died")

    with contextlib.ExitStack() as stack:
        stack.enter_context(_stub_cli_package())
        p = lambda *a, **k: stack.enter_context(patch(*a, **k))  # noqa: E731

        p("src.news.application.usecases.content.run_content")
        p("src.news.application.usecases.article.run")
        p("src.shared.infrastructure.composition_root.run_image_unsplash")
        p("src.shared.infrastructure.composition_root.run_image_google")
        p("src.shared.infrastructure.composition_root.run_image_enricher")
        p("src.shared.application.usecases.tts_from_article.run_tts_from_articles",
          return_value=[])
        p(
            "src.shared.infrastructure.composition_root.create_video_generator",
            return_value=_Gen(),
        )
        p(
            "src.shared.adapters.mongo_db.get_database",
            return_value=_FakeDb({
                "generated_articles": _FakeCollection(
                    [{"_id": 1, "tts_audio_path": os.path.abspath(__file__)}]
                )
            }),
        )
        # Patch WordPress and social to avoid real DB access
        p("src.shared.infrastructure.composition_root.run_wordpress")
        p("src.shared.infrastructure.composition_root.run_bluesky")
        p("src.shared.infrastructure.composition_root.run_facebook")
        p("src.shared.infrastructure.composition_root.run_mastodon")
        yield


def _run_pipeline(job_id):
    """Start the pipeline and wait until its worker thread releases the lock.

    ``execute_pipeline_async`` spawns its own daemon thread and returns
    immediately, so waiting on the call is not enough — the module-level
    ``_execution_lock`` is released in the worker's ``finally``.
    """
    started = pipeline_executor.execute_pipeline_async(job_id)
    assert started, "pipeline rejected: execution lock was still held"

    deadline = time.time() + 60
    while pipeline_executor._execution_lock.locked() and time.time() < deadline:
        time.sleep(0.01)

    assert not pipeline_executor._execution_lock.locked(), (
        "pipeline worker thread did not finish within 60s"
    )


def _capture_steps(job_id, scenario):
    """Run the pipeline recording every (step_name, status) pair."""
    steps = []
    with patch.object(
        pipeline_executor, "add_step",
        side_effect=lambda job, name, status: steps.append((name, status)),
    ), patch.object(pipeline_executor, "update_job_status"), scenario:
        _run_pipeline(job_id)
    return steps


def _terminal_status(steps, step_name):
    terminal = [st for s, st in steps if s == step_name and st != ProcessingStepStatus.RUNNING]
    assert terminal, f"no terminal status recorded for {step_name}; steps={steps}"
    return terminal[-1]


class TestAudioFailureIsEnrichment:
    """Step 7 (audio) failing is ENRICHMENT: records ERROR, continues, final PARTIAL."""

    def test_audio_failure_records_error_status(self):
        steps = _capture_steps("job-audio-1", _audio_fails())
        status = _terminal_status(steps, AUDIO)
        assert status == ProcessingStepStatus.ERROR, (
            f"audio failure must be ERROR, got {status}"
        )

    def test_audio_failure_does_not_record_skipped(self):
        steps = _capture_steps("job-audio-2", _audio_fails())
        status = _terminal_status(steps, AUDIO)
        assert status != ProcessingStepStatus.SKIPPED

    def test_audio_failure_is_logged_as_error_not_warning(self):
        """Enrichment failure logs as error; 'Warning en ...' is wrong."""
        with patch.object(pipeline_executor.logger, "error") as err, \
             patch.object(pipeline_executor.logger, "warning") as warn, \
             _audio_fails():
            _run_pipeline("job-audio-3")

        errors = [str(c.args[0]) for c in err.call_args_list if c.args]
        warnings = [str(c.args[0]) for c in warn.call_args_list if c.args]

        assert any("TTS exploded" in m for m in errors), (
            f"failure not logged via logger.error; errors={errors}"
        )
        assert not any("TTS exploded" in m for m in warnings), (
            f"failure logged as warning: {warnings}"
        )

    def test_audio_failure_continues_to_video_step(self):
        """Enrichment: pipeline continues to video step after audio failure."""
        steps = _capture_steps("job-audio-4", _audio_fails())
        names = [n for n, _ in steps]
        assert VIDEO in names, (
            "pipeline should continue to video step after audio enrichment failure"
        )

    def test_audio_failure_final_status_is_partial(self):
        """Enrichment failure -> final job status PARTIAL."""
        with patch.object(pipeline_executor, "update_job_status") as update_status, \
             _audio_fails():
            _run_pipeline("job-audio-5")

        # Check final update_job_status call
        calls = update_status.call_args_list
        final_call = calls[-1]
        assert final_call[0][1] == JobStatus.PARTIAL, (
            f"final status should be PARTIAL, got {final_call[0][1]}"
        )
        assert "enriquecimiento" in str(final_call[0][2]).lower() or "audio" in str(final_call[0][2]).lower(), (
            f"error message should mention enrichment/audio: {final_call[0][2]}"
        )


class TestVideoFailureIsEnrichment:
    """Step 8 (video) failing is ENRICHMENT: records ERROR, continues, final PARTIAL."""

    def test_video_failure_records_error_status(self):
        steps = _capture_steps("job-video-1", _video_fails())
        status = _terminal_status(steps, VIDEO)
        assert status == ProcessingStepStatus.ERROR, (
            f"video failure must be ERROR, got {status}"
        )

    def test_video_failure_does_not_record_skipped(self):
        steps = _capture_steps("job-video-2", _video_fails())
        status = _terminal_status(steps, VIDEO)
        assert status != ProcessingStepStatus.SKIPPED

    def test_video_failure_is_logged_as_error_not_warning(self):
        """Enrichment failure logs as error via the executor's logger."""
        with patch.object(pipeline_executor.logger, "error") as err, \
             patch.object(pipeline_executor.logger, "warning") as warn, \
             _video_fails():
            _run_pipeline("job-video-3")

        errors = [str(c.args[0]) for c in err.call_args_list if c.args]
        assert any("ffmpeg died" in m for m in errors), (
            f"video failure not logged via logger.error; errors={errors}"
        )

    def test_video_failure_continues_to_wordpress_step(self):
        """Enrichment: pipeline continues to WordPress step after video failure."""
        steps = _capture_steps("job-video-4", _video_fails())
        names = [n for n, _ in steps]
        assert ProcessingStepName.PUBLISH_WORDPRESS in names, (
            "pipeline should continue to WordPress step after video enrichment failure"
        )

    def test_video_failure_final_status_is_partial(self):
        """Enrichment failure -> final job status PARTIAL."""
        with patch.object(pipeline_executor, "update_job_status") as update_status, \
             _video_fails():
            _run_pipeline("job-video-5")

        calls = update_status.call_args_list
        final_call = calls[-1]
        assert final_call[0][1] == JobStatus.PARTIAL, (
            f"final status should be PARTIAL, got {final_call[0][1]}"
        )
        assert "enriquecimiento" in str(final_call[0][2]).lower() or "video" in str(final_call[0][2]).lower(), (
            f"error message should mention enrichment/video: {final_call[0][2]}"
        )


class TestCriticalFailureAborts:
    """Critical step failure aborts pipeline, final status FAILED."""

    def test_rss_failure_aborts_and_fails(self):
        """RSS is critical: failure aborts, no further steps, final FAILED."""
        with contextlib.ExitStack() as stack:
            stack.enter_context(_stub_cli_package())
            p = lambda *a, **k: stack.enter_context(patch(*a, **k))
            p("src.news.entrypoints.cli.main_rss", side_effect=_Boom("RSS exploded"))

            steps = _capture_steps("job-rss-1", contextlib.nullcontext())
            names = [n for n, _ in steps]
            assert ProcessingStepName.FULL_VERIFICATION not in names, (
                "pipeline should abort after RSS failure"
            )

        with patch.object(pipeline_executor, "update_job_status") as update_status, \
             contextlib.ExitStack() as stack:
            stack.enter_context(_stub_cli_package())
            p = lambda *a, **k: stack.enter_context(patch(*a, **k))
            p("src.news.entrypoints.cli.main_rss", side_effect=_Boom("RSS exploded"))
            _run_pipeline("job-rss-2")

            calls = update_status.call_args_list
            final_call = calls[-1]
            assert final_call[0][1] == JobStatus.FAILED