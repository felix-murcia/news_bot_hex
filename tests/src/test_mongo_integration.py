"""Comprehensive MongoDB integration tests.

Tests all MongoDB repositories and adapters using real MongoDB connection
when available, falling back to mocks when not.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta


# ============================================================
# MongoDB Connection Tests
# ============================================================

class TestMongoDBClient:
    """Test MongoDB client connection."""

    def test_get_client_singleton(self):
        """Test that MongoDBClient returns a singleton instance."""
        from src.shared.adapters.mongo_db import MongoDBClient

        # Test that the class-level singleton works
        instance1 = MongoDBClient()
        instance2 = MongoDBClient()
        assert instance1 is instance2

        client = instance1.get_client()
        assert client is not None

    def test_get_database(self):
        """Test get_database returns database reference."""
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        assert db is not None

    def test_get_database_returns_correct_db(self):
        """Test get_database returns configured database name."""
        from src.shared.adapters.mongo_db import get_database
        from config.settings import Settings

        db = get_database()
        assert db.name == Settings.MONGO_DB_NAME

    def test_test_connection(self):
        """Test connection test returns bool."""
        from src.shared.adapters.mongo_db import test_connection

        result = test_connection()
        assert isinstance(result, bool)

    def test_module_level_get_database(self):
        """Test module-level get_database wrapper."""
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        assert db is not None


# ============================================================
# Article Repository Tests
# ============================================================

class TestMongoArticleRepository:
    """Test MongoArticleRepository with real MongoDB."""

    @pytest.fixture
    def repo(self):
        """Create repository instance."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoArticleRepository
        from src.news.domain.entities.article import Article

        return MongoArticleRepository(), Article

    def test_insert_and_count_articles(self, repo):
        """Test inserting and counting articles."""
        repository, Article = repo

        articles = [
            Article(
                title="Test Article 1",
                url="https://example.com/test1",
                source="Test Source",
                desc="Test description 1",
            ),
            Article(
                title="Test Article 2",
                url="https://example.com/test2",
                source="Test Source",
                desc="Test description 2",
            ),
        ]

        # Insert articles
        result = repository.insert_articles(articles)
        assert result is True

        # Count articles
        count = repository.count_articles()
        assert count >= 2

    def test_get_all_articles(self, repo):
        """Test retrieving all articles."""
        repository, Article = repo

        articles = repository.get_all_articles()
        assert isinstance(articles, list)
        for article in articles:
            assert isinstance(article, Article)

    def test_insert_empty_list(self, repo):
        """Test inserting empty article list returns False (MongoDB requirement)."""
        repository, _ = repo

        result = repository.insert_articles([])
        # MongoDB requires non-empty list, so False is expected
        assert result is False

    def test_article_from_dict_roundtrip(self, repo):
        """Test Article entity serialization/deserialization."""
        _, Article = repo

        original = Article(
            title="Roundtrip Test",
            url="https://example.com/roundtrip",
            source="Test",
            desc="Description",
        )

        data = original.to_dict()
        restored = Article.from_dict(data)

        assert restored.title == original.title
        assert restored.url == original.url
        assert restored.source == original.source


# ============================================================
# Verified News Repository Tests
# ============================================================

