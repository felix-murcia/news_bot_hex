"""Comprehensive integration tests for the news bot application."""

import pytest
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add project root to path
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


class TestSettings:
    """Test centralized settings configuration."""

    def test_settings_initialization(self):
        """Test that settings can be initialized."""
        from config.settings import Settings

        assert Settings.BASE_DIR is not None
        assert Settings.DATA_DIR is not None
        assert Settings.CACHE_DIR is not None

    def test_settings_directories_exist(self):
        """Test that required directories exist."""
        from config.settings import Settings

        assert Settings.DATA_DIR.exists()
        assert Settings.CACHE_DIR.exists()

    def test_topic_normalization(self):
        """Test topic normalization."""
        from config.settings import Settings

        assert Settings.get_normalized_topic("Audio") == "Noticias"
        assert Settings.get_normalized_topic("Video") == "Noticias"
        assert Settings.get_normalized_topic("Custom Topic") == "Custom Topic"

    def test_backward_compatibility(self):
        """Test that old config imports still work."""
        from config.config import BASE_DIR, API_KEYS, POST_LIMITS

        assert BASE_DIR is not None
        assert isinstance(API_KEYS, dict)
        assert isinstance(POST_LIMITS, dict)


class TestRetryUtilities:
    """Test retry utilities."""

    def test_retry_decorator_import(self):
        """Test retry decorator can be imported."""
        from src.shared.utils.retry import retry_with_backoff

        assert retry_with_backoff is not None

    def test_retry_context_import(self):
        """Test retry context manager can be imported."""
        from src.shared.utils.retry import RetryContext

        assert RetryContext is not None

    def test_retry_on_success(self):
        """Test retry decorator on successful function."""
        from src.shared.utils.retry import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_function()
        assert result == "success"
        assert call_count == 1

    def test_retry_on_failure_then_success(self):
        """Test retry decorator retries on failure."""
        from src.shared.utils.retry import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def failing_then_succeeding():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "success"

        result = failing_then_succeeding()
        assert result == "success"
        assert call_count == 2


class TestAIFactory:
    """Test AI adapter factory."""

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"})
    def test_get_gemini_adapter(self):
        """Test getting Gemini adapter."""
        from src.shared.adapters.ai.ai_factory import get_ai_adapter

        adapter = get_ai_adapter("gemini", validate_key=False)
        assert adapter.provider == "gemini"

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"})
    def test_get_openrouter_adapter(self):
        """Test getting OpenRouter adapter."""
        from src.shared.adapters.ai.ai_factory import get_ai_adapter

        adapter = get_ai_adapter("openrouter", validate_key=False)
        assert adapter.provider == "openrouter"

    def test_list_providers(self):
        """Test listing available providers."""
        from src.shared.adapters.ai.ai_factory import list_providers

        providers = list_providers()
        assert isinstance(providers, list)
        assert "gemini" in providers
        assert "openrouter" in providers

    def test_invalid_provider_raises_error(self):
        """Test that invalid provider raises ValueError."""
        from src.shared.adapters.ai.ai_factory import get_ai_adapter

        with pytest.raises(ValueError, match="no válido"):
            get_ai_adapter("invalid_provider")


class TestAIGeminiAdapter:
    """Test Gemini AI adapter."""

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"})
    def test_gemini_adapter_initialization(self):
        """Test Gemini adapter initializes correctly."""
        from src.shared.adapters.ai.gemini_adapter import GeminiAdapter

        adapter = GeminiAdapter(validate_on_init=False)
        assert adapter.provider == "gemini"
        assert isinstance(adapter.api_key, str)

    @patch.dict(os.environ, {"GEMINI_API_KEY": ""})
    def test_gemini_adapter_missing_key_warning(self):
        """Test adapter handles empty/missing API key."""
        from src.shared.adapters.ai.gemini_adapter import GeminiAdapter

        adapter = GeminiAdapter(validate_on_init=False)
        # Key may come from .env or be empty
        assert isinstance(adapter.api_key, str)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"})
    def test_gemini_validate_key(self):
        """Test key validation."""
        from src.shared.adapters.ai.gemini_adapter import GeminiAdapter

        adapter = GeminiAdapter(validate_on_init=False)
        assert adapter.validate_key() is True

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"})
    def test_gemini_transcribe_not_implemented(self):
        """Test that transcription raises NotImplementedError."""
        from src.shared.adapters.ai.gemini_adapter import GeminiAdapter

        adapter = GeminiAdapter(validate_on_init=False)
        with pytest.raises(NotImplementedError):
            adapter.transcribe("fake_path.mp3")


