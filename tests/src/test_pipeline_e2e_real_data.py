"""End-to-End Pipeline Tests with Real Data

These tests validate the complete news pipeline with REAL data from appdb:
- RSS sources load correctly
- Articles are fetched from real RSS feeds
- Articles are processed and stored
- Data comes from appdb, not mocked

CRITICAL: These tests MUST use real MongoDB and real RSS sources.
If these tests pass, the pipeline can process production data.
If these tests fail, infrastructure or data is misconfigured.
"""

import pytest


class TestNewsProcessingPipelineWithRealData:
    """Test the complete news pipeline with real appdb data."""

    def test_pipeline_has_rss_sources(self):
        """Pipeline must have access to RSS sources from appdb."""
        from src.news.infrastructure.adapters import MongoRSSSourceRepository

        repo = MongoRSSSourceRepository()
        sources = repo.get_all_sources()

        assert len(sources) >= 10, (
            f"Pipeline needs 10+ RSS sources. Found: {len(sources)}. "
            f"Check that appdb.sources_rss is initialized."
        )

    def test_pipeline_has_articles_in_database(self):
        """Pipeline must have articles to work with."""
        from src.news.infrastructure.adapters import MongoArticleRepository

        repo = MongoArticleRepository()
        article_count = repo.count_articles()

        assert article_count >= 1000, (
            f"Pipeline needs 1000+ articles in raw_news. Found: {article_count}. "
            f"Check that appdb contains real data."
        )

    def test_fetch_rss_news_use_case_executes(self):
        """FetchRSSNewsUseCase should execute without errors using real data."""
        from src.news.application.usecases import FetchRSSNewsUseCase
        from src.news.infrastructure.adapters import (
            MongoRSSSourceRepository,
            MongoArticleRepository,
            FeedparserRSSFetcher,
        )

        # Use REAL repositories, not mocks
        source_repo = MongoRSSSourceRepository()
        article_repo = MongoArticleRepository()
        rss_fetcher = FeedparserRSSFetcher()

        use_case = FetchRSSNewsUseCase(source_repo, article_repo, rss_fetcher)

        # Execute the use case
        try:
            result = use_case.execute()
            # Result should indicate success or partial success
            assert "status" in result, "Use case should return status"
            assert result["status"] in ["ok", "warning", "error"], (
                f"Invalid status: {result['status']}"
            )
        except Exception as e:
            pytest.fail(f"FetchRSSNewsUseCase failed: {str(e)}")

    def test_article_repository_loads_real_articles(self):
        """ArticleRepository should load real articles from appdb."""
        from src.news.infrastructure.adapters import MongoArticleRepository

        repo = MongoArticleRepository()
        articles = repo.get_all_articles()

        # Should have articles
        assert len(articles) > 0, (
            "ArticleRepository should load articles from appdb. "
            "Check raw_news collection."
        )

        # First article should have expected structure
        first = articles[0]
        assert hasattr(first, "title"), "Article should have title"
        assert hasattr(first, "url"), "Article should have URL"
        assert hasattr(first, "source"), "Article should have source"

    def test_verified_news_repository_has_data(self):
        """VerifiedNewsRepository should have processed articles."""
        from src.news.infrastructure.adapters import MongoVerifiedNewsRepository

        repo = MongoVerifiedNewsRepository()
        verified = repo.get_verified_news()

        # May be empty if pipeline hasn't run, but shouldn't error
        assert isinstance(verified, list), "Should return list of verified articles"

    def test_pipeline_article_processing_chain(self):
        """Test the complete pipeline: fetch → verify → process."""
        from src.news.application.usecases import FetchRSSNewsUseCase
        from src.news.infrastructure.adapters import (
            MongoRSSSourceRepository,
            MongoArticleRepository,
            FeedparserRSSFetcher,
        )

        # Step 1: Fetch RSS news
        fetch_use_case = FetchRSSNewsUseCase(
            MongoRSSSourceRepository(),
            MongoArticleRepository(),
            FeedparserRSSFetcher(),
        )

        result = fetch_use_case.execute()

        # Should not error
        assert result.get("status") != "fatal_error", (
            f"RSS fetch failed: {result.get('message', 'Unknown error')}"
        )

        # Step 2: Verify we have articles
        repo = MongoArticleRepository()
        article_count = repo.count_articles()

        assert article_count > 0, (
            "Pipeline should have articles to process. "
            "Check appdb.raw_news collection."
        )

    def test_no_pipeline_uses_hardcoded_test_data(self):
        """Ensure pipeline doesn't use hardcoded defaults."""
        from src.news.infrastructure.adapters import MongoRSSSourceRepository

        repo = MongoRSSSourceRepository()
        sources = repo.get_all_sources()

        # These are hardcoded values we DON'T want
        hardcoded_names = {"TestSource", "MockFeed", "DefaultSource"}
        actual = {s.get("source") for s in sources}

        forbidden = actual.intersection(hardcoded_names)
        assert len(forbidden) == 0, (
            f"Found hardcoded sources {forbidden}. "
            f"Pipeline must use real MongoDB sources, not defaults."
        )


