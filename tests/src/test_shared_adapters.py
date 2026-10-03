"""Tests for shared adapters."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


class TestCacheManager:
    """Test cache manager functions."""

    def test_save_and_load_content(self):
        from src.shared.adapters.cache_manager import (
            save_content_to_cache,
            load_content_from_cache,
        )

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

    @patch(
        "src.shared.adapters.image_enricher.ImageEnricher._is_accessible_image",
        return_value=True,
    )
    def test_enrich_with_unsplash_url(self, mock_is_accessible):
        from src.shared.adapters.image_enricher import ImageEnricher

        enricher = ImageEnricher()
        posts = [{"title": "Test", "unsplash_image": "https://unsplash.com/img.jpg"}]
        result = enricher.enrich(posts)
        assert result[0]["image_url"] == "https://unsplash.com/img.jpg"

    @patch(
        "src.shared.adapters.image_enricher.ImageEnricher._is_accessible_image",
        return_value=True,
    )
    def test_enrich_with_google_url(self, mock_is_accessible):
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

    @patch("src.shared.adapters.mongo_db.get_database")
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
        assert hasattr(gemini_adapter, "GeminiAdapter")


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
    """Test Google Images fetcher.

    Since refactor 3926848 the module exposes `filter_by_relevance()` plus a
    `GoogleImagesFetcher` class (the former module-level `clean_title`,
    `fallback_google_query` and `search_google_images` helpers are gone).
    """

    def test_filter_by_relevance_keeps_matching_descriptions(self):
        from src.shared.adapters.google_images_fetcher import filter_by_relevance

        images = [
            {"id": "hit", "url": "https://example.com/hit.jpg", "description": "protest march downtown"},
            {"id": "miss", "url": "https://example.com/miss.jpg", "description": "sunny beach holiday"},
        ]
        result = filter_by_relevance(images, ["protest downtown"])

        assert [img["id"] for img in result] == ["hit"]
        assert result[0]["_relevance_score"] > 0.25

    def test_filter_by_relevance_drops_unrelated_descriptions(self):
        from src.shared.adapters.google_images_fetcher import filter_by_relevance

        images = [
            {"id": "miss", "url": "https://example.com/miss.jpg", "description": "sunny beach holiday"},
        ]
        assert filter_by_relevance(images, ["parlament election vote"]) == []

    def test_filter_by_relevance_passthrough_without_input(self):
        from src.shared.adapters.google_images_fetcher import filter_by_relevance

        assert filter_by_relevance([], ["protest"]) == []
        assert filter_by_relevance([{"id": "x"}], []) == [{"id": "x"}]

    def test_filter_by_relevance_uses_alt_when_description_missing(self):
        from src.shared.adapters.google_images_fetcher import filter_by_relevance

        images = [{"id": "hit", "url": "https://example.com/h.jpg", "alt": "government building protest"}]
        result = filter_by_relevance(images, ["government protest"])
        assert [img["id"] for img in result] == ["hit"]

    def test_search_images_without_keys_returns_empty(self):
        """Without GOOGLE_SEARCH_API_KEY/CX the fetcher must degrade to [] (no network)."""
        from src.shared.adapters import google_images_fetcher as mod

        with patch.object(mod, "GOOGLE_API_KEY", ""), patch.object(mod, "GOOGLE_CX", ""):
            assert mod.GoogleImagesFetcher()._search_images("protest", limit=5) == []

    def test_search_images_maps_api_results(self):
        from src.shared.adapters import google_images_fetcher as mod

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "link": "https://example.com/img.jpg",
                    "title": "Protest downtown",
                    "snippet": "protest downtown crowd",
                    "image": {"thumbnailLink": "https://example.com/thumb.jpg"},
                }
            ]
        }

        with patch.object(mod, "GOOGLE_API_KEY", "key"), patch.object(mod, "GOOGLE_CX", "cx"), \
             patch.object(mod, "get_used_ids", return_value=set()), \
             patch.object(mod._google_session, "get", return_value=mock_response):
            result = mod.GoogleImagesFetcher()._search_images("protest", limit=5)

        assert len(result) == 1
        assert result[0]["url"] == "https://example.com/img.jpg"
        assert result[0]["thumbnail"] == "https://example.com/thumb.jpg"
        assert result[0]["description"] == "protest downtown crowd"
        # The adapter derives its own id from the image URL (hash is salted per
        # process, so only its presence/shape is assertable).
        assert isinstance(result[0]["id"], str) and result[0]["id"]

    def test_search_images_skips_already_used_links(self):
        from src.shared.adapters import google_images_fetcher as mod

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [{"link": "https://example.com/used.jpg", "snippet": "protest"}]
        }

        with patch.object(mod, "GOOGLE_API_KEY", "key"), patch.object(mod, "GOOGLE_CX", "cx"), \
             patch.object(mod, "get_used_ids", return_value={"https://example.com/used.jpg"}), \
             patch.object(mod._google_session, "get", return_value=mock_response):
            result = mod.GoogleImagesFetcher()._search_images("protest", limit=5)

        assert result == []

    def test_search_images_http_error_returns_empty(self):
        from src.shared.adapters import google_images_fetcher as mod

        mock_response = Mock()
        mock_response.status_code = 429

        with patch.object(mod, "GOOGLE_API_KEY", "key"), patch.object(mod, "GOOGLE_CX", "cx"), \
             patch.object(mod, "get_used_ids", return_value=set()), \
             patch.object(mod._google_session, "get", return_value=mock_response):
            assert mod.GoogleImagesFetcher()._search_images("protest") == []

    @patch("src.shared.adapters.image_query_generator.generar_keywords_visuales_con_llm")
    @patch("src.shared.adapters.google_images_fetcher.add_used_id")
    @patch("src.shared.adapters.google_images_fetcher.get_used_ids", return_value=set())
    def test_fetch_for_posts_with_mock(self, mock_used_ids, mock_add_id, mock_keywords):
        from src.shared.adapters.google_images_fetcher import GoogleImagesFetcher

        mock_keywords.return_value = ["protest downtown"]

        fetcher = GoogleImagesFetcher()
        posts = [{"title": "Protest in downtown", "image_url": ""}]
        with patch.object(
            fetcher,
            "_search_images",
            return_value=[
                {"id": "123", "url": "https://example.com/img.jpg", "description": "protest downtown crowd"}
            ],
        ):
            result = fetcher.fetch_for_posts(posts)

        assert len(result) == 1
        assert "google_image" in result[0]
        assert result[0]["google_image"] == "https://example.com/img.jpg"
        assert result[0]["image_credit"] == "Google Images"
        assert result[0]["alt_text"] == "protest downtown crowd"
        mock_add_id.assert_called_once_with("123")

    @patch("src.shared.adapters.image_query_generator.generar_keywords_visuales_con_llm")
    def test_fetch_for_posts_skips_posts_that_already_have_image(self, mock_keywords):
        from src.shared.adapters.google_images_fetcher import GoogleImagesFetcher

        posts = [{"title": "Already enriched", "google_image": "https://example.com/x.jpg"}]
        result = GoogleImagesFetcher().fetch_for_posts(posts)

        mock_keywords.assert_not_called()
        assert result[0]["google_image"] == "https://example.com/x.jpg"

    @patch("src.shared.adapters.image_query_generator.generar_keywords_visuales_con_llm")
    def test_fetch_for_posts_leaves_post_untouched_when_no_relevant_image(self, mock_keywords):
        from src.shared.adapters.google_images_fetcher import GoogleImagesFetcher

        mock_keywords.return_value = ["protest downtown"]
        fetcher = GoogleImagesFetcher()
        posts = [{"title": "Protest in downtown", "image_url": ""}]

        with patch.object(fetcher, "_search_images", return_value=[]):
            result = fetcher.fetch_for_posts(posts)

        assert "google_image" not in result[0]


class TestUnsplashFetcher:
    """Test Unsplash fetcher.

    Since refactor 3926848 the module exposes `filter_by_relevance()` plus an
    `UnsplashFetcher` class (the former module-level `clean_title`,
    `fallback_unsplash_query` and `search_unsplash` helpers are gone).
    """

    def test_filter_by_relevance_keeps_matching_descriptions(self):
        from src.shared.adapters.unsplash_fetcher import filter_by_relevance

        images = [
            {"id": "hit", "regular_url": "https://u/hit.jpg", "description": "government building downtown"},
            {"id": "miss", "regular_url": "https://u/miss.jpg", "description": "cat sleeping on sofa"},
        ]
        result = filter_by_relevance(images, ["government building"])

        assert [img["id"] for img in result] == ["hit"]
        assert result[0]["_relevance_score"] > 0.25

    def test_filter_by_relevance_drops_unrelated_descriptions(self):
        from src.shared.adapters.unsplash_fetcher import filter_by_relevance

        images = [{"id": "miss", "regular_url": "https://u/miss.jpg", "description": "cat sleeping on sofa"}]
        assert filter_by_relevance(images, ["parliament election"]) == []

    def test_search_images_without_key_returns_empty(self):
        """Without UNSPLASH_ACCESS_KEY the fetcher must degrade to [] (no network)."""
        from src.shared.adapters import unsplash_fetcher as mod

        with patch.object(mod, "UNSPLASH_ACCESS_KEY", ""):
            assert mod.UnsplashFetcher()._search_images("protest", limit=5) == []

    def test_search_images_maps_results_and_skips_used_ids(self):
        from src.shared.adapters import unsplash_fetcher as mod

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "new1",
                    "urls": {"raw": "https://u/raw.jpg", "full": "https://u/full.jpg", "regular": "https://u/reg.jpg", "small": "https://u/small.jpg"},
                    "description": "protest downtown",
                    "user": {"name": "Jane Doe"},
                },
                {
                    "id": "used1",
                    "urls": {"raw": "https://u/raw2.jpg", "full": "https://u/full2.jpg", "regular": "https://u/reg2.jpg", "small": "https://u/small2.jpg"},
                    "description": "protest square",
                    "user": {"name": "John Doe"},
                },
            ]
        }

        with patch.object(mod, "UNSPLASH_ACCESS_KEY", "key"), \
             patch.object(mod, "get_used_ids", return_value={"used1"}), \
             patch.object(mod._unsplash_session, "get", return_value=mock_response):
            result = mod.UnsplashFetcher()._search_images("protest", limit=5)

        assert [img["id"] for img in result] == ["new1"]
        assert result[0]["regular_url"] == "https://u/reg.jpg"
        assert result[0]["user"] == "Jane Doe"

    def test_search_images_http_error_returns_empty(self):
        from src.shared.adapters import unsplash_fetcher as mod

        mock_response = Mock()
        mock_response.status_code = 403

        with patch.object(mod, "UNSPLASH_ACCESS_KEY", "key"), \
             patch.object(mod, "get_used_ids", return_value=set()), \
             patch.object(mod._unsplash_session, "get", return_value=mock_response):
            assert mod.UnsplashFetcher()._search_images("protest") == []

    @patch("src.shared.adapters.image_query_generator.generar_keywords_visuales_con_llm")
    @patch("src.shared.adapters.unsplash_fetcher.add_used_id")
    @patch("src.shared.adapters.unsplash_fetcher.get_used_ids", return_value=set())
    def test_fetch_for_posts_with_mock(self, mock_used_ids, mock_add_id, mock_keywords):
        from src.shared.adapters.unsplash_fetcher import UnsplashFetcher

        mock_keywords.return_value = ["protest downtown"]

        fetcher = UnsplashFetcher()
        posts = [{"title": "Protest in downtown", "image_url": ""}]
        with patch.object(
            fetcher,
            "_search_images",
            return_value=[
                {
                    "id": "abc123",
                    "regular_url": "https://unsplash.com/reg.jpg",
                    "full_url": "https://unsplash.com/full.jpg",
                    "user": "John Doe",
                    "description": "protest downtown crowd",
                }
            ],
        ):
            result = fetcher.fetch_for_posts(posts)

        assert len(result) == 1
        assert "unsplash_image" in result[0]
        assert result[0]["unsplash_image"] == "https://unsplash.com/reg.jpg"
        assert result[0]["unsplash_image_url"] == "https://unsplash.com/full.jpg"
        assert result[0]["image_url"] == "https://unsplash.com/reg.jpg"
        assert result[0]["image_credit"] == "John Doe"
        assert result[0]["alt_text"] == "protest downtown crowd"
        mock_add_id.assert_called_once_with("abc123")

    @patch("src.shared.adapters.image_query_generator.generar_keywords_visuales_con_llm")
    def test_fetch_for_posts_skips_posts_that_already_have_image(self, mock_keywords):
        from src.shared.adapters.unsplash_fetcher import UnsplashFetcher

        posts = [{"title": "Already enriched", "unsplash_image": "https://u/x.jpg"}]
        result = UnsplashFetcher().fetch_for_posts(posts)

        mock_keywords.assert_not_called()
        assert result[0]["unsplash_image"] == "https://u/x.jpg"

    @patch("src.shared.adapters.image_query_generator.generar_keywords_visuales_con_llm")
    def test_fetch_for_posts_leaves_post_untouched_when_no_relevant_image(self, mock_keywords):
        from src.shared.adapters.unsplash_fetcher import UnsplashFetcher

        mock_keywords.return_value = ["protest downtown"]
        fetcher = UnsplashFetcher()
        posts = [{"title": "Protest in downtown", "image_url": ""}]

        with patch.object(fetcher, "_search_images", return_value=[]):
            result = fetcher.fetch_for_posts(posts)

        assert "unsplash_image" not in result[0]


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


class TestAudioConverter:
    """Test AudioConverter HTTP client."""

    @patch("src.shared.adapters.audio_converter.os.path.getsize", return_value=1024)
    @patch("src.shared.adapters.audio_converter.os.path.exists", return_value=True)
    @patch("src.shared.adapters.audio_converter.requests.post")
    def test_convert_to_mp3_calls_endpoint(self, mock_post, mock_exists, mock_getsize):
        from src.shared.adapters.audio_converter import AudioConverter

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"output": "/tmp/output.mp3"}
        mock_post.return_value = mock_response

        converter = AudioConverter(base_url="http://localhost:8082")
        result = converter.convert_to_mp3("/tmp/input.wav")

        assert result == "/tmp/output.mp3"
        call_args = mock_post.call_args
        assert call_args[1]["json"] == {"path": "/tmp/input.wav", "format": "mp3"}

    @patch("src.shared.adapters.audio_converter.os.path.getsize", return_value=1024)
    @patch("src.shared.adapters.audio_converter.os.path.exists", return_value=True)
    @patch("src.shared.adapters.audio_converter.requests.post")
    def test_convert_to_wav16k_calls_endpoint(
        self, mock_post, mock_exists, mock_getsize
    ):
        """The /audio/convert-to-wav16k route answers with binary audio, not JSON.

        See AudioConverter.convert_to_wav16k docstring ("Opción A (recomendada):
        JSON {"path": ...} -> binario WAV en respuesta").
        """
        from src.shared.adapters.audio_converter import AudioConverter

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"RIFF fake wav payload"
        mock_post.return_value = mock_response

        converter = AudioConverter(base_url="http://localhost:8082")
        result = converter.convert_to_wav16k("/tmp/input.mp3", "/tmp/converted.wav")

        assert result == "/tmp/converted.wav"
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://localhost:8082/audio/convert-to-wav16k"
        assert call_args[1]["json"] == {"path": "/tmp/input.mp3"}
        assert Path("/tmp/converted.wav").read_bytes() == b"RIFF fake wav payload"

    @patch("src.shared.adapters.audio_converter.os.path.exists", return_value=True)
    @patch("src.shared.adapters.audio_converter.requests.post")
    def test_convert_to_wav16k_generates_output_path_when_omitted(self, mock_post, mock_exists):
        """Omitting output_path must derive a unique temp file name."""
        from src.shared.adapters.audio_converter import AudioConverter

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"wav"
        mock_post.return_value = mock_response

        converter = AudioConverter(base_url="http://localhost:8082")
        result = converter.convert_to_wav16k("/tmp/input.mp3")

        assert result is not None
        assert result.endswith(".wav")
        assert "wav16k_" in result
        Path(result).unlink(missing_ok=True)

    @patch("src.shared.adapters.audio_converter.os.path.exists", return_value=False)
    @patch("src.shared.adapters.audio_converter.requests.post")
    def test_convert_to_wav16k_missing_input_returns_none(self, mock_post, mock_exists):
        """A missing input must short-circuit before any HTTP call."""
        from src.shared.adapters.audio_converter import AudioConverter

        converter = AudioConverter(base_url="http://localhost:8082")
        assert converter.convert_to_wav16k("/tmp/nope.mp3") is None
        mock_post.assert_not_called()

    @patch("src.shared.adapters.audio_converter.os.path.exists", return_value=True)
    @patch("src.shared.adapters.audio_converter.requests.post")
    def test_convert_to_wav16k_http_error_returns_none(self, mock_post, mock_exists):
        from src.shared.adapters.audio_converter import AudioConverter

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "not found"
        mock_post.return_value = mock_response

        converter = AudioConverter(base_url="http://localhost:8082")
        assert converter.convert_to_wav16k("/tmp/input.mp3", "/tmp/out.wav") is None

    @patch("src.shared.adapters.audio_converter.os.path.exists", return_value=True)
    @patch("src.shared.adapters.audio_converter.requests.post")
    def test_has_audio_stream_true(self, mock_post, mock_exists):
        from src.shared.adapters.audio_converter import AudioConverter

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"has_audio": True}
        mock_post.return_value = mock_response

        converter = AudioConverter(base_url="http://localhost:8082")
        assert converter.has_audio_stream("/tmp/video.mp4") is True

    @patch("src.shared.adapters.audio_converter.requests.post")
    def test_has_audio_stream_false(self, mock_post):
        from src.shared.adapters.audio_converter import AudioConverter

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"has_audio": False}
        mock_post.return_value = mock_response

        converter = AudioConverter(base_url="http://localhost:8082")
        assert converter.has_audio_stream("/tmp/video.mp4") is False


class TestTTSFactory:
    """Test TTS Factory selection."""

    @patch("src.shared.adapters.tts_factory.TTSAdapter")
    def test_get_tts_adapter_speaches(self, mock_adapter):
        from src.shared.adapters.tts_factory import get_tts_adapter, _adapter_cache

        # Clear cache to ensure fresh instantiation
        _adapter_cache.clear()

        mock_instance = Mock()
        mock_adapter.return_value = mock_instance

        with patch("config.settings.Settings.TTS_MODE", "speaches"):
            adapter = get_tts_adapter()
            assert adapter is mock_instance

    @patch("src.shared.adapters.tts_factory.CoquiTTSAdapter")
    def test_get_tts_adapter_coqui(self, mock_adapter):
        from src.shared.adapters.tts_factory import get_tts_adapter, _adapter_cache

        # Clear cache to ensure fresh instantiation
        _adapter_cache.clear()

        mock_instance = Mock()
        mock_adapter.return_value = mock_instance

        with patch("config.settings.Settings.TTS_MODE", "coqui"):
            adapter = get_tts_adapter()
            assert adapter is mock_instance

    def test_get_tts_adapter_invalid_mode_uses_fallback(self):
        from src.shared.adapters.tts_factory import get_tts_adapter, _adapter_cache

        # Clear cache to ensure fresh adapter creation
        _adapter_cache.clear()

        with patch("config.settings.Settings.TTS_MODE", "invalid_mode"):
            adapter = get_tts_adapter()
            # Should return TTSAdapter (fallback)
            from src.shared.adapters.tts_adapter import TTSAdapter

            assert isinstance(adapter, TTSAdapter)


class TestCoquiTTSAdapter:
    """Test Coqui TTS Adapter with MP3 conversion.

    Since commit 1d830f4 the adapter does not instantiate AudioConverter itself;
    it receives one from `get_audio_converter()` (coqui_tts_adapter.py:66), so
    these tests inject the converter at that seam.
    """

    @staticmethod
    def _wav_response():
        response = Mock()
        response.status_code = 200
        response.iter_content = lambda chunk_size: [b"fake wav data"]
        return response

    @staticmethod
    def _adapter(mock_converter, audio_dir, **kwargs):
        """Build a CoquiTTSAdapter with deterministic output dir/post-processing/atempo."""
        from src.shared.adapters.coqui_tts_adapter import CoquiTTSAdapter

        with patch(
            "src.shared.adapters.coqui_tts_adapter.get_audio_converter",
            return_value=mock_converter,
        ), patch("config.settings.Settings.COQUI_API_URL", "http://localhost:5002"):
            adapter = CoquiTTSAdapter(enable_post_processing=False, **kwargs)
        # Keep artefacts inside the test's tmp dir. The adapter default
        # (/tmp/audios) is a shared global owned by root in this environment.
        adapter.audio_dir = audio_dir
        # Neutralise atempo: .env ships COQUI_ATEMPO=1.1, which would trigger a
        # real HTTP call to ffmpeg-api. The atempo path has its own test below.
        adapter.atempo = 1.0
        return adapter

    @patch("src.shared.adapters.coqui_tts_adapter._coqui_session.get")
    def test_text_to_speech_returns_mp3(self, mock_get, tmp_path):
        from src.shared.adapters.coqui_tts_adapter import CoquiTTSAdapter

        mock_get.return_value = self._wav_response()

        mock_converter = Mock()
        expected_mp3 = tmp_path / "noticia_test.mp3"

        def _convert(**kwargs):
            # The adapter only accepts the MP3 if it really exists on disk.
            expected_mp3.write_bytes(b"fake mp3")
            return str(expected_mp3)

        mock_converter.convert_to_mp3.side_effect = _convert

        adapter = self._adapter(mock_converter, tmp_path)
        result = adapter.text_to_speech("Prueba texto")

        # Coqui must be called on the /api/tts route with the processed text
        call_url = mock_get.call_args[0][0]
        params = mock_get.call_args[1]["params"]
        assert call_url == "http://localhost:5002/api/tts"
        assert params["text"]
        assert "temperature" in params

        # The WAV produced must be handed to the injected converter
        mock_converter.convert_to_mp3.assert_called_once()
        assert mock_converter.convert_to_mp3.call_args[1]["delete_original"] is True

        assert result == str(expected_mp3)

    @patch("src.shared.adapters.coqui_tts_adapter._coqui_session.get")
    def test_conversion_fallback_to_wav_on_error(self, mock_get, tmp_path):
        from src.shared.adapters.coqui_tts_adapter import CoquiTTSAdapter

        mock_get.return_value = self._wav_response()

        # Conversión falla, devuelve None
        mock_converter = Mock()
        mock_converter.convert_to_mp3.return_value = None

        adapter = self._adapter(mock_converter, tmp_path)
        result = adapter.text_to_speech("texto")

        # Aunque conversión falle, devuelve WAV path
        assert result.endswith(".wav")
        assert str(tmp_path) in result

    @patch("src.shared.adapters.coqui_tts_adapter._coqui_session.post")
    @patch("src.shared.adapters.coqui_tts_adapter._coqui_session.get")
    def test_text_to_speech_applies_atempo_when_configured(
        self, mock_get, mock_post, tmp_path
    ):
        from src.shared.adapters.coqui_tts_adapter import CoquiTTSAdapter

        mock_get.return_value = self._wav_response()
        atempo_response = Mock()
        atempo_response.status_code = 200
        atempo_response.content = b"atempo wav"
        mock_post.return_value = atempo_response

        mock_converter = Mock()
        mock_converter.base_url = "http://ffmpeg.test"
        expected_mp3 = tmp_path / "noticia_test.mp3"

        def _convert(**kwargs):
            expected_mp3.write_bytes(b"fake mp3")
            return str(expected_mp3)

        mock_converter.convert_to_mp3.side_effect = _convert

        with patch(
            "src.shared.adapters.coqui_tts_adapter.get_audio_converter",
            return_value=mock_converter,
        ), patch("config.settings.Settings.COQUI_API_URL", "http://localhost:5002"):
            adapter = CoquiTTSAdapter(enable_post_processing=False)
        adapter.audio_dir = tmp_path
        adapter.atempo = 1.25

        result = adapter.text_to_speech("texto")

        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == "http://ffmpeg.test/audio/apply-atempo"
        assert mock_post.call_args[1]["json"]["tempo_factor"] == 1.25
        assert result == str(expected_mp3)

    @patch("src.shared.adapters.coqui_tts_adapter._coqui_session.get")
    def test_text_to_speech_raises_on_http_error(self, mock_get, tmp_path):
        from src.shared.adapters.coqui_tts_adapter import CoquiTTSAdapter

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        mock_get.return_value = mock_response

        adapter = self._adapter(Mock(), tmp_path)
        with pytest.raises(RuntimeError):
            adapter.text_to_speech("texto")

    @patch("src.shared.adapters.coqui_tts_adapter._coqui_session.get")
    def test_text_to_speech_empty_text_returns_empty_string(self, mock_get, tmp_path):
        from src.shared.adapters.coqui_tts_adapter import CoquiTTSAdapter

        adapter = self._adapter(Mock(), tmp_path)
        assert adapter.text_to_speech("   ") == ""
        mock_get.assert_not_called()

    @patch("src.shared.adapters.coqui_tts_adapter._coqui_session.get")
    def test_is_available_success(self, mock_get):
        from src.shared.adapters.coqui_tts_adapter import CoquiTTSAdapter

        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        with patch("config.settings.Settings.COQUI_API_URL", "http://localhost:5002"):
            adapter = CoquiTTSAdapter()
            assert adapter.is_available() is True
            assert mock_get.call_args[0][0] == "http://localhost:5002/health"

    @patch("src.shared.adapters.coqui_tts_adapter._coqui_session.get")
    def test_is_available_failure(self, mock_get):
        from src.shared.adapters.coqui_tts_adapter import CoquiTTSAdapter

        mock_get.side_effect = OSError("Connection error")

        with patch("config.settings.Settings.COQUI_API_URL", "http://localhost:5002"):
            adapter = CoquiTTSAdapter()
            assert adapter.is_available() is False

    @patch("src.shared.adapters.coqui_tts_adapter._coqui_session.get")
    def test_is_available_false_on_non_200(self, mock_get):
        """A reachable-but-broken service must also report unavailable."""
        from src.shared.adapters.coqui_tts_adapter import CoquiTTSAdapter

        mock_response = Mock()
        mock_response.status_code = 503
        mock_get.return_value = mock_response

        with patch("config.settings.Settings.COQUI_API_URL", "http://localhost:5002"):
            adapter = CoquiTTSAdapter()
            assert adapter.is_available() is False
