import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


class TestFetchRSSNewsUseCase:
    """Test FetchRSSNewsUseCase functionality."""

    def test_fetch_rss_news_use_case_init(self):
        """Test FetchRSSNewsUseCase initialization."""
        from src.news.application.usecases import FetchRSSNewsUseCase
        from src.news.infrastructure.adapters import (
            MongoRSSSourceRepository,
            MongoArticleRepository,
            FeedparserRSSFetcher,
        )

        source_repo = MongoRSSSourceRepository()
        article_repo = MongoArticleRepository()
        rss_fetcher = FeedparserRSSFetcher()

        use_case = FetchRSSNewsUseCase(source_repo, article_repo, rss_fetcher)

        assert use_case._source_repo is not None
        assert use_case._article_repo is not None
        assert use_case._rss_fetcher is not None

    @patch("src.news.infrastructure.adapters.MongoRSSSourceRepository.get_all_sources")
    @patch("src.news.infrastructure.adapters.MongoArticleRepository.get_all_articles")
    @patch("src.news.infrastructure.adapters.MongoArticleRepository.insert_articles")
    @patch("src.news.infrastructure.adapters.MongoArticleRepository.count_articles")
    def test_fetch_rss_news_with_no_sources(
        self, mock_count, mock_insert, mock_get_articles, mock_get_sources
    ):
        """Test FetchRSSNewsUseCase when no sources available."""
        from src.news.application.usecases import FetchRSSNewsUseCase
        from src.news.infrastructure.adapters import (
            MongoRSSSourceRepository,
            MongoArticleRepository,
            FeedparserRSSFetcher,
        )

        mock_get_sources.return_value = []
        mock_count.return_value = 0

        use_case = FetchRSSNewsUseCase(
            MongoRSSSourceRepository(), MongoArticleRepository(), FeedparserRSSFetcher()
        )

        result = use_case.execute()

        assert result["status"] == "error"
        assert "No se encontraron fuentes RSS" in result["message"]


class TestVerifyNewsUseCase:
    """Test VerifyNewsUseCase functionality."""

    def test_verify_news_use_case_init(self):
        """Test VerifyNewsUseCase initialization."""
        from src.news.application.usecases import VerifyNewsUseCase
        from src.news.infrastructure.adapters import MongoVerifiedNewsRepository

        verified_repo = MongoVerifiedNewsRepository()
        use_case = VerifyNewsUseCase(verified_repo)

        assert use_case._verified_repo is not None


class TestFullVerifyNewsUseCase:
    """Test FullVerifyNewsUseCase functionality."""

    def test_full_verify_news_use_case_init(self):
        """Test FullVerifyNewsUseCase initialization."""
        from src.news.application.usecases import FullVerifyNewsUseCase
        from src.news.infrastructure.adapters import (
            MongoArticleRepository,
            MongoVerifiedNewsRepository,
            MongoPublishedUrlsRepository,
            MongoKeywordsRepository,
            MongoScoringConfigRepository,
        )

        use_case = FullVerifyNewsUseCase(
            article_repo=MongoArticleRepository(),
            verified_repo=MongoVerifiedNewsRepository(),
            published_urls_repo=MongoPublishedUrlsRepository(),
            keywords_repo=MongoKeywordsRepository(),
            scoring_config_repo=MongoScoringConfigRepository(),
        )

        assert use_case._article_repo is not None
        assert use_case._verified_repo is not None
        assert use_case._published_urls_repo is not None
        assert use_case._keywords_repo is not None
        assert use_case._scoring_config_repo is not None


class TestSoftVerifyUseCase:
    """Test SoftVerifyUseCase functionality."""

    def test_soft_verify_use_case_init(self):
        """Test SoftVerifyUseCase initialization."""
        from src.news.application.usecases.soft_verify import SoftVerifyUseCase
        from src.news.infrastructure.adapters import (
            MongoVerifiedNewsRepository,
            MongoPublishedUrlsRepository,
            JinaContentExtractor,
        )

        use_case = SoftVerifyUseCase(
            verified_repo=MongoVerifiedNewsRepository(),
            published_urls_repo=MongoPublishedUrlsRepository(),
            content_extractor=JinaContentExtractor(),
        )

        assert use_case._verified_repo is not None
        assert use_case._published_urls_repo is not None


class TestArticleFromNewsUseCase:
    """Test ArticleFromNewsUseCase functionality."""

    def test_article_from_news_init(self):
        """Test ArticleFromNewsUseCase initialization."""
        from src.news.application.usecases.article_from_news import (
            ArticleFromNewsUseCase,
        )

        use_case = ArticleFromNewsUseCase(use_gemini=True)

        assert use_case.use_gemini == True

    def test_article_from_news_with_gemini_disabled(self):
        """Test ArticleFromNewsUseCase with Gemini disabled."""
        from src.news.application.usecases.article_from_news import (
            ArticleFromNewsUseCase,
        )

        use_case = ArticleFromNewsUseCase(use_gemini=False)

        assert use_case.use_gemini == False


