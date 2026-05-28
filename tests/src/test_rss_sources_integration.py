"""Integration tests for RSS sources from appdb.

These tests MUST run against real MongoDB with appdb containing production data.
They validate that:
- RSS sources load from MongoDB (not hardcoded or mocked)
- Sources come from the correct database
- Data structure is valid
- Quantity is sufficient for pipeline execution

These tests FAIL if infrastructure is misconfigured.
"""

import pytest


class TestRSSSourcesFromAppDB:
    """Validate that RSS sources load from real appdb, not mocks or defaults."""

    def test_get_all_sources_returns_real_data(self):
        """RSS sources must load from MongoDB, not mocked data."""
        from src.news.infrastructure.adapters import MongoRSSSourceRepository

        repo = MongoRSSSourceRepository()
        sources = repo.get_all_sources()

        assert sources is not None, "Sources should not be None"
        assert isinstance(sources, list), "Sources should be a list"
        assert len(sources) > 0, (
            "Sources list is empty. Check that appdb has sources_rss collection "
            "with {_id: 'sources', sources: [...]}"
        )

    def test_rss_sources_count_meets_minimum(self):
        """Must have at least 10 RSS sources (currently ~18)."""
        from src.news.infrastructure.adapters import MongoRSSSourceRepository

        repo = MongoRSSSourceRepository()
        sources = repo.get_all_sources()

        assert len(sources) >= 10, (
            f"Insufficient RSS sources. Expected >= 10, Found: {len(sources)}. "
            f"This indicates appdb.sources_rss is not properly initialized. "
            f"Current sources in appdb: {[s.get('source') for s in sources[:5]]}"
        )

    def test_rss_source_structure_is_valid(self):
        """Each source must have required fields."""
        from src.news.infrastructure.adapters import MongoRSSSourceRepository

        repo = MongoRSSSourceRepository()
        sources = repo.get_all_sources()

        assert len(sources) > 0, "Must have sources to validate structure"

        for i, source in enumerate(sources[:3]):  # Check first 3
            assert isinstance(source, dict), f"Source {i} should be a dict"
            assert "source" in source, f"Source {i} missing 'source' field"
            assert "url" in source, f"Source {i} missing 'url' field"
            assert isinstance(source["source"], str), (
                f"Source {i} field 'source' should be string"
            )
            assert isinstance(source["url"], str), f"Source {i} field 'url' should be string"
            assert len(source["source"]) > 0, f"Source {i} name cannot be empty"
            assert len(source["url"]) > 0, f"Source {i} URL cannot be empty"

    def test_rss_sources_are_from_production_appdb(self):
        """Verify sources come from appdb, not test database or hardcoded."""
        from src.news.infrastructure.adapters import MongoRSSSourceRepository
        from config.settings import Settings

        # Verify we're using the correct database
        assert Settings.MONGO_DB_NAME == "appdb", (
            "Tests must use appdb. Check MONGO_DB_NAME environment variable."
        )

        repo = MongoRSSSourceRepository()
        sources = repo.get_all_sources()

        # Get some known sources from appdb
        # (These are the sources we know exist in appdb with real data)
        expected_sources = {
            "BBC World",  # BBC Mundo
            "New York Times",  # Known quality source
            "Reuters",  # Reuters
            "NPR",  # NPR
        }

        actual_sources = {s.get("source") for s in sources}

        # At least SOME of the expected sources should be present
        found = actual_sources.intersection(expected_sources)
        assert len(found) > 0, (
            f"Expected to find sources like {expected_sources} in appdb. "
            f"Found: {sorted(list(actual_sources)[:5])}... "
            f"This suggests sources_rss is not from production appdb."
        )

    def test_no_hardcoded_default_sources_in_production(self):
        """Prevent accidentally using hardcoded DEFAULT_SOURCES."""
        from src.news.infrastructure.adapters import MongoRSSSourceRepository

        repo = MongoRSSSourceRepository()
        sources = repo.get_all_sources()

        # If these sources are present, they came from a hardcoded DEFAULT_SOURCES
        # (These are sources we would never use in production)
        forbidden_sources = {
            "El Mundo",  # Sensationalist source
            "El Español",  # Sensationalist source
            "La Vanguardia",  # Sensationalist source
        }

        actual = {s.get("source") for s in sources}
        forbidden_found = actual.intersection(forbidden_sources)

        assert len(forbidden_found) == 0, (
            f"Found sensationalist sources {forbidden_found}. "
            f"This suggests DEFAULT_SOURCES or hardcoded data was used. "
            f"Sources must come from appdb.sources_rss collection."
        )

    def test_get_source_by_origin(self):
        """Test finding source by origin field."""
        from src.news.infrastructure.adapters import MongoRSSSourceRepository

        repo = MongoRSSSourceRepository()
        sources = repo.get_all_sources()

        if len(sources) == 0:
            pytest.skip("No sources to test retrieval")

        # Get a source with an 'origin' field
        source_with_origin = next((s for s in sources if "origin" in s), None)

        if source_with_origin:
            origin = source_with_origin["origin"]
            found = repo.get_source_by_origin(origin)
            assert found is not None, f"Should find source with origin '{origin}'"
            assert found["origin"] == origin, "Origin should match"

    def test_sources_urls_are_valid_feeds(self):
        """URLs should look like valid RSS feed URLs."""
        from src.news.infrastructure.adapters import MongoRSSSourceRepository

        repo = MongoRSSSourceRepository()
        sources = repo.get_all_sources()

        assert len(sources) > 0, "Must have sources"

        # Check first 5 sources have reasonable URLs
        for source in sources[:5]:
            url = source.get("url")
            assert url.startswith("http"), f"URL should start with http: {url}"
            assert "." in url, f"URL should look like domain: {url}"
            assert len(url) > 10, f"URL seems too short: {url}"

    def test_all_sources_have_non_empty_names_and_urls(self):
        """Validate all sources have valid non-empty fields."""
        from src.news.infrastructure.adapters import MongoRSSSourceRepository

        repo = MongoRSSSourceRepository()
        sources = repo.get_all_sources()

        assert len(sources) > 0, "Must have sources"

        for i, source in enumerate(sources):
            source_name = source.get("source", "").strip()
            url = source.get("url", "").strip()

            assert source_name, f"Source {i} has empty name: {source}"
            assert url, f"Source {i} has empty URL: {source}"
            assert len(source_name) >= 3, f"Source {i} name too short: '{source_name}'"