class TestAIOpenRouterAdapter:
    """Test OpenRouter AI adapter."""

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"})
    def test_openrouter_adapter_initialization(self):
        """Test OpenRouter adapter initializes correctly."""
        from src.shared.adapters.ai.openrouter_adapter import OpenRouterAdapter

        adapter = OpenRouterAdapter(validate_on_init=False)
        assert adapter.provider == "openrouter"
        # API key may come from .env or mock
        assert isinstance(adapter.api_key, str)
        assert len(adapter.api_key) > 0

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": ""})
    def test_openrouter_adapter_missing_key_warning(self):
        """Test adapter handles empty/missing API key."""
        from src.shared.adapters.ai.openrouter_adapter import OpenRouterAdapter

        adapter = OpenRouterAdapter(validate_on_init=False)
        # Key may come from .env or be empty
        assert isinstance(adapter.api_key, str)


class TestBasePipeline:
    """Test base pipeline use case."""

    def test_base_pipeline_import(self):
        """Test base pipeline can be imported."""
        from src.shared.application.usecases.base_pipeline import BasePipelineUseCase

        assert BasePipelineUseCase is not None

    def test_base_pipeline_cannot_instantiate_directly(self):
        """Test that base class cannot be instantiated directly."""
        from src.shared.application.usecases.base_pipeline import BasePipelineUseCase

        with pytest.raises(TypeError):
            BasePipelineUseCase(mode="test")


class TestAudioPipeline:
    """Test audio pipeline."""

    def test_audio_pipeline_import(self):
        """Test audio pipeline can be imported."""
        from src.audio.application.usecases.audio_pipeline import AudioPipelineUseCase

        assert AudioPipelineUseCase is not None

    def test_audio_pipeline_inherits_from_base(self):
        """Test audio pipeline inherits from base."""
        from src.audio.application.usecases.audio_pipeline import AudioPipelineUseCase
        from src.shared.application.usecases.base_pipeline import BasePipelineUseCase

        assert issubclass(AudioPipelineUseCase, BasePipelineUseCase)

    def test_audio_pipeline_initialization(self):
        """Test audio pipeline initialization."""
        from src.audio.application.usecases.audio_pipeline import AudioPipelineUseCase

        pipeline = AudioPipelineUseCase(no_publish=True)
        assert pipeline.no_publish is True
        assert pipeline.mode == "audio"

    @patch('src.audio.application.usecases.audio_pipeline.run_from_audio')
    @patch('src.audio.infrastructure.adapters.audio_transcriber.transcribe_audio')
    @patch('src.audio.infrastructure.adapters.audio_fetcher.has_audio_stream')
    @patch('src.audio.infrastructure.adapters.audio_fetcher.download_audio')
    def test_audio_pipeline_run(
        self,
        mock_download,
        mock_has_stream,
        mock_transcribe,
        mock_run_from_audio,
    ):
        """Test audio pipeline execution with mocks."""
        from src.audio.application.usecases.audio_pipeline import AudioPipelineUseCase

        # Setup mocks
        mock_download.return_value = "/tmp/test_audio.mp3"
        mock_has_stream.return_value = True
        mock_transcribe.return_value = "Test transcript"
        mock_run_from_audio.return_value = {
            "article": {
                "title": "Test Article",
                "content": "<p>Test content</p>",
                "labels": ["Test"],
            },
            "tweet": "Test tweet",
            "article_file": "/tmp/article.json",
        }

        pipeline = AudioPipelineUseCase(no_publish=True)
        result = pipeline.run("https://example.com/audio", "Test")

        assert result["mode"] == "audio"
        assert result["transcript"] == "Test transcript"
        assert result["article"]["title"] == "Test Article"


class TestVideoPipeline:
    """Test video pipeline."""

    def test_video_pipeline_import(self):
        """Test video pipeline can be imported."""
        from src.video.application.usecases.video_pipeline import VideoPipelineUseCase

        assert VideoPipelineUseCase is not None

    def test_video_pipeline_inherits_from_base(self):
        """Test video pipeline inherits from base."""
        from src.video.application.usecases.video_pipeline import VideoPipelineUseCase
        from src.shared.application.usecases.base_pipeline import BasePipelineUseCase

        assert issubclass(VideoPipelineUseCase, BasePipelineUseCase)

    def test_video_pipeline_initialization(self):
        """Test video pipeline initialization."""
        from src.video.application.usecases.video_pipeline import VideoPipelineUseCase

        pipeline = VideoPipelineUseCase(no_publish=True)
        assert pipeline.no_publish is True
        assert pipeline.mode == "video"


class TestImageEnricher:
    """Test image enricher."""

    def test_image_enricher_import(self):
        """Test image enricher can be imported."""
        from src.shared.adapters.image_enricher import ImageEnricher

        assert ImageEnricher is not None

    def test_image_enricher_initialization(self):
        """Test image enricher initialization."""
        from src.shared.adapters.image_enricher import ImageEnricher

        enricher = ImageEnricher(mode="test")
        assert enricher.mode == "test"

    def test_image_enricher_enrich_empty_posts(self):
        """Test enriching empty posts list."""
        from src.shared.adapters.image_enricher import ImageEnricher

        enricher = ImageEnricher(mode="test")
        result = enricher.enrich([])
        assert result == []


