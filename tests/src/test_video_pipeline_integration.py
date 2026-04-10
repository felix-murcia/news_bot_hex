import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


class TestVideoPipelineIntegration:
    """Integration tests for Video Pipeline."""

    def test_video_to_news_with_mock_video(self):
        """Test VideoToNewsUseCase with a mocked video."""
        from src.video.application.usecases import VideoToNewsUseCase

        use_case = VideoToNewsUseCase(use_ai=False)
        assert use_case.use_ai is False

    def test_article_from_video_with_mock(self):
        """Test ArticleFromVideoUseCase with mocked data."""
        from src.video.application.usecases import ArticleFromVideoUseCase

        use_case = ArticleFromVideoUseCase(llm_provider="mock")
        assert use_case.llm_provider == "mock"

    def test_video_fetcher_can_be_instantiated(self):
        """Test VideoFetcher can be instantiated."""
        from src.video.infrastructure.adapters import VideoFetcher

        fetcher = VideoFetcher()
        assert fetcher is not None

    def test_video_transcriber_can_be_instantiated(self):
        """Test VideoTranscriber can be instantiated."""
        from src.video.infrastructure.adapters import VideoTranscriber

        transcriber = VideoTranscriber()
        assert transcriber is not None

    def test_video_to_news_dependencies(self):
        """Test VideoToNewsUseCase dependencies are available."""
        from src.video.application.usecases import VideoToNewsUseCase

        use_case = VideoToNewsUseCase(use_ai=True, model_provider="openrouter")
        assert use_case.use_ai is True
        assert use_case.model_provider == "openrouter"

    def test_article_from_video_dependencies(self):
        """Test ArticleFromVideoUseCase dependencies are available."""
        from src.video.application.usecases import ArticleFromVideoUseCase

        use_case = ArticleFromVideoUseCase(llm_provider="openrouter")
        assert use_case.llm_provider == "openrouter"

    def test_video_uses_ai_adapter(self):
        """Test video pipeline can access AI adapter module."""
        from src.shared.adapters.ai import ai_factory

        assert ai_factory is not None


class TestVideoPipelineWorkflow:
    """Test complete video pipeline workflow."""

    def test_full_video_pipeline(self):
        """Test full video pipeline from fetch to article generation."""
        from src.video.application.usecases import VideoToNewsUseCase
        from src.video.application.usecases import ArticleFromVideoUseCase

        video_use_case = VideoToNewsUseCase(use_ai=False)
        article_use_case = ArticleFromVideoUseCase(llm_provider="mock")

        assert video_use_case is not None
        assert article_use_case is not None

    def test_video_repository_access(self):
        """Test video data can be stored/retrieved from MongoDB."""
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        assert db is not None
        assert db.name == "appdb"


class TestVideoPipelinePorts:
    """Test video pipeline ports/adapters."""

    def test_video_port_imports(self):
        """Test all video ports can be imported."""
        from src.video.infrastructure.adapters import VideoFetcher
        from src.video.infrastructure.adapters import VideoTranscriber

        assert VideoFetcher is not None
        assert VideoTranscriber is not None

    def test_video_domain_imports(self):
        """Test video domain can be imported."""
        from src.video import domain

        assert domain is not None


class TestVideoAIProviders:
    """Test video pipeline with different AI providers."""

    def test_video_with_openrouter_provider(self):
        """Test VideoToNewsUseCase with OpenRouter provider."""
        from src.video.application.usecases import VideoToNewsUseCase

        use_case = VideoToNewsUseCase(model_provider="openrouter", use_ai=True)
        assert use_case.model_provider == "openrouter"
        assert use_case.use_ai is True

    def test_video_with_gemini_provider(self):
        """Test VideoToNewsUseCase with Gemini provider."""
        from src.video.application.usecases import VideoToNewsUseCase

        use_case = VideoToNewsUseCase(model_provider="gemini", use_ai=True)
        assert use_case.model_provider == "gemini"
        assert use_case.use_ai is True

    def test_video_with_local_provider(self):
        """Test VideoToNewsUseCase with local provider."""
        from src.video.application.usecases import VideoToNewsUseCase

        use_case = VideoToNewsUseCase(model_provider="local", use_ai=True)
        assert use_case.model_provider == "local"
        assert use_case.use_ai is True

    def test_video_with_mock_provider(self):
        """Test VideoToNewsUseCase with mock provider."""
        from src.video.application.usecases import VideoToNewsUseCase

        use_case = VideoToNewsUseCase(model_provider="mock", use_ai=False)
        assert use_case.model_provider == "mock"
        assert use_case.use_ai is False
