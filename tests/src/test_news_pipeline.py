import pytest
import sys
import os

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


class TestNewsPipelineImports:
    """Test that all news pipeline modules can be imported correctly."""

    def test_import_news_entrypoint(self):
        """Test that news CLI entrypoint imports correctly."""
        from src.news.entrypoints.cli import (
            main_rss,
            main_verify,
            main_full_verify,
            main_verifier,
            main_soft,
            main_article,
            main_content,
            main_news_to_news,
            main_bluesky,
            main_facebook,
            main_mastodon,
            main_wordpress,
        )

        assert callable(main_rss)
        assert callable(main_verify)
        assert callable(main_full_verify)
        assert callable(main_verifier)
        assert callable(main_soft)
        assert callable(main_article)
        assert callable(main_content)
        assert callable(main_news_to_news)
        assert callable(main_bluesky)
        assert callable(main_facebook)
        assert callable(main_mastodon)
        assert callable(main_wordpress)

    def test_import_news_domain(self):
        """Test that news domain modules import correctly."""
        from src.news.domain.entities.article import Article
        from src.news.domain.entities.verified_article import VerifiedArticle
        from src.news.domain.ports import (
            RSSSourceRepository,
            ArticleRepository,
            RSSFetcher,
            VerifiedNewsRepository,
        )

        assert Article is not None
        assert VerifiedArticle is not None
        assert RSSSourceRepository is not None
        assert ArticleRepository is not None

    def test_import_news_usecases(self):
        """Test that news use cases import correctly."""
        from src.news.application.usecases import (
            FetchRSSNewsUseCase,
            VerifyNewsUseCase,
            FullVerifyNewsUseCase,
        )
        from src.news.application.usecases.soft_verify import SoftVerifyUseCase
        from src.news.application.usecases.article_from_news import run_from_news
        from src.news.application.usecases.article import (
            run as run_article_gemini,
        )
        from src.news.application.usecases.content import (
            run_content as run_content_gemini,
        )
        from src.news.application.usecases.news_to_news import process_news_url

        assert FetchRSSNewsUseCase is not None
        assert VerifyNewsUseCase is not None
        assert FullVerifyNewsUseCase is not None
        assert SoftVerifyUseCase is not None
        assert callable(run_from_news)
        assert callable(run_article_gemini)
        assert callable(run_content_gemini)
        assert callable(process_news_url)

    def test_import_news_adapters(self):
        """Test that news infrastructure adapters import correctly."""
        from src.news.infrastructure.adapters import (
            MongoRSSSourceRepository,
            MongoArticleRepository,
            FeedparserRSSFetcher,
            MongoVerifiedNewsRepository,
            MongoPublishedUrlsRepository,
            MongoKeywordsRepository,
        )

        assert MongoRSSSourceRepository is not None
        assert MongoArticleRepository is not None
        assert FeedparserRSSFetcher is not None
        assert MongoVerifiedNewsRepository is not None


class TestSharedAdaptersImports:
    """Test that shared adapters import correctly."""

    def test_import_mongo_db(self):
        """Test MongoDB adapter imports."""
        from src.shared.adapters.mongo_db import (
            get_database,
            test_connection,
            MongoDBClient,
        )

        assert get_database is not None
        assert test_connection is not None
        assert MongoDBClient is not None

    def test_import_translator(self):
        """Test translator adapter imports."""
        from src.shared.adapters.translator import translate_text

        assert callable(translate_text)

    def test_import_cache_manager(self):
        """Test cache manager imports."""
        from src.shared.adapters.cache_manager import (
            save_content_to_cache,
            load_content_from_cache,
            clear_old_cache,
        )

        assert callable(save_content_to_cache)
        assert callable(load_content_from_cache)
        assert callable(clear_old_cache)

    def test_import_bluesky_publisher(self):
        """Test Bluesky publisher imports."""
        from src.shared.adapters.bluesky_publisher import (
            BlueskyPublisher,
            run as run_bluesky,
        )

        assert BlueskyPublisher is not None
        assert callable(run_bluesky)

    def test_import_facebook_publisher(self):
        """Test Facebook publisher imports."""
        from src.shared.adapters.facebook_publisher import (
            FacebookPublisher,
            run as run_facebook,
        )

        assert FacebookPublisher is not None
        assert callable(run_facebook)

    def test_import_mastodon_publisher(self):
        """Test Mastodon publisher imports."""
        from src.shared.adapters.mastodon_publisher import (
            MastodonPublisher,
            run as run_mastodon,
        )

        assert MastodonPublisher is not None
        assert callable(run_mastodon)

    def test_import_wordpress_publisher(self):
        """Test WordPress publisher imports."""
        from src.shared.adapters.wordpress_publisher import (
            WordPressPublisher,
            run as run_wordpress,
        )

        assert WordPressPublisher is not None
        assert callable(run_wordpress)


