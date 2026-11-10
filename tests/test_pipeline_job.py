"""Tests for pipeline_job module (B12: InMemoryJobRepository empty dict fix)."""

def test_in_memory_repo_accepts_empty_dict():
    """Empty dict passed to InMemoryJobRepository should be used, not discarded (B12)."""
    from src.news.application.usecases.pipeline_job import InMemoryJobRepository

    custom_store = {}
    repo = InMemoryJobRepository(store=custom_store)

    assert repo.store is custom_store, "Empty dict was discarded!"
    assert repo.store == {}
    assert repo.store is not None

def test_in_memory_repo_none_creates_new_dict():
    """None passed should create a new empty dict (default behavior)."""
    from src.news.application.usecases.pipeline_job import InMemoryJobRepository

    repo = InMemoryJobRepository(store=None)

    assert repo.store == {}
    assert repo.store is not None

def test_in_memory_repo_no_arg_creates_new_dict():
    """No argument should create a new empty dict (default behavior)."""
    from src.news.application.usecases.pipeline_job import InMemoryJobRepository

    repo = InMemoryJobRepository()

    assert repo.store == {}
    assert repo.store is not None

def test_default_repo_uses_global_store():
    """_default_repo should use the global _jobs_store."""
    from src.news.application.usecases.pipeline_job import _default_repo, _jobs_store

    assert _default_repo.store is _jobs_store, "Default repo doesn't use global store!"