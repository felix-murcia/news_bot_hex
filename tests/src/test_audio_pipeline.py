import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from config.settings import Settings

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


class TestAudioFetcher:
    """Test AudioFetcher functionality."""

    def test_audio_fetcher_init(self):
        """Test AudioFetcher initialization."""
        from src.audio.infrastructure.adapters import AudioFetcher

        fetcher = AudioFetcher()
        assert fetcher is not None

    def test_extract_audio_id_youtube_watch(self):
        """Test extract audio ID from YouTube watch URL."""
        from src.audio.infrastructure.adapters.audio_fetcher import extract_audio_id

        assert extract_audio_id("https://www.youtube.com/watch?v=abc123") == "abc123"

    def test_extract_audio_id_rtve(self):
        """Test extract audio ID from RTVE URL."""
        from src.audio.infrastructure.adapters.audio_fetcher import extract_audio_id

        assert (
            extract_audio_id("https://www.rtve.es/play/audios/24-horas/test/17016782/")
            == "17016782"
        )

    def test_is_direct_audio_url(self):
        """Test is_direct_audio_url detection."""
        from src.audio.infrastructure.adapters.audio_fetcher import is_direct_audio_url

        assert is_direct_audio_url("https://example.com/audio.mp3") is True
        assert is_direct_audio_url("https://example.com/audio.m4a") is True
        assert is_direct_audio_url("https://example.com/video.mp4") is False
        assert is_direct_audio_url("https://example.com/page.html") is False

    def test_is_rtve_url(self):
        """Test RTVE URL detection."""
        from src.audio.infrastructure.adapters.audio_fetcher import _is_rtve_url

        assert _is_rtve_url("https://www.rtve.es/play/audios/test") is True
        assert _is_rtve_url("https://rtve.es/audio/test") is True
        assert _is_rtve_url("https://youtube.com/watch?v=test") is False


class TestAudioToNewsUseCase:
    """Test AudioToNewsUseCase functionality."""

    def test_audio_to_news_use_case_init(self):
        """Test AudioToNewsUseCase initialization."""
        from src.audio.application.usecases import AudioToNewsUseCase

        use_case = AudioToNewsUseCase(model_provider=Settings.AI_PROVIDER)
        assert use_case.model_provider == Settings.AI_PROVIDER


class TestArticleFromAudioUseCase:
    """Test ArticleFromAudioUseCase functionality."""

    def test_article_from_audio_use_case_init(self):
        """Test ArticleFromAudioUseCase initialization."""
        from src.audio.application.usecases import ArticleFromAudioUseCase

        use_case = ArticleFromAudioUseCase(llm_provider=Settings.AI_PROVIDER)
        assert use_case.llm_provider == Settings.AI_PROVIDER


class TestAudioTranscriber:
    """Test AudioTranscriber functionality."""

    def test_audio_transcriber_init(self):
        """Test AudioTranscriber initialization."""
        from src.audio.infrastructure.adapters import AudioTranscriber

        transcriber = AudioTranscriber()
        assert transcriber is not None


class TestAudioPipeline:
    """Test Audio Pipeline integration."""

    def test_audio_pipeline_end_to_end(self):
        """Test complete audio pipeline."""
        from src.audio.application.usecases import AudioToNewsUseCase
        from src.audio.application.usecases import ArticleFromAudioUseCase

        use_case = AudioToNewsUseCase(use_ai=False)
        assert use_case is not None

        article_use_case = ArticleFromAudioUseCase(llm_provider=Settings.AI_PROVIDER)
        assert article_use_case is not None


class TestAudioUseCases:
    """Test Audio use cases imports."""

    def test_import_audio_to_news(self):
        """Test AudioToNewsUseCase can be imported."""
        from src.audio.application.usecases import AudioToNewsUseCase

        assert AudioToNewsUseCase is not None

    def test_import_article_from_audio(self):
        """Test ArticleFromAudioUseCase can be imported."""
        from src.audio.application.usecases import ArticleFromAudioUseCase

        assert ArticleFromAudioUseCase is not None

    def test_import_audio_fetcher(self):
        """Test AudioFetcher can be imported."""
        from src.audio.infrastructure.adapters import AudioFetcher

        assert AudioFetcher is not None

    def test_import_audio_transcriber(self):
        """Test AudioTranscriber can be imported."""
        from src.audio.infrastructure.adapters import AudioTranscriber

        assert AudioTranscriber is not None

    def test_import_audio_pipeline(self):
        """Test AudioPipelineUseCase can be imported."""
        from src.audio.application.usecases import AudioPipelineUseCase

        assert AudioPipelineUseCase is not None


class TestAudioPipelineUseCase:
    """Test AudioPipelineUseCase functionality."""

    def test_audio_pipeline_init(self):
        """Test AudioPipelineUseCase initialization."""
        from src.audio.application.usecases import AudioPipelineUseCase

        pipeline = AudioPipelineUseCase(no_publish=True)
        assert pipeline.no_publish is True
        assert pipeline._image_enricher is None
        assert pipeline._social_publisher is None

    def test_audio_pipeline_with_publish(self):
        """Test AudioPipelineUseCase with publish enabled."""
        from src.audio.application.usecases import AudioPipelineUseCase

        pipeline = AudioPipelineUseCase(no_publish=False)
        assert pipeline.no_publish is False
