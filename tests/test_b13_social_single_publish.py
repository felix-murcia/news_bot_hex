"""B13-fix: pipelines must publish social via facade only (no direct run_* calls)."""

import inspect


def test_pipeline_runner_does_not_call_social_run_functions_directly():
    from src.news.application.usecases import pipeline_runner

    source = inspect.getsource(pipeline_runner)
    assert "run_facebook" not in source
    assert "run_bluesky" not in source
    assert "run_mastodon" not in source
    assert "publish_all" in source


def test_process_url_pipeline_does_not_call_social_run_functions_directly():
    from src.news.application.usecases import process_url_pipeline

    source = inspect.getsource(process_url_pipeline)
    assert "run_facebook" not in source
    assert "run_bluesky" not in source
    assert "run_mastodon" not in source
    assert "publish_all" in source


def test_social_facade_has_publish_all():
    from src.shared.adapters.publishers.social import SocialMediaPublisher

    assert hasattr(SocialMediaPublisher, "publish_all")
    assert callable(SocialMediaPublisher.publish_all)