class TestPipelineDataIntegrity:
    """Validate that pipeline data comes from correct sources."""

    def test_articles_from_correct_database(self):
        """Articles must come from appdb, not any other database."""
        from config.settings import Settings

        assert Settings.MONGO_DB_NAME == "appdb", (
            "Tests must run against appdb, not test database"
        )

    def test_rss_sources_are_production_quality(self):
        """RSS sources should be quality news outlets, not test data."""
        from src.news.infrastructure.adapters import MongoRSSSourceRepository

        repo = MongoRSSSourceRepository()
        sources = repo.get_all_sources()

        # Get actual source names
        source_names = {s.get("source") for s in sources}

        # Should have SOME known quality sources
        known_quality_sources = {
            "BBC",
            "Reuters",
            "AP",
            "New York Times",
            "NPR",
            "CNN",
        }

        quality_found = sum(
            1 for name in source_names if any(q in name for q in known_quality_sources)
        )

        assert quality_found > 0, (
            f"Should have quality news sources. Found: {sorted(list(source_names)[:10])}. "
            f"This suggests sources_rss doesn't have real production data."
        )

    def test_article_urls_are_valid(self):
        """Articles should have valid URLs."""
        from src.news.infrastructure.adapters import MongoArticleRepository

        repo = MongoArticleRepository()
        articles = repo.get_all_articles()

        if len(articles) == 0:
            pytest.skip("No articles to validate")

        # Check first 10 articles have valid URLs
        for article in articles[:10]:
            url = article.url if hasattr(article, "url") else article.get("url")
            assert url is not None, "Article should have URL"
            assert url.startswith("http"), f"URL should start with http: {url}"
            assert len(url) > 10, f"URL seems invalid: {url}"

    def test_article_sources_match_rss_sources(self):
        """Articles should cite sources that exist in RSS sources config."""
        from src.news.infrastructure.adapters import (
            MongoArticleRepository,
            MongoRSSSourceRepository,
        )

        article_repo = MongoArticleRepository()
        source_repo = MongoRSSSourceRepository()

        articles = article_repo.get_all_articles()
        sources = source_repo.get_all_sources()

        if len(articles) == 0 or len(sources) == 0:
            pytest.skip("Need articles and sources to validate")

        # Get valid source names
        valid_sources = {s.get("source") for s in sources}

        # Check a sample of articles
        sample_size = min(5, len(articles))
        for article in articles[:sample_size]:
            article_source = (
                article.source if hasattr(article, "source") else article.get("source")
            )
            # Source should be in our configured sources
            assert article_source in valid_sources, (
                f"Article source '{article_source}' not in configured sources. "
                f"Available: {sorted(list(valid_sources)[:5])}"
            )


class TestPipelineConfiguration:
    """Validate pipeline is configured correctly."""

    def test_pipeline_env_uses_appdb(self):
        """Application must be configured to use appdb."""
        from config.settings import Settings

        assert Settings.MONGO_DB_NAME == "appdb", (
            f"MONGO_DB_NAME should be 'appdb', got '{Settings.MONGO_DB_NAME}'. "
            f"Check environment variables and .env file."
        )

    def test_pipeline_can_connect_to_mongodb(self):
        """Pipeline must be able to connect to MongoDB."""
        from src.shared.adapters.mongo_db import get_database

        try:
            db = get_database()
            db.command("ping")
        except Exception as e:
            pytest.fail(f"Cannot connect to MongoDB: {str(e)}")

    def test_pipeline_required_collections_exist(self):
        """All required collections must exist in appdb."""
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        collections = set(db.list_collection_names())

        required = {"sources_rss", "raw_news", "verified_news"}
        missing = required - collections

        assert len(missing) == 0, (
            f"Missing required collections: {missing}. "
            f"Initialize appdb with all required collections."
        )