class TestContentGeminiUseCase:
    """Test ContentGeminiUseCase functionality."""

    def test_content_gemini_init(self):
        """Test ContentGeminiUseCase initialization."""
        from src.news.application.usecases.content_gemini import ContentGeminiUseCase

        use_case = ContentGeminiUseCase(
            network="bluesky",
            use_gemini=True,
            mode="news",
        )

        assert use_case.network == "bluesky"
        assert use_case.mode == "news"

    def test_post_limits(self):
        """Test POST_LIMITS constant."""
        from src.news.application.usecases.content_gemini import POST_LIMITS

        assert POST_LIMITS["bluesky"] == 300
        assert POST_LIMITS["twitter"] == 280


class TestNewsToNewsUseCase:
    """Test NewsToNewsUseCase functionality."""

    def test_news_to_news_init(self):
        """Test NewsToNewsUseCase initialization."""
        from src.news.application.usecases.news_to_news import NewsToNewsUseCase

        use_case = NewsToNewsUseCase(use_gemini=True)

        assert use_case.use_gemini == True

    def test_news_to_news_with_gemini_disabled(self):
        """Test NewsToNewsUseCase with Gemini disabled."""
        from src.news.application.usecases.news_to_news import NewsToNewsUseCase

        use_case = NewsToNewsUseCase(use_gemini=False)

        assert use_case.use_gemini == False


class TestArticleGeminiUseCase:
    """Test ArticleGeminiUseCase functionality."""

    def test_article_gemini_init(self):
        """Test ArticleGeminiUseCase initialization."""
        from src.news.application.usecases.article_gemini import ArticleGeminiUseCase

        use_case = ArticleGeminiUseCase(use_gemini=True)

        assert use_case is not None

    def test_slugify(self):
        """Test slugify function."""
        from src.news.application.usecases.article_gemini import slugify

        assert slugify("Test Title") == "test-title"
        assert slugify("Test Multiple Spaces") == "test-multiple-spaces"


class TestPublisherClasses:
    """Test publisher classes."""

    def test_bluesky_publisher_init(self):
        """Test BlueskyPublisher initialization."""
        from src.shared.adapters.bluesky_publisher import BlueskyPublisher

        publisher = BlueskyPublisher()

        assert publisher._client is None

    def test_facebook_publisher_init(self):
        """Test FacebookPublisher initialization."""
        from src.shared.adapters.facebook_publisher import FacebookPublisher

        publisher = FacebookPublisher()

        assert publisher is not None

    def test_mastodon_publisher_init(self):
        """Test MastodonPublisher initialization."""
        from src.shared.adapters.mastodon_publisher import MastodonPublisher

        publisher = MastodonPublisher()

        assert publisher is not None

    def test_wordpress_publisher_init(self):
        """Test WordPressPublisher initialization."""
        from src.shared.adapters.wordpress_publisher import WordPressPublisher

        publisher = WordPressPublisher()

        assert publisher is not None


class TestUtilityFunctions:
    """Test utility functions."""

    def test_parse_date_flexible(self):
        """Test parse_date_flexible function."""
        from src.news.infrastructure.adapters import parse_date_flexible
        from datetime import datetime

        result = parse_date_flexible("2024-01-01")
        assert result is not None
        assert isinstance(result, datetime)

    def test_parse_date_flexible_with_none(self):
        """Test parse_date_flexible with None input."""
        from src.news.infrastructure.adapters import parse_date_flexible

        result = parse_date_flexible(None)
        assert result is None

    def test_is_today_or_yesterday(self):
        """Test is_today_or_yesterday function."""
        from src.news.infrastructure.adapters import is_today_or_yesterday
        from datetime import datetime, timedelta

        now = datetime.now()
        assert is_today_or_yesterday(now) == True

        yesterday = datetime.now() - timedelta(days=1)
        assert is_today_or_yesterday(yesterday) == True

        old = datetime.now() - timedelta(days=10)
        assert is_today_or_yesterday(old) == False

    def test_compute_score(self):
        """Test compute_score function."""
        from src.news.infrastructure.adapters import compute_score

        scoring_rules = {"Technology": 5, "Noticias": 3}
        source_prioritarias = set()
        trending_keywords = ["tech"]
        breaking_keywords = ["urgent"]
        weights = {
            "trending_weight": 1,
            "breaking_weight": 2,
            "max_trending_bonus": 3,
            "max_breaking_bonus": 4,
        }

        article = {
            "title": "Tech news",
            "desc": "Description",
            "publishedAt": datetime.now().isoformat(),
        }

        score = compute_score(
            article,
            "Technology",
            0.9,
            scoring_rules,
            source_prioritarias,
            trending_keywords,
            breaking_keywords,
            weights,
        )

        assert score > 0


class TestCacheManager:
    """Test cache manager functions."""

    def test_cache_dir_exists(self):
        """Test cache directory is created."""
        from src.shared.adapters.cache_manager import CACHE_DIR

        assert CACHE_DIR is not None
        assert "cache" in str(CACHE_DIR)


class TestTranslator:
    """Test translator functions."""

    def test_translator_module_exists(self):
        """Test translator module exists."""
        from src.shared.adapters.translator import (
            translate_text,
            _is_probably_spanish,
            _split_into_chunks,
        )

        assert callable(translate_text)
        assert callable(_is_probably_spanish)
        assert callable(_split_into_chunks)