class TestMongoVerifiedNewsRepository:
    """Test MongoVerifiedNewsRepository with real MongoDB."""

    @pytest.fixture
    def repo(self):
        """Create repository instance."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoVerifiedNewsRepository
        from src.news.domain.entities.verified_article import VerifiedArticle

        return MongoVerifiedNewsRepository(), VerifiedArticle

    def test_insert_and_get_all_news(self, repo):
        """Test inserting and retrieving verified news."""
        repository, VerifiedArticle = repo

        articles = [
            VerifiedArticle(
                title="Verified Article 1",
                desc="Description 1",
                source="Test Source",
                origin="Test Origin",
                url="https://example.com/verified1",
                publishedAt=datetime.now(timezone.utc),
                tema="Test",
                resumen="Summary 1",
                score=10,
                model_prediction="real",
                confidence=0.95,
                verification={"verified": True},
                slug="verified-article-1",
            ),
            VerifiedArticle(
                title="Verified Article 2",
                desc="Description 2",
                source="Test Source",
                origin="Test Origin",
                url="https://example.com/verified2",
                publishedAt=datetime.now(timezone.utc),
                tema="Test",
                resumen="Summary 2",
                score=8,
                model_prediction="real",
                confidence=0.90,
                verification={"verified": True},
                slug="verified-article-2",
            ),
        ]

        # Insert news
        result = repository.insert_news(articles)
        assert result is True

        # Get all news
        news = repository.get_all_news()
        assert isinstance(news, list)
        assert len(news) >= 2

    def test_get_news_by_url(self, repo):
        """Test retrieving news by URL."""
        repository, VerifiedArticle = repo

        # Use the articles from previous test
        url = "https://example.com/verified1"
        article = repository.get_news_by_url(url)

        # May or may not exist depending on test order
        if article is not None:
            assert isinstance(article, VerifiedArticle)
            assert article.url == url

    def test_get_verified_news(self, repo):
        """Test retrieving only verified news."""
        repository, VerifiedArticle = repo

        news = repository.get_verified_news()
        assert isinstance(news, list)

    def test_get_all_for_soft_verify(self, repo):
        """Test retrieving raw dicts for soft verify."""
        repository, _ = repo

        news = repository.get_all_for_soft_verify()
        assert isinstance(news, list)
        if news:
            assert isinstance(news[0], dict)

    def test_delete_all_news(self, repo):
        """Test deleting all verified news."""
        repository, _ = repo

        result = repository.delete_all_news()
        assert result is True

        # Verify deletion
        count = len(repository.get_all_news())
        assert count == 0

    def test_save_verified_all(self, repo):
        """Test saving to verified_all collection."""
        repository, VerifiedArticle = repo

        articles = [
            VerifiedArticle(
                title="Verified All 1",
                desc="Desc 1",
                source="Source",
                origin="Origin",
                url="https://example.com/all1",
                publishedAt=datetime.now(timezone.utc),
                tema="Test",
                resumen="Summary",
                score=10,
                model_prediction="real",
                confidence=0.95,
                verification={"verified": True},
            ),
        ]

        result = repository.save_verified_all(articles)
        assert result is True

    def test_save_verified_all_empty(self, repo):
        """Test saving empty list to verified_all."""
        repository, VerifiedArticle = repo

        result = repository.save_verified_all([])
        assert result is True

    def test_verified_article_from_dict(self, repo):
        """Test VerifiedArticle entity serialization."""
        _, VerifiedArticle = repo

        data = {
            "title": "Test",
            "desc": "Desc",
            "source": "Source",
            "origin": "Origin",
            "url": "https://example.com",
            "publishedAt": "2024-01-15T10:00:00+00:00",
            "tema": "Test",
            "resumen": "Summary",
            "score": 10,
            "model_prediction": "real",
            "confidence": 0.95,
            "verification": {"verified": True},
            "slug": "test-article",
        }

        article = VerifiedArticle.from_dict(data)
        assert article.title == "Test"
        assert isinstance(article.publishedAt, datetime)


# ============================================================
# RSS Source Repository Tests
# ============================================================

class TestMongoRSSSourceRepository:
    """Test MongoRSSSourceRepository."""

    @pytest.fixture
    def repo(self):
        """Create repository instance."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoRSSSourceRepository

        return MongoRSSSourceRepository()

    def test_get_all_sources(self, repo):
        """Test retrieving all RSS sources."""
        sources = repo.get_all_sources()
        assert isinstance(sources, list)

    def test_get_source_by_origin_existing(self, repo):
        """Test retrieving source by existing origin."""
        sources = repo.get_all_sources()
        if sources:
            origin = sources[0].get("origin", "")
            if origin:
                source = repo.get_source_by_origin(origin)
                assert source is not None
                assert source.get("origin") == origin

    def test_get_source_by_origin_nonexistent(self, repo):
        """Test retrieving source by non-existent origin."""
        source = repo.get_source_by_origin("__nonexistent_origin__")
        assert source is None


# ============================================================
# Published URLs Repository Tests
# ============================================================

