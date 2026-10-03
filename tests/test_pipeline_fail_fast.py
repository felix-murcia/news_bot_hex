"""B14 — fail-fast step status semantics in the pipeline executor.

Contract under test (T4): the pipeline is **fail-fast**. When a step raises,
the step must be recorded as ``ERROR`` / ``FAILED`` and the job must abort.
Recording the step as ``SKIPPED`` is wrong: SKIPPED means "intentionally not
executed" (e.g. ``video_gen.is_available()`` is False), never "attempted and
failed".

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
from src.news.application.usecases.pipeline_job import (
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
    condition unrelated to the fail-fast contract under test, so the CLI is
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
    """Steps 1-6 succeed; step 7 (audio) raises."""
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
        yield


@contextlib.contextmanager
def _video_fails():
    """Steps 1-7 succeed; step 8 (video) raises."""

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


class TestAudioFailureIsErrorNotSkipped:
    """Step 7 (audio) failing must be ERROR, not SKIPPED."""

    def test_audio_failure_records_error_status(self):
        steps = _capture_steps("job-audio-1", _audio_fails())
        status = _terminal_status(steps, AUDIO)
        assert status == ProcessingStepStatus.ERROR, (
            f"audio failure must be ERROR under fail-fast, got {status}"
        )

    def test_audio_failure_does_not_record_skipped(self):
        steps = _capture_steps("job-audio-2", _audio_fails())
        status = _terminal_status(steps, AUDIO)
        assert status != ProcessingStepStatus.SKIPPED

    def test_audio_failure_is_logged_as_error_not_warning(self):
        """Fail-fast logs a failure as error; 'Warning en ...' is wrong."""
        with patch.object(pipeline_executor, "add_step"), \
             patch.object(pipeline_executor, "update_job_status"), \
             patch.object(pipeline_executor.logger, "error") as err, \
             patch.object(pipeline_executor.logger, "warning") as warn, \
             _audio_fails():
            _run_pipeline("job-audio-3")

        errors = [str(c.args[0]) for c in err.call_args_list if c.args]
        warnings = [str(c.args[0]) for c in warn.call_args_list if c.args]

        assert any("TTS exploded" in m for m in errors), (
            f"failure not logged via logger.error; errors={errors}"
        )
        assert not any("TTS exploded" in m for m in warnings), (
            f"failure logged as warning under fail-fast: {warnings}"
        )

    def test_audio_failure_aborts_before_video_step(self):
        """Fail-fast: the pipeline must not reach the video step."""
        steps = _capture_steps("job-audio-4", _audio_fails())
        names = [n for n, _ in steps]
        assert VIDEO not in names, (
            "pipeline continued to the video step after an audio failure"
        )


class TestVideoFailureIsErrorNotSkipped:
    """Step 8 (video) failing must be ERROR, not SKIPPED."""

    def test_video_failure_records_error_status(self):
        steps = _capture_steps("job-video-1", _video_fails())
        status = _terminal_status(steps, VIDEO)
        assert status == ProcessingStepStatus.ERROR, (
            f"video failure must be ERROR under fail-fast, got {status}"
        )

    def test_video_failure_does_not_record_skipped(self):
        steps = _capture_steps("job-video-2", _video_fails())
        status = _terminal_status(steps, VIDEO)
        assert status != ProcessingStepStatus.SKIPPED

    def test_video_failure_is_logged_as_error_not_warning(self):
        with patch.object(pipeline_executor, "add_step"), \
             patch.object(pipeline_executor, "update_job_status"), \
             patch.object(pipeline_executor.logger, "error") as err, \
             patch.object(pipeline_executor.logger, "warning") as warn, \
             _video_fails():
            _run_pipeline("job-video-3")

        errors = [str(c.args[0]) for c in err.call_args_list if c.args]
        assert any("ffmpeg died" in m for m in errors), (
            f"video failure not logged via logger.error; errors={errors}"
        )