class TestRSSSourcesRepositoryIntegration:
    """Test repository correctly interfaces with MongoDB."""

    def test_repository_uses_correct_collection(self):
        """RSS repository should use 'sources_rss' collection."""
        from src.news.infrastructure.adapters import MongoRSSSourceRepository

        assert MongoRSSSourceRepository.COLLECTION_NAME == "sources_rss", (
            "Repository should use 'sources_rss' collection"
        )

    def test_repository_finds_sources_document(self):
        """Sources repository should find document with _id: 'sources'."""
        from src.news.infrastructure.adapters import MongoRSSSourceRepository
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        sources_doc = db["sources_rss"].find_one({"_id": "sources"})

        assert sources_doc is not None, (
            "sources_rss collection must have document with _id: 'sources'. "
            "Initialize with: db['sources_rss'].insert_one({_id: 'sources', sources: [...]})"
        )

        assert "sources" in sources_doc, (
            "Document must have 'sources' field containing array of RSS sources"
        )

        assert isinstance(sources_doc["sources"], list), (
            "'sources' field must be a list/array"
        )

    def test_repository_handles_missing_sources(self):
        """Repository should gracefully handle missing sources document."""
        from src.news.infrastructure.adapters import MongoRSSSourceRepository
        from unittest.mock import patch, MagicMock

        # Test behavior when sources document doesn't exist
        mock_db = MagicMock()
        mock_db.__getitem__.return_value.find_one.return_value = None

        repo = MongoRSSSourceRepository(db=mock_db)
        sources = repo.get_all_sources()

        assert sources == [], "Should return empty list if sources document missing"
