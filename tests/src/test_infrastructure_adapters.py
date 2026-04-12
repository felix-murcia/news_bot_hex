"""Tests for news infrastructure adapters."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta


class TestScoring:
    """Test scoring functions."""

    def test_compute_score_base(self):
        from src.news.infrastructure.adapters.scoring import compute_score

        article = {
            "title": "Test Article",
            "desc": "Test description",
            "source": {"name": "Reuters"},
            "publishedAt": "2024-01-15T10:00:00Z",
        }
        score = compute_score(
            article=article,
            tema="politics",
            confidence=0.95,
            scoring_rules={"politics": 5},
            source_prioritarias={"Reuters"},
            trending_keywords=["test"],
            breaking_keywords=["breaking"],
            weights={"max_trending_bonus": 3, "trending_weight": 1, "max_breaking_bonus": 4, "breaking_weight": 2},
        )
        assert score >= 5

    def test_compute_score_with_trending(self):
        from src.news.infrastructure.adapters.scoring import compute_score

        article = {
            "title": "Economy test article",
            "desc": "Description with economy keyword",
            "source": {"name": "AP"},
            "publishedAt": "2024-01-15T10:00:00Z",
        }
        score = compute_score(
            article=article,
            tema="economia",
            confidence=0.8,
            scoring_rules={"economia": 3},
            source_prioritarias=set(),
            trending_keywords=["economy"],
            breaking_keywords=[],
            weights={"max_trending_bonus": 3, "trending_weight": 1, "max_breaking_bonus": 4, "breaking_weight": 2},
        )
        assert score > 3

    def test_compute_score_with_breaking(self):
        from src.news.infrastructure.adapters.scoring import compute_score

        article = {
            "title": "Breaking news headline",
            "desc": "Breaking event description",
            "source": {"name": "BBC"},
        }
        score = compute_score(
            article=article,
            tema="news",
            confidence=0.7,
            scoring_rules={"news": 2},
            source_prioritarias=set(),
            trending_keywords=[],
            breaking_keywords=["breaking", "news"],
            weights={"max_trending_bonus": 3, "trending_weight": 1, "max_breaking_bonus": 4, "breaking_weight": 2},
        )
        assert score > 2

    def test_categorizar_noticia(self):
        from src.news.infrastructure.adapters.scoring import categorizar_noticia

        result = categorizar_noticia("Test title", "Test description")
        assert isinstance(result, str)

    def test_check_breaking_keywords(self):
        from src.news.infrastructure.adapters.scoring import check_breaking_keywords

        assert check_breaking_keywords("Breaking news", "", ["breaking", "news"]) >= 1
        assert check_breaking_keywords("Normal article", "nothing special", ["emergency"]) == 0

    def test_is_valid_score(self):
        from src.news.infrastructure.adapters.scoring import is_valid_score

        assert is_valid_score(10, 0) is True
        assert is_valid_score(3, 3) is True
        assert is_valid_score(2, 0) is False

    def test_sort_verified_news(self):
        from src.news.infrastructure.adapters.scoring import sort_verified_news

        news = [
            {"title": "A", "score": 5, "publishedAt": "2024-01-01"},
            {"title": "B", "score": 10, "publishedAt": "2024-01-02"},
            {"title": "C", "score": 5, "publishedAt": "2024-01-03"},
        ]
        sorted_news = sort_verified_news(news)
        assert sorted_news[0]["title"] == "B"

    def test_parse_iso_date_empty(self):
        from src.news.infrastructure.adapters.scoring import parse_iso_date

        assert parse_iso_date("") == datetime.min

    def test_resumir_noticia(self):
        from src.news.infrastructure.adapters.scoring import resumir_noticia

        assert resumir_noticia("Title", "Description") == "Title. Description"
        assert resumir_noticia("Title", "") == "Title"
        long_desc = "x" * 300
        result = resumir_noticia("Title", long_desc)
        assert len(result) <= 250


class TestDateUtils:
    """Test date utilities."""

    def test_parse_date_flexible_none(self):
        from src.news.infrastructure.adapters.date_utils import parse_date_flexible

        assert parse_date_flexible(None) is None

    def test_parse_date_flexible_iso(self):
        from src.news.infrastructure.adapters.date_utils import parse_date_flexible

        result = parse_date_flexible("2024-01-15T10:30:00Z")
        assert result is not None

    def test_parse_date_flexible_gmt(self):
        from src.news.infrastructure.adapters.date_utils import parse_date_flexible

        result = parse_date_flexible("Mon, 15 Jan 2024 10:30:00 GMT")
        assert result is not None

    def test_is_today_or_yesterday(self):
        from src.news.infrastructure.adapters.date_utils import is_today_or_yesterday

        now = datetime.now(timezone.utc)
        assert is_today_or_yesterday(now) is True

        yesterday = now - timedelta(days=1)
        assert is_today_or_yesterday(yesterday) is True

        old = now - timedelta(days=5)
        assert is_today_or_yesterday(old) is False

    def test_is_today_or_yesterday_none(self):
        from src.news.infrastructure.adapters.date_utils import is_today_or_yesterday

        assert is_today_or_yesterday(None) is False

    def test_get_article_date_found(self):
        from src.news.infrastructure.adapters.date_utils import get_article_date

        article = {"publishedAt": "2024-01-15"}
        result = get_article_date(article)
        assert result == "2024-01-15"

    def test_get_article_date_not_found(self):
        from src.news.infrastructure.adapters.date_utils import get_article_date

        article = {"title": "Test"}
        assert get_article_date(article) is None


class TestRSSFetcher:
    """Test RSS fetcher."""

    def test_rss_fetcher_module(self):
        from src.news.infrastructure.adapters import rss_fetcher

        assert rss_fetcher is not None


class TestContentExtractor:
    """Test content extractor."""

    def test_content_extractor_module(self):
        from src.news.infrastructure.adapters import content_extractor

        assert content_extractor is not None
