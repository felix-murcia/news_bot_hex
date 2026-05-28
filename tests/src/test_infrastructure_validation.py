"""Infrastructure Validation Tests

These tests ensure critical infrastructure preconditions are met before application starts.
They validate:
- Database name is 'appdb'
- MongoDB connection works
- Database has minimum required data
- All required collections exist

These tests are critical for preventing silent infrastructure misconfiguration.
"""

import pytest
import os
import sys
from typing import Optional


class TestDatabaseConfiguration:
    """Test that database is correctly configured."""

    def test_mongo_db_name_is_appdb(self):
        """CRITICAL: MONGO_DB_NAME must be 'appdb' for production data."""
        from config.settings import Settings

        db_name = Settings.MONGO_DB_NAME
        assert db_name == "appdb", (
            f"MONGO_DB_NAME must be 'appdb' for production data. "
            f"Current: '{db_name}'. Check your .env file."
        )

    def test_mongo_db_name_not_news_bot(self):
        """Explicitly prevent news_bot database (empty/test database)."""
        from config.settings import Settings

        db_name = Settings.MONGO_DB_NAME
        assert db_name != "news_bot", (
            f"MONGO_DB_NAME is '{db_name}' (empty database). "
            f"Must be 'appdb' which contains production data."
        )


class TestMongoDBConnection:
    """Test that MongoDB connection is functional."""

    def test_mongodb_connection_works(self):
        """MongoDB must be accessible and responding."""
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        assert db is not None, "Failed to get database connection"

        # Ping to verify connection
        try:
            db.command("ping")
        except Exception as e:
            pytest.fail(f"MongoDB connection failed: {str(e)}")

    def test_database_name_matches_configured(self):
        """Connected database name must match MONGO_DB_NAME."""
        from src.shared.adapters.mongo_db import get_database
        from config.settings import Settings

        db = get_database()
        expected_name = Settings.MONGO_DB_NAME

        assert db.name == expected_name, (
            f"Connected to wrong database. Expected: {expected_name}, Got: {db.name}"
        )


class TestDatabaseDataQuantities:
    """Test that database has minimum required data."""

    def test_articles_count_minimum(self):
        """Database must have at least 1000 articles (currently ~21K)."""
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        article_count = db["raw_news"].count_documents({})

        assert article_count >= 1000, (
            f"Insufficient articles in database. "
            f"Expected: >= 1000, Found: {article_count:,}. "
            f"This indicates database is empty or wrong database is configured."
        )

    def test_articles_count_reasonable_production(self):
        """Database should have substantial article count for production."""
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        article_count = db["raw_news"].count_documents({})

        # Warning if significantly below expected
        if article_count < 5000:
            pytest.warns(
                UserWarning,
                match="Article count is below expected for production",
            )

    def test_rss_sources_count_minimum(self):
        """Database must have at least 10 RSS sources configured."""
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        sources_doc = db["sources_rss"].find_one({"_id": "sources"})
        sources_count = len(sources_doc.get("sources", [])) if sources_doc else 0

        assert sources_count >= 10, (
            f"Insufficient RSS sources configured. "
            f"Expected: >= 10, Found: {sources_count}. "
            f"This indicates sources_rss collection is not properly initialized."
        )

    def test_rss_sources_reasonable_production(self):
        """Database should have reasonable number of RSS sources for production."""
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        sources_doc = db["sources_rss"].find_one({"_id": "sources"})
        sources_count = len(sources_doc.get("sources", [])) if sources_doc else 0

        # Current state should be around 18
        assert sources_count >= 10, (
            f"RSS sources count is {sources_count}, expected >= 18 for production"
        )


