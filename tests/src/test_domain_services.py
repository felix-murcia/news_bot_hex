"""Tests for news domain services with high coverage."""
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestValidationRulesCache:
    """Test ValidationRulesCache."""

    def test_get_instance_singleton(self):
        from src.news.domain.services.classic_news_validator import ValidationRulesCache

        instance1 = ValidationRulesCache.get_instance()
        instance2 = ValidationRulesCache.get_instance()
        assert instance1 is instance2

    def test_load_defaults(self):
        from src.news.domain.services.classic_news_validator import ValidationRulesCache

        cache = ValidationRulesCache()
        cache._loaded = False
        cache.load_defaults()

        assert cache._loaded is True
        assert cache._stopwords is not None
        assert cache._sensationalist_words is not None
        assert cache._source_indicators is not None
        assert cache._scoring_config is not None
        assert cache._date_patterns is not None

    def test_ensure_loaded(self):
        from src.news.domain.services.classic_news_validator import ValidationRulesCache

        instance = ValidationRulesCache.ensure_loaded()
        assert instance is not None

    def test_properties_after_load(self):
        from src.news.domain.services.classic_news_validator import ValidationRulesCache

        cache = ValidationRulesCache()
        cache.load_defaults()

        assert isinstance(cache.stopwords, frozenset)
        assert isinstance(cache.sensationalist_words, frozenset)
        assert isinstance(cache.source_indicators, list)
        assert isinstance(cache.scoring_config, dict)
        assert isinstance(cache.date_patterns, list)

    def test_get_validation_rules(self):
        from src.news.domain.services.classic_news_validator import get_validation_rules

        rules = get_validation_rules()
        assert rules is not None


class TestPreprocessText:
    """Test preprocess_text."""

    def test_preprocess_empty(self):
        from src.news.domain.services.classic_news_validator import preprocess_text

        assert preprocess_text("") == ""
        assert preprocess_text(None) == ""

    def test_preprocess_normal(self):
        from src.news.domain.services.classic_news_validator import preprocess_text

        result = preprocess_text("The quick brown fox jumps over 123 lazy dogs!")
        assert "quick" in result
        assert "brown" in result
        assert "123" not in result

    def test_preprocess_removes_urls(self):
        from src.news.domain.services.classic_news_validator import preprocess_text

        result = preprocess_text("Check https://example.com for details")
        assert "https" not in result
        assert "example" not in result

    def test_preprocess_removes_html(self):
        from src.news.domain.services.classic_news_validator import preprocess_text

        result = preprocess_text("<p>Hello world</p>")
        assert "<" not in result


class TestHeuristicPredict:
    """Test heuristic_predict."""

    def test_real_news(self):
        from src.news.domain.services.classic_news_validator import heuristic_predict

        text = (
            "The government announced today that according to official sources "
            "the new policy will take effect in January. The study shows 50 percent "
            "increase in funding for education."
        )
        is_real, confidence = heuristic_predict(text)
        assert is_real is True
        assert 0.0 <= confidence <= 1.0

    def test_fake_news(self):
        from src.news.domain.services.classic_news_validator import heuristic_predict

        text = "SHOCKING EXPOSED: The secret conspiracy they don't want you to know! UNBELIEVABLE hoax!!!"
        is_real, confidence = heuristic_predict(text)
        assert is_real is False

    def test_empty_text(self):
        from src.news.domain.services.classic_news_validator import heuristic_predict

        is_real, confidence = heuristic_predict("")
        assert isinstance(is_real, bool)
        assert 0.0 <= confidence <= 1.0


class TestVerifiedArticle:
    """Test VerifiedArticle entity."""

    def test_from_dict_with_string_date(self):
        from src.news.domain.entities.verified_article import VerifiedArticle

        data = {
            "title": "Test Article",
            "desc": "Test description",
            "source": "Test Source",
            "origin": "Test Origin",
            "url": "https://example.com",
            "publishedAt": "2024-01-15T10:30:00Z",
            "tema": "Test",
            "resumen": "Test summary",
            "score": 10,
            "model_prediction": "real",
            "confidence": 0.95,
            "verification": {"verified": True},
            "slug": "test-article",
            "content": "<p>Content</p>",
            "labels": ["Test"],
            "image_url": "https://example.com/img.jpg",
            "excerpt": "Excerpt",
            "seo_title": "SEO Title",
            "focus_keyword": "keyword",
            "image_credit": "Credit",
            "is_draft": False,
            "source_url": "https://source.com",
            "alt_text": "Alt text",
            "source_type": "news_man",
            "original_url": "https://original.com",
            "title_es": "Título ES",
        }

        article = VerifiedArticle.from_dict(data)
        assert article.title == "Test Article"
        assert article.slug == "test-article"

    def test_from_dict_with_none_date(self):
        from src.news.domain.entities.verified_article import VerifiedArticle

        data = {
            "title": "Test",
            "desc": "Desc",
            "source": "Source",
            "origin": "Origin",
            "url": "https://example.com",
            "publishedAt": None,
            "tema": "Test",
            "resumen": "Summary",
            "score": 5,
            "model_prediction": "real",
            "confidence": 0.8,
            "verification": {},
        }
        article = VerifiedArticle.from_dict(data)
        assert article.publishedAt is not None

    def test_to_dict(self):
        from datetime import datetime, timezone
        from src.news.domain.entities.verified_article import VerifiedArticle

        article = VerifiedArticle(
            title="Test",
            desc="Desc",
            source="Source",
            origin="Origin",
            url="https://example.com",
            publishedAt=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            tema="Test",
            resumen="Summary",
            score=10,
            model_prediction="real",
            confidence=0.95,
            verification={"verified": True},
            slug="test",
            content="<p>Content</p>",
            labels=["Test"],
        )

        d = article.to_dict()
        assert d["title"] == "Test"
        assert isinstance(d["publishedAt"], str)

    def test_post_init_defaults_labels(self):
        from src.news.domain.entities.verified_article import VerifiedArticle
        from datetime import datetime, timezone

        article = VerifiedArticle(
            title="Test",
            desc="Desc",
            source="Source",
            origin="Origin",
            url="https://example.com",
            publishedAt=datetime.now(timezone.utc),
            tema="Test",
            resumen="Summary",
            score=10,
            model_prediction="real",
            confidence=0.9,
            verification={},
        )
        assert article.labels == ["Noticias"]