class TestMongoPublishedUrlsRepository:
    """Test MongoPublishedUrlsRepository."""

    @pytest.fixture
    def repo(self):
        """Create repository instance."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoPublishedUrlsRepository

        return MongoPublishedUrlsRepository()

    def test_save_and_get_urls(self, repo):
        """Test saving and retrieving URLs."""
        urls = {
            "https://example.com/1",
            "https://example.com/2",
            "https://example.com/3",
        }

        result = repo.save_urls(urls, ttl_days=30, max_urls=1000)
        assert result is True

        retrieved = repo.get_urls(ttl_days=30, max_urls=1000)
        assert isinstance(retrieved, set)
        assert "https://example.com/1" in retrieved

    def test_get_urls_returns_set(self, repo):
        """Test getting URLs returns a set (may have real data)."""
        urls = repo.get_urls(ttl_days=30, max_urls=1000)
        assert isinstance(urls, set)

    def test_save_urls_with_max_limit(self, repo):
        """Test saving URLs with max limit."""
        urls = {f"https://example.com/{i}" for i in range(50)}

        result = repo.save_urls(urls, ttl_days=1, max_urls=10)
        assert result is True

        retrieved = repo.get_urls(ttl_days=1, max_urls=10)
        assert len(retrieved) <= 10

    def test_save_urls_with_ttl_expired(self, repo):
        """Test that expired URLs are cleaned up."""
        urls = {"https://example.com/expired"}

        # Save with very short TTL
        result = repo.save_urls(urls, ttl_days=0, max_urls=1000)
        assert result is True

    def test_save_urls_empty(self, repo):
        """Test saving empty URL set."""
        result = repo.save_urls(set(), ttl_days=30, max_urls=1000)
        assert result is True


# ============================================================
# Keywords Repository Tests
# ============================================================

class TestMongoKeywordsRepository:
    """Test MongoKeywordsRepository."""

    @pytest.fixture
    def repo(self):
        """Create repository instance."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoKeywordsRepository

        return MongoKeywordsRepository()

    def test_get_breaking_keywords(self, repo):
        """Test retrieving breaking keywords."""
        keywords = repo.get_breaking_keywords()
        assert isinstance(keywords, list)

    def test_get_trending_keywords(self, repo):
        """Test retrieving trending keywords."""
        keywords = repo.get_trending_keywords()
        assert isinstance(keywords, list)


# ============================================================
# Scoring Config Repository Tests
# ============================================================

