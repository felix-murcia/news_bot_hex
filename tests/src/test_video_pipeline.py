import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from config.settings import Settings

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


class TestVideoFetcher:
    """Test VideoFetcher functionality."""

    def test_video_fetcher_init(self):
        """Test VideoFetcher initialization."""
        from src.video.infrastructure.adapters import VideoFetcher

        fetcher = VideoFetcher()
        assert fetcher is not None


class TestVideoToNewsUseCase:
    """Test VideoToNewsUseCase functionality."""

    def test_video_to_news_use_case_init(self):
        """Test VideoToNewsUseCase initialization."""
        from src.video.application.usecases import VideoToNewsUseCase

        use_case = VideoToNewsUseCase(use_ai=True, model_provider=Settings.AI_PROVIDER)
        assert use_case.use_ai is True
        assert use_case.model_provider == Settings.AI_PROVIDER

    def test_check_copyright(self):
        """Test copyright check function."""
        from src.video.application.usecases.video_to_news import check_copyright

        assert check_copyright("https://youtube.com/watch?v=123") is True
        assert check_copyright("https://youtu.be/abc") is True
        assert check_copyright("https://tiktok.com/@user/video/123") is True
        assert check_copyright("https://example.com/article") is False

    def test_slugify(self):
        """Test slugify function."""
        from src.video.application.usecases.video_to_news import slugify

        assert slugify("Test Video Title") == "test-video-title"
        assert slugify("Video with 123 Numbers") == "video-with-123-numbers"
        assert slugify("Special!@#Characters") == "specialcharacters"


class TestArticleFromVideoUseCase:
    """Test ArticleFromVideoUseCase functionality."""

    def test_article_from_video_use_case_init(self):
        """Test ArticleFromVideoUseCase initialization."""
        from src.video.application.usecases import ArticleFromVideoUseCase

        use_case = ArticleFromVideoUseCase(llm_provider="gemini")

        assert use_case.llm_provider == "gemini"


class TestVideoTranscriber:
    """Test VideoTranscriber functionality."""

    def test_video_transcriber_init(self):
        """Test VideoTranscriber initialization."""
        from src.video.infrastructure.adapters import VideoTranscriber

        transcriber = VideoTranscriber()
        assert transcriber is not None


class TestVideoPipeline:
    """Test Video Pipeline integration."""

    def test_video_pipeline_end_to_end(self):
        """Test complete video pipeline."""
        from src.video.application.usecases import VideoToNewsUseCase
        from src.video.application.usecases import ArticleFromVideoUseCase

        use_case = VideoToNewsUseCase(use_ai=False)
        assert use_case is not None

        article_use_case = ArticleFromVideoUseCase(llm_provider="mock")
        assert article_use_case is not None


class TestVideoUseCases:
    """Test Video use cases imports."""

    def test_import_video_to_news(self):
        """Test VideoToNewsUseCase can be imported."""
        from src.video.application.usecases import VideoToNewsUseCase

        assert VideoToNewsUseCase is not None

    def test_import_article_from_video(self):
        """Test ArticleFromVideoUseCase can be imported."""
        from src.video.application.usecases import ArticleFromVideoUseCase

        assert ArticleFromVideoUseCase is not None

    def test_import_video_fetcher(self):
        """Test VideoFetcher can be imported."""
        from src.video.infrastructure.adapters import VideoFetcher

        assert VideoFetcher is not None

    def test_import_video_transcriber(self):
        """Test VideoTranscriber can be imported."""
        from src.video.infrastructure.adapters import VideoTranscriber

        assert VideoTranscriber is not None