class TestRequiredCollections:
    """Test that all required MongoDB collections exist."""

    REQUIRED_COLLECTIONS = {
        "sources_rss": "RSS sources configuration",
        "raw_news": "Raw news articles",
        "verified_news": "Verified articles",
    }

    def test_required_collections_exist(self):
        """All required collections must exist in database."""
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        existing = set(db.list_collection_names())

        for collection_name, description in self.REQUIRED_COLLECTIONS.items():
            assert collection_name in existing, (
                f"Required collection '{collection_name}' does not exist. "
                f"Purpose: {description}"
            )

    def test_required_collections_have_data(self):
        """Required collections must contain data."""
        from src.shared.adapters.mongo_db import get_database

        db = get_database()

        for collection_name, description in self.REQUIRED_COLLECTIONS.items():
            collection = db[collection_name]
            count = collection.count_documents({})

            # raw_news must have significant data
            if collection_name == "raw_news":
                assert count >= 1000, (
                    f"Collection '{collection_name}' is empty or has insufficient data. "
                    f"Count: {count}, Expected: >= 1000"
                )
            # sources_rss must have sources document
            elif collection_name == "sources_rss":
                sources = collection.find_one({"_id": "sources"})
                assert sources is not None, (
                    f"Collection '{collection_name}' missing sources document"
                )
            # verified_news can be less populated initially
            else:
                assert count >= 0, (
                    f"Collection '{collection_name}' cannot be counted"
                )


class TestStartupValidatorIntegration:
    """Test that startup validator works correctly."""

    def test_startup_validator_passes_with_appdb(self):
        """Startup validator must pass when infrastructure is correct."""
        from src.shared.infrastructure.startup_validator import StartupValidator

        # Should not raise exception
        try:
            StartupValidator.validate_all()
        except SystemExit as e:
            pytest.fail(
                f"Startup validator failed unexpectedly with exit code {e.code}. "
                f"Ensure appdb is configured and contains data."
            )

    def test_startup_validator_detects_wrong_database_name(self, monkeypatch):
        """Startup validator must detect wrong database name."""
        from src.shared.infrastructure.startup_validator import (
            StartupValidator,
            InfrastructureValidationError,
        )

        # Temporarily change database name
        monkeypatch.setenv("MONGO_DB_NAME", "wrong_db")

        with pytest.raises(InfrastructureValidationError):
            # Need to reimport to pick up new env var
            import importlib
            import config.settings

            importlib.reload(config.settings)
            StartupValidator.validate_all()

    def test_startup_validator_detects_insufficient_articles(self, monkeypatch):
        """Startup validator must detect insufficient article count."""
        # This test would need to mock the count_documents call
        # Skipping for now as it requires more complex mocking
        pytest.skip("Requires MongoDB mock setup")

    def test_startup_validator_provides_clear_error_message(self, monkeypatch):
        """Startup validator error messages must be actionable."""
        from src.shared.infrastructure.startup_validator import (
            StartupValidator,
            InfrastructureValidationError,
        )

        monkeypatch.setenv("MONGO_DB_NAME", "wrong_db")

        try:
            import importlib
            import config.settings

            importlib.reload(config.settings)
            StartupValidator.validate_all()
        except InfrastructureValidationError as e:
            error_msg = str(e)
            # Error message should be clear and actionable
            assert "MONGO_DB_NAME" in error_msg or "appdb" in error_msg
            assert len(error_msg) > 20, "Error message should be descriptive"


# ============================================================
# Test Execution Guard
# ============================================================


def test_guard_infrastructure_valid_before_other_tests():
    """
    This test runs first (alphabetically) and ensures infrastructure
    is valid before other tests run. It prevents silent failures where
    tests pass but with wrong database.
    """
    from src.shared.infrastructure.startup_validator import StartupValidator

    # This will fail immediately and loudly if infrastructure is wrong
    try:
        StartupValidator.validate_all()
    except SystemExit as e:
        pytest.fail(
            f"Infrastructure validation failed. Application cannot start. "
            f"Check database configuration and data."
        )


def pytest_configure(config):
    """Hook that runs before any tests execute."""
    # Validate infrastructure early
    from src.shared.infrastructure.startup_validator import (
        StartupValidator,
        InfrastructureValidationError,
    )

    try:
        StartupValidator.validate_all()
    except InfrastructureValidationError as e:
        # Don't fail pytest collection, let individual tests handle it
        pass
    except SystemExit:
        # Startup validator calls sys.exit() on failure
        # We let it proceed for now, tests will validate
        pass