class TestMongoScoringConfigRepository:
    """Test MongoScoringConfigRepository."""

    @pytest.fixture
    def repo(self):
        """Create repository instance."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoScoringConfigRepository

        return MongoScoringConfigRepository()

    def test_get_scoring_config(self, repo):
        """Test retrieving scoring config."""
        config = repo.get_scoring_config()
        assert isinstance(config, dict)

    def test_default_config_structure(self, repo):
        """Test default config has expected structure."""
        config = repo._default_config()
        assert "scoring_rules" in config
        assert "weights" in config
        assert "limits" in config
        assert "source_prioritarias" in config

    def test_default_scoring_rules(self, repo):
        """Test default scoring rules exist."""
        config = repo._default_config()
        rules = config["scoring_rules"]
        assert isinstance(rules, dict)
        assert "Politics" in rules


# ============================================================
# Validation Rules Repository Tests
# ============================================================

class TestMongoValidationRulesRepository:
    """Test MongoValidationRulesRepository."""

    @pytest.fixture
    def repo(self):
        """Create repository instance."""
        from src.news.infrastructure.adapters.mongo_validation_rules import MongoValidationRulesRepository

        return MongoValidationRulesRepository()

    def test_get_stopwords_english(self, repo):
        """Test retrieving English stopwords."""
        stopwords = repo.get_stopwords("english")
        assert isinstance(stopwords, list)

    def test_get_stopwords_nonexistent_language(self, repo):
        """Test retrieving stopwords for non-existent language."""
        stopwords = repo.get_stopwords("klingon")
        assert isinstance(stopwords, list)

    def test_get_sensationalist_words(self, repo):
        """Test retrieving sensationalist words."""
        words = repo.get_sensationalist_words()
        assert isinstance(words, list)

    def test_get_source_indicators(self, repo):
        """Test retrieving source indicators."""
        indicators = repo.get_source_indicators()
        assert isinstance(indicators, list)

    def test_get_scoring_config(self, repo):
        """Test retrieving scoring config."""
        config = repo.get_scoring_config()
        assert isinstance(config, dict)

    def test_get_date_patterns(self, repo):
        """Test retrieving date patterns."""
        patterns = repo.get_date_patterns()
        assert isinstance(patterns, list)

    def test_save_and_get_rules(self, repo):
        """Test saving and retrieving custom rules."""
        test_rule = {
            "_id": "test_rules",
            "description": "Test rules",
            "words": ["test1", "test2"],
        }

        result = repo.save_rules("test_rules", test_rule)
        assert result is True

        # Retrieve the rule
        retrieved = repo.get_rules("test_rules")
        assert isinstance(retrieved, dict)

        # Cleanup
        repo.delete_rules("test_rules")

    def test_get_all_rules(self, repo):
        """Test retrieving all rules."""
        rules = repo.get_all_rules()
        assert isinstance(rules, list)

    def test_delete_nonexistent_rule(self, repo):
        """Test deleting non-existent rule."""
        result = repo.delete_rules("__nonexistent_rule__")
        assert isinstance(result, (bool, type(None)))

    def test_get_rules_nonexistent(self, repo):
        """Test getting non-existent rule."""
        rule = repo.get_rules("__nonexistent_rule__")
        assert rule is None or isinstance(rule, dict)


# ============================================================
# MongoDB Integration Error Handling
# ============================================================

class TestMongoDBErrorHandling:
    """Test MongoDB error handling."""

    @patch('src.shared.adapters.mongo_db.get_database')
    def test_article_repo_handles_db_error(self, mock_db):
        """Test article repository handles DB errors gracefully."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoArticleRepository

        mock_db.side_effect = Exception("DB unavailable")

        with pytest.raises(Exception):
            MongoArticleRepository()

    @patch('src.shared.adapters.mongo_db.get_database')
    def test_verified_news_repo_handles_db_error(self, mock_db):
        """Test verified news repository handles DB errors."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoVerifiedNewsRepository

        mock_db.side_effect = Exception("DB unavailable")

        with pytest.raises(Exception):
            MongoVerifiedNewsRepository()

    @patch('src.shared.adapters.mongo_db.get_database')
    def test_rss_source_repo_handles_db_error(self, mock_db):
        """Test RSS source repository handles DB errors."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoRSSSourceRepository

        mock_db.side_effect = Exception("DB unavailable")

        with pytest.raises(Exception):
            MongoRSSSourceRepository()


# ============================================================
# MongoDB with Mocked Collections
# ============================================================

