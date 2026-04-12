"""Tests for shared adapters."""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


class TestCacheManager:
    """Test cache manager functions."""

    def test_save_and_load_content(self):
        from src.shared.adapters.cache_manager import save_content_to_cache, load_content_from_cache

        url = "https://example.com/test123"
        content = "<html><body>" + "x" * 200 + "</body></html>"

        result = save_content_to_cache(url, content)
        assert result is True

        loaded, status = load_content_from_cache(url)
        assert loaded == content
        assert status == "cache_hit"

    def test_save_short_content(self):
        from src.shared.adapters.cache_manager import save_content_to_cache

        result = save_content_to_cache("https://example.com/short", "short")
        assert result is False

    def test_load_nonexistent(self):
        from src.shared.adapters.cache_manager import load_content_from_cache

        content, status = load_content_from_cache("https://nonexistent.com")
        assert content is None
        assert status == "no_cache"

    def test_clear_old_cache(self):
        from src.shared.adapters.cache_manager import clear_old_cache

        result = clear_old_cache(max_age_hours=72)
        assert isinstance(result, int)


class TestImageEnricher:
    """Test image enricher."""

    def test_enrich_empty_posts(self):
        from src.shared.adapters.image_enricher import ImageEnricher

        enricher = ImageEnricher()
        result = enricher.enrich([])
        assert result == []

    def test_enrich_with_unsplash_url(self):
        from src.shared.adapters.image_enricher import ImageEnricher

        enricher = ImageEnricher()
        posts = [{"title": "Test", "unsplash_image": "https://unsplash.com/img.jpg"}]
        result = enricher.enrich(posts)
        assert result[0]["image_url"] == "https://unsplash.com/img.jpg"

    def test_enrich_with_google_url(self):
        from src.shared.adapters.image_enricher import ImageEnricher

        enricher = ImageEnricher()
        posts = [{"title": "Test", "google_image": "https://google.com/img.jpg"}]
        result = enricher.enrich(posts)
        assert result[0]["image_url"] == "https://google.com/img.jpg"

    def test_enrich_fallback(self):
        from src.shared.adapters.image_enricher import ImageEnricher

        enricher = ImageEnricher()
        posts = [{"title": "Test"}]
        result = enricher.enrich(posts)
        assert "image_url" in result[0]
        assert result[0]["image_credit"] == "NBES"


class TestMongoDB:
    """Test MongoDB adapter."""

    @patch('src.shared.adapters.mongo_db.get_database')
    def test_get_database(self, mock_get_db):
        from src.shared.adapters.mongo_db import get_database

        mock_db = Mock()
        mock_get_db.return_value = mock_db

        db = get_database()
        assert db is not None


class TestAIAdapterFactory:
    """Test AI adapter factory error paths."""

    def test_import_error_in_factory(self):
        from src.shared.adapters.ai.ai_factory import get_ai_adapter

        with pytest.raises(ValueError, match="no válido"):
            get_ai_adapter("nonexistent_provider")


class TestGeminiAdapter:
    """Test Gemini adapter."""

    def test_gemini_adapter_module(self):
        from src.shared.adapters.ai import gemini_adapter

        assert gemini_adapter is not None
        assert hasattr(gemini_adapter, 'GeminiAdapter')


class TestOpenRouterAdapter:
    """Test OpenRouter adapter."""

    def test_openrouter_adapter_init_no_key(self):
        from src.shared.adapters.ai.openrouter_adapter import OpenRouterAdapter

        adapter = OpenRouterAdapter({})
        assert adapter is not None


class TestSocialPublisher:
    """Test social publisher adapters."""

    def test_bluesky_publisher_init_and_methods(self):
        from src.shared.adapters.bluesky_publisher import BlueskyPublisher

        publisher = BlueskyPublisher()
        assert publisher is not None

    def test_facebook_publisher_init(self):
        from src.shared.adapters.facebook_publisher import FacebookPublisher

        publisher = FacebookPublisher()
        assert publisher is not None

    def test_mastodon_publisher_init(self):
        from src.shared.adapters.mastodon_publisher import MastodonPublisher

        publisher = MastodonPublisher()
        assert publisher is not None

    def test_wordpress_publisher_init(self):
        from src.shared.adapters.wordpress_publisher import WordPressPublisher

        publisher = WordPressPublisher()
        assert publisher is not None


class TestGoogleImagesFetcher:
    """Test Google Images fetcher."""

    def test_clean_title(self):
        from src.shared.adapters.google_images_fetcher import clean_title

        assert clean_title("BREAKING: Test news!") == "Test news"
        assert clean_title("Hello world") == "Hello world"

    def test_fallback_google_query(self):
        from src.shared.adapters.google_images_fetcher import fallback_google_query

        result = fallback_google_query("protesta en Madrid")
        assert result is not None

    @patch('src.shared.adapters.google_images_fetcher.search_google_images')
    def test_fetch_for_posts_with_mock(self, mock_search):
        from src.shared.adapters.google_images_fetcher import GoogleImagesFetcher

        mock_search.return_value = {
            "id": "123",
            "url": "https://example.com/img.jpg",
        }
        fetcher = GoogleImagesFetcher()
        posts = [{"title": "Test news article", "image_url": ""}]
        result = fetcher.fetch_for_posts(posts)
        assert len(result) == 1
        assert "google_image" in result[0]


class TestUnsplashFetcher:
    """Test Unsplash fetcher."""

    def test_clean_title(self):
        from src.shared.adapters.unsplash_fetcher import clean_title

        assert clean_title("LIVE: Test event") == "Test event"
        assert clean_title("Simple title") == "Simple title"

    def test_fallback_query(self):
        from src.shared.adapters.unsplash_fetcher import fallback_unsplash_query

        result = fallback_unsplash_query("tecnología en España")
        assert result is not None

    @patch('src.shared.adapters.unsplash_fetcher.search_unsplash')
    def test_fetch_for_posts_with_mock(self, mock_search):
        from src.shared.adapters.unsplash_fetcher import UnsplashFetcher

        mock_search.return_value = {
            "id": "abc123",
            "regular_url": "https://unsplash.com/img.jpg",
            "full_url": "https://unsplash.com/full.jpg",
            "user": "John Doe",
            "description": "A nice photo",
        }
        fetcher = UnsplashFetcher()
        posts = [{"title": "Test article", "image_url": ""}]
        result = fetcher.fetch_for_posts(posts)
        assert len(result) == 1
        assert "unsplash_image" in result[0]


class TestPublishersSocial:
    """Test social publishers."""

    def test_social_publisher_module(self):
        from src.shared.adapters.publishers import social

        assert social is not None


class TestTranslator:
    """Test translator."""

    def test_translator_module(self):
        from src.shared.adapters import translator

        assert translator is not None


class TestVideoTranscriber:
    """Test video transcriber."""

    def test_video_transcriber_init(self):
        from src.video.infrastructure.adapters.video_transcriber import VideoTranscriber

        transcriber = VideoTranscriber()
        assert transcriber is not None