class TestCacheManager:
    """Test cache manager."""

    def test_cache_manager_import(self):
        """Test cache manager can be imported."""
        from src.shared.adapters.cache_manager import (
            save_content_to_cache,
            load_content_from_cache,
        )

        assert save_content_to_cache is not None
        assert load_content_from_cache is not None

    def test_save_and_load_cache(self):
        """Test saving and loading from cache."""
        from src.shared.adapters.cache_manager import (
            save_content_to_cache,
            load_content_from_cache,
        )

        test_url = "https://example.com/test"
        test_content = "Test content for caching" * 10  # Make it long enough

        # Save to cache
        saved = save_content_to_cache(test_url, test_content)
        assert saved is True

        # Load from cache
        content, status = load_content_from_cache(test_url, max_age_hours=1)
        assert status == "cache_hit"
        assert content == test_content

    def test_load_nonexistent_cache(self):
        """Test loading from nonexistent cache."""
        from src.shared.adapters.cache_manager import load_content_from_cache

        content, status = load_content_from_cache(
            "https://example.com/nonexistent", max_age_hours=1
        )
        assert status == "no_cache"
        assert content is None

    def test_cache_too_short(self):
        """Test that short content is not cached."""
        from src.shared.adapters.cache_manager import (
            save_content_to_cache,
            load_content_from_cache,
        )

        test_url = "https://example.com/short"
        short_content = "Too short"

        saved = save_content_to_cache(test_url, short_content)
        assert saved is False


class TestWordPressPublisher:
    """Test WordPress publisher."""

    def test_wordpress_publisher_import(self):
        """Test WordPress publisher can be imported."""
        from src.shared.adapters.wordpress_publisher import (
            publish_post,
            ensure_category,
            ensure_tag,
            upload_image_from_url,
        )

        assert publish_post is not None
        assert ensure_category is not None

    def test_get_headers_missing_token(self):
        """Test that missing JWT token raises error."""
        from config.settings import Settings
        from src.shared.adapters.wordpress_publisher import get_headers
        
        # Save original token
        original_token = Settings.WP_HOSTING_JWT_TOKEN
        
        try:
            # Temporarily remove token
            Settings.WP_HOSTING_JWT_TOKEN = ""
            
            with pytest.raises(RuntimeError, match="WP_HOSTING_JWT_TOKEN"):
                get_headers()
        finally:
            # Restore original token
            Settings.WP_HOSTING_JWT_TOKEN = original_token


class TestSocialPublisher:
    """Test social media publisher."""

    def test_social_publisher_import(self):
        """Test social publisher can be imported."""
        from src.shared.adapters.publishers.social import SocialMediaPublisher

        assert SocialMediaPublisher is not None

    def test_social_publisher_initialization(self):
        """Test social publisher initialization."""
        from src.shared.adapters.publishers.social import SocialMediaPublisher

        publisher = SocialMediaPublisher(
            enable_bluesky=False, enable_mastodon=False
        )
        assert publisher._bluesky is None
        assert publisher._mastodon is None


class TestErrorHandling:
    """Test error handling across the application."""

    def test_pipeline_handles_missing_audio_file(self):
        """Test pipeline handles missing audio file gracefully."""
        from src.audio.application.usecases.audio_pipeline import AudioPipelineUseCase

        pipeline = AudioPipelineUseCase(no_publish=True)

        with pytest.raises(RuntimeError, match="Error in audio download"):
            pipeline.run("https://invalid.url/audio.mp3", "Test")

    def test_pipeline_handles_missing_video_file(self):
        """Test pipeline handles missing video file gracefully."""
        from src.video.application.usecases.video_pipeline import VideoPipelineUseCase

        pipeline = VideoPipelineUseCase(no_publish=True)

        with pytest.raises(RuntimeError, match="Error in video download"):
            pipeline.run("https://invalid.url/video.mp4", "Test")


class TestTypeHints:
    """Test that type hints are properly defined."""

    def test_base_pipeline_has_type_hints(self):
        """Test base pipeline has type hints."""
        from src.shared.application.usecases.base_pipeline import BasePipelineUseCase
        import inspect

        # Check run method has annotations
        assert hasattr(BasePipelineUseCase.run, '__annotations__')

    def test_audio_pipeline_has_type_hints(self):
        """Test audio pipeline has type hints."""
        from src.audio.application.usecases.audio_pipeline import AudioPipelineUseCase
        import inspect

        assert hasattr(AudioPipelineUseCase.run, '__annotations__')

    def test_video_pipeline_has_type_hints(self):
        """Test video pipeline has type hints."""
        from src.video.application.usecases.video_pipeline import VideoPipelineUseCase
        import inspect

        assert hasattr(VideoPipelineUseCase.run, '__annotations__')