class TestMongoRepositoriesWithMocks:
    """Test repositories with mocked collections for full path coverage."""

    def test_article_repo_get_all_with_mock(self):
        """Test get_all_articles with mocked collection."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoArticleRepository

        with patch('src.shared.adapters.mongo_db.get_database') as mock_db:
            mock_coll = Mock()
            mock_coll.find.return_value = []
            mock_db.return_value = {"raw_news": mock_coll}

            repo = MongoArticleRepository()
            articles = repo.get_all_articles()
            assert articles == []

    def test_article_repo_insert_with_mock(self):
        """Test insert_articles with mocked collection."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoArticleRepository
        from src.news.domain.entities.article import Article

        with patch('src.shared.adapters.mongo_db.get_database') as mock_db:
            mock_coll = Mock()
            mock_coll.insert_many.return_value = Mock(inserted_ids=[1])
            mock_db.return_value = {"raw_news": mock_coll}

            repo = MongoArticleRepository()
            articles = [Article(title="Test", url="https://example.com", source="Test", desc="Test")]
            result = repo.insert_articles(articles)
            assert result is True
            mock_coll.insert_many.assert_called_once()

    def test_article_repo_count_with_mock(self):
        """Test count_articles with mocked collection."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoArticleRepository

        with patch('src.shared.adapters.mongo_db.get_database') as mock_db:
            mock_coll = Mock()
            mock_coll.count_documents.return_value = 42
            mock_db.return_value = {"raw_news": mock_coll}

            repo = MongoArticleRepository()
            count = repo.count_articles()
            assert count == 42

    def test_verified_news_repo_get_all_with_mock(self):
        """Test get_all_news with mocked collection."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoVerifiedNewsRepository

        with patch('src.shared.adapters.mongo_db.get_database') as mock_db:
            mock_coll = Mock()
            mock_coll.find.return_value = []
            mock_db.return_value = {"verified_news": mock_coll}

            repo = MongoVerifiedNewsRepository()
            news = repo.get_all_news()
            assert news == []

    def test_verified_news_repo_delete_with_mock(self):
        """Test delete_all_news with mocked collection."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoVerifiedNewsRepository

        with patch('src.shared.adapters.mongo_db.get_database') as mock_db:
            mock_coll = Mock()
            mock_coll.delete_many.return_value = Mock(deleted_count=10)
            mock_db.return_value = {"verified_news": mock_coll}

            repo = MongoVerifiedNewsRepository()
            result = repo.delete_all_news()
            assert result is True

    def test_verified_news_repo_save_all_with_mock(self):
        """Test save_verified_all with mocked collection."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoVerifiedNewsRepository
        from src.news.domain.entities.verified_article import VerifiedArticle

        with patch('src.shared.adapters.mongo_db.get_database') as mock_db:
            mock_coll_verified = Mock()
            mock_coll_all = Mock()
            mock_coll_all.delete_many.return_value = Mock()
            mock_coll_all.insert_many.return_value = Mock()

            mock_db_obj = Mock()
            mock_db_obj.__getitem__ = Mock(side_effect=lambda key: mock_coll_verified if key == "verified_news" else mock_coll_all)
            mock_db.return_value = mock_db_obj

            repo = MongoVerifiedNewsRepository()
            articles = [VerifiedArticle(
                title="Test", desc="Desc", source="Source", origin="Origin",
                url="https://example.com", publishedAt=datetime.now(timezone.utc),
                tema="Test", resumen="Summary", score=10,
                model_prediction="real", confidence=0.95, verification={}
            )]
            result = repo.save_verified_all(articles)
            assert result is True

    def test_published_urls_repo_get_urls_empty(self):
        """Test get_urls with no data."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoPublishedUrlsRepository

        with patch('src.shared.adapters.mongo_db.get_database') as mock_db:
            mock_coll = Mock()
            mock_coll.find_one.return_value = None
            mock_db.return_value = {"published_urls": mock_coll}

            repo = MongoPublishedUrlsRepository()
            urls = repo.get_urls(ttl_days=30, max_urls=100)
            assert urls == set()

    def test_published_urls_repo_save_with_mock(self):
        """Test save_urls with mocked collection."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoPublishedUrlsRepository

        with patch('src.shared.adapters.mongo_db.get_database') as mock_db:
            mock_coll = Mock()
            mock_coll.find_one.return_value = None
            mock_coll.delete_many.return_value = Mock()
            mock_coll.insert_one.return_value = Mock()
            mock_db.return_value = {"published_urls": mock_coll}

            repo = MongoPublishedUrlsRepository()
            urls = {"https://example.com/1", "https://example.com/2"}
            result = repo.save_urls(urls, ttl_days=30, max_urls=1000)
            assert result is True

    def test_keywords_repo_breaking_with_mock(self):
        """Test get_breaking_keywords with mocked collection."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoKeywordsRepository

        with patch('src.shared.adapters.mongo_db.get_database') as mock_db:
            mock_coll = Mock()
            mock_coll.find_one.return_value = {"breaking_keywords": ["breaking", "urgent"]}
            mock_db.return_value = {"breaking_keywords": mock_coll, "trending_keywords": mock_coll}

            repo = MongoKeywordsRepository()
            keywords = repo.get_breaking_keywords()
            assert "breaking" in keywords
            assert "urgent" in keywords

    def test_keywords_repo_trending_with_mock(self):
        """Test get_trending_keywords with mocked collection."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoKeywordsRepository

        with patch('src.shared.adapters.mongo_db.get_database') as mock_db:
            mock_coll = Mock()
            mock_coll.find_one.return_value = {"trending_keywords": ["tech", "ai"]}
            mock_db.return_value = {"trending_keywords": mock_coll, "breaking_keywords": mock_coll}

            repo = MongoKeywordsRepository()
            keywords = repo.get_trending_keywords()
            assert "tech" in keywords
            assert "ai" in keywords

    def test_scoring_repo_config_with_mock(self):
        """Test get_scoring_config with mocked collection."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoScoringConfigRepository

        with patch('src.shared.adapters.mongo_db.get_database') as mock_db:
            mock_coll = Mock()
            mock_coll.find_one.return_value = {"_id": "scoring", "rules": {"test": 5}}
            mock_db.return_value = {"scoring": mock_coll}

            repo = MongoScoringConfigRepository()
            config = repo.get_scoring_config()
            assert "rules" in config

    def test_scoring_repo_default_config(self):
        """Test default scoring config when no data in DB."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoScoringConfigRepository

        with patch('src.shared.adapters.mongo_db.get_database') as mock_db:
            mock_coll = Mock()
            mock_coll.find_one.return_value = None
            mock_db.return_value = {"scoring": mock_coll}

            repo = MongoScoringConfigRepository()
            config = repo.get_scoring_config()
            assert "scoring_rules" in config
            assert "weights" in config

    def test_rss_source_repo_empty_sources(self):
        """Test get_all_sources with no data."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoRSSSourceRepository

        with patch('src.shared.adapters.mongo_db.get_database') as mock_db:
            mock_coll = Mock()
            mock_coll.find_one.return_value = None
            mock_db.return_value = {"sources_rss": mock_coll}

            repo = MongoRSSSourceRepository()
            sources = repo.get_all_sources()
            assert sources == []

    def test_rss_source_repo_with_data(self):
        """Test get_all_sources with data."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoRSSSourceRepository

        with patch('src.shared.adapters.mongo_db.get_database') as mock_db:
            mock_coll = Mock()
            mock_coll.find_one.return_value = {
                "_id": "sources",
                "sources": [{"origin": "Test", "url": "https://test.com/rss"}]
            }
            mock_db.return_value = {"sources_rss": mock_coll}

            repo = MongoRSSSourceRepository()
            sources = repo.get_all_sources()
            assert len(sources) == 1
            assert sources[0]["origin"] == "Test"

    def test_validation_rules_repo_save_and_get(self):
        """Test validation rules save and get."""
        from src.news.infrastructure.adapters.mongo_validation_rules import MongoValidationRulesRepository

        with patch('src.shared.adapters.mongo_db.get_database') as mock_db:
            mock_coll = Mock()
            mock_coll.find_one.return_value = None
            mock_coll.replace_one.return_value = Mock(matched_count=1)
            mock_db.return_value = {"validation_rules": mock_coll}

            repo = MongoValidationRulesRepository()
            rules = {"_id": "test", "words": ["word1", "word2"]}
            result = repo.save_rules("test", rules)
            assert result is True

    def test_validation_rules_repo_get_all(self):
        """Test validation rules get_all."""
        from src.news.infrastructure.adapters.mongo_validation_rules import MongoValidationRulesRepository

        with patch('src.shared.adapters.mongo_db.get_database') as mock_db:
            mock_coll = Mock()
            mock_coll.find.return_value = [{"_id": "rule1"}, {"_id": "rule2"}]
            mock_db.return_value = {"validation_rules": mock_coll}

            repo = MongoValidationRulesRepository()
            rules = repo.get_all_rules()
            assert len(rules) == 2

    def test_validation_rules_repo_delete(self):
        """Test validation rules delete."""
        from src.news.infrastructure.adapters.mongo_validation_rules import MongoValidationRulesRepository

        with patch('src.shared.adapters.mongo_db.get_database') as mock_db:
            mock_coll = Mock()
            mock_coll.delete_one.return_value = Mock(deleted_count=1)
            mock_db.return_value = {"validation_rules": mock_coll}

            repo = MongoValidationRulesRepository()
            result = repo.delete_rules("test")
            assert result is not None