class TestArticleEntity:
    """Test Article entity functionality."""

    def test_article_creation(self):
        """Test Article entity creation and methods."""
        from src.news.domain.entities.article import Article
        from datetime import datetime

        article = Article(
            title="Test Title",
            url="https://example.com",
            source="TestSource",
            desc="Test description",
            published_at=datetime.now(),
            origin="RSS",
            published=False,
            filtered=True,
        )

        assert article.title == "Test Title"
        assert article.url == "https://example.com"
        assert article.source == "TestSource"
        assert article.published == False

        data = article.to_dict()
        assert data["title"] == "Test Title"
        assert data["url"] == "https://example.com"

    def test_article_from_dict(self):
        """Test Article creation from dictionary."""
        from src.news.domain.entities.article import Article

        data = {
            "title": "Dict Title",
            "url": "https://example.com",
            "source": "DictSource",
            "desc": "Dict description",
            "origin": "RSS",
        }

        article = Article.from_dict(data)
        assert article.title == "Dict Title"
        assert article.url == "https://example.com"


class TestVerifiedArticleEntity:
    """Test VerifiedArticle entity functionality."""

    def test_verified_article_creation(self):
        """Test VerifiedArticle entity creation."""
        from src.news.domain.entities.verified_article import VerifiedArticle
        from datetime import datetime

        article = VerifiedArticle(
            title="Verified Title",
            desc="Verified description",
            source="VerifiedSource",
            origin="Verified",
            url="https://example.com",
            publishedAt=datetime.now(),
            tema="Technology",
            resumen="Summary",
            score=10,
            model_prediction="real",
            confidence=0.95,
            verification={"verified": True},
        )

        assert article.title == "Verified Title"
        assert article.score == 10
        assert article.model_prediction == "real"
        assert article.confidence == 0.95

    def test_verified_article_to_dict(self):
        """Test VerifiedArticle to_dict method."""
        from src.news.domain.entities.verified_article import VerifiedArticle
        from datetime import datetime

        article = VerifiedArticle(
            title="Test",
            desc="Test",
            source="Test",
            origin="Test",
            url="https://test.com",
            publishedAt=datetime.now(),
            tema="Test",
            resumen="Test",
            score=5,
            model_prediction="real",
            confidence=0.9,
            verification={"verified": True},
        )

        data = article.to_dict()
        assert data["title"] == "Test"
        assert data["score"] == 5
        assert data["verification"]["verified"] == True


class TestPortsInterfaces:
    """Test that port interfaces are correctly defined."""

    def test_rss_source_repository_is_abstract(self):
        """Test RSSSourceRepository is abstract."""
        from src.news.domain.ports import RSSSourceRepository

        assert RSSSourceRepository.__abstractmethods__

    def test_article_repository_is_abstract(self):
        """Test ArticleRepository is abstract."""
        from src.news.domain.ports import ArticleRepository

        assert ArticleRepository.__abstractmethods__

    def test_rss_fetcher_is_abstract(self):
        """Test RSSFetcher is abstract."""
        from src.news.domain.ports import RSSFetcher

        assert RSSFetcher.__abstractmethods__

    def test_verified_news_repository_is_abstract(self):
        """Test VerifiedNewsRepository is abstract."""
        from src.news.domain.ports import VerifiedNewsRepository

        assert VerifiedNewsRepository.__abstractmethods__
