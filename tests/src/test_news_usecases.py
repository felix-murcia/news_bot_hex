"""Tests for news application use cases."""
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestNewsToNewsUseCase:
    """Test NewsToNewsUseCase."""

    def test_init(self):
        from src.news.application.usecases.news_to_news import NewsToNewsUseCase

        mock_extractor = Mock()
        use_case = NewsToNewsUseCase(
            content_extractor=mock_extractor, use_ai=False
        )
        assert use_case.use_ai is False
        assert use_case.content_extractor is mock_extractor

    def test_slugify(self):
        from src.news.application.usecases.news_to_news import slugify

        assert slugify("Hello World") == "hello-world"
        assert slugify("  Multiple   spaces  ") == "multiple-spaces"
        assert slugify("Special!@#chars") == "specialchars"

    def test_check_copyright(self):
        from src.news.application.usecases.news_to_news import check_copyright

        # Test with typical copyright domains
        result = check_copyright("https://youtube.com/watch?v=test")
        assert isinstance(result, bool)

    @patch('src.shared.adapters.cache_manager.load_content_from_cache')
    def test_load_from_cache_hit(self, mock_load):
        from src.news.application.usecases.news_to_news import NewsToNewsUseCase

        mock_load.return_value = ("Cached content", "cache_hit")
        mock_extractor = Mock()
        use_case = NewsToNewsUseCase(content_extractor=mock_extractor, use_ai=False)

        result = use_case._load_from_cache("https://example.com")
        assert result is not None

    @patch('src.shared.adapters.cache_manager.load_content_from_cache')
    def test_load_from_cache_miss(self, mock_load):
        from src.news.application.usecases.news_to_news import NewsToNewsUseCase

        mock_load.return_value = (None, "no_cache")
        mock_extractor = Mock()
        use_case = NewsToNewsUseCase(content_extractor=mock_extractor, use_ai=False)

        result = use_case._load_from_cache("https://example.com")
        assert result is None

    @patch('src.shared.adapters.cache_manager.save_content_to_cache')
    def test_save_to_cache(self, mock_save):
        from src.news.application.usecases.news_to_news import NewsToNewsUseCase

        mock_save.return_value = True
        mock_extractor = Mock()
        use_case = NewsToNewsUseCase(content_extractor=mock_extractor, use_ai=False)

        use_case._save_to_cache("https://example.com", "content")
        mock_save.assert_called_once()


class TestContentUseCase:
    """Test ContentUseCase."""

    def test_init(self):
        from src.news.application.usecases.content import ContentUseCase

        use_case = ContentUseCase(network="bluesky", use_ai=False)
        assert use_case.network == "bluesky"
        assert use_case.use_ai is False
        assert use_case.MAX_CHARS == 300

    def test_init_twitter(self):
        from src.news.application.usecases.content import ContentUseCase

        use_case = ContentUseCase(network="twitter", use_ai=False)
        assert use_case.MAX_CHARS == 280

    def test_init_mastodon(self):
        from src.news.application.usecases.content import ContentUseCase

        use_case = ContentUseCase(network="mastodon", use_ai=False)
        assert use_case.MAX_CHARS == 500

    def test_init_facebook(self):
        from src.news.application.usecases.content import ContentUseCase

        use_case = ContentUseCase(network="facebook", use_ai=False)
        assert use_case.MAX_CHARS == 63206


class TestSoftVerifyUseCase:
    """Test SoftVerifyUseCase."""

    def test_module_exists(self):
        from src.news.application.usecases import soft_verify

        assert soft_verify is not None


class TestArticleFromNewsUseCase:
    """Test ArticleFromNewsUseCase."""

    def test_init(self):
        from src.news.application.usecases.article_from_news import ArticleFromNewsUseCase

        use_case = ArticleFromNewsUseCase(use_ai=False)
        assert use_case.use_ai is False

    def test_slugify_from_article(self):
        from src.news.application.usecases.article import slugify

        assert slugify("Test Article Title") == "test-article-title"


class TestAudioToNewsUseCase:
    """Test AudioToNewsUseCase."""

    def test_init(self):
        from src.audio.application.usecases.audio_to_news import AudioToNewsUseCase

        use_case = AudioToNewsUseCase(use_ai=False)
        assert use_case.use_ai is False

    def test_slugify(self):
        from src.audio.application.usecases.audio_to_news import slugify

        assert slugify("Test Audio Title") == "test-audio-title"

    def test_check_copyright(self):
        from src.audio.application.usecases.audio_to_news import check_copyright

        result = check_copyright("https://youtube.com/test")
        assert isinstance(result, bool)


class TestArticleFromAudioUseCase:
    """Test ArticleFromAudioUseCase."""

    def test_init(self):
        from src.audio.application.usecases.article_from_audio import ArticleFromAudioUseCase

        use_case = ArticleFromAudioUseCase(use_gemini=False)
        assert use_case.use_gemini is False

    def test_execute_fallback(self):
        from src.audio.application.usecases.article_from_audio import ArticleFromAudioUseCase

        use_case = ArticleFromAudioUseCase(use_gemini=False)
        result = use_case.execute(
            transcript="Line 1\nLine 2\nLine 3",
            url="https://example.com",
            tema="Test"
        )
        assert "article" in result
        assert "post" in result
        assert "tweet" in result

    def test_slugify(self):
        from src.audio.application.usecases.article_from_audio import slugify

        assert slugify("Test Audio") == "test-audio"


class TestAudioPipelineUseCase:
    """Test AudioPipelineUseCase with run method."""

    @patch('src.audio.application.usecases.audio_pipeline.run_from_audio')
    @patch('src.audio.infrastructure.adapters.audio_transcriber.transcribe_audio')
    @patch('src.audio.infrastructure.adapters.audio_fetcher.has_audio_stream')
    @patch('src.audio.infrastructure.adapters.audio_fetcher.download_audio')
    def test_run_success(self, mock_download, mock_has_stream, mock_transcribe, mock_run_article):
        from src.audio.application.usecases.audio_pipeline import AudioPipelineUseCase

        mock_download.return_value = "/tmp/test.mp3"
        mock_has_stream.return_value = True
        mock_transcribe.return_value = "Test transcript"
        mock_run_article.return_value = {
            "article": {"title": "Test", "content": "<p>Content</p>"},
            "tweet": "Test tweet",
            "article_file": "/tmp/article.json",
        }

        pipeline = AudioPipelineUseCase(no_publish=True)
        result = pipeline.run("https://example.com/audio", "Test")

        assert result["mode"] == "audio"
        assert result["transcript"] == "Test transcript"

    @patch('src.audio.infrastructure.adapters.audio_fetcher.download_audio')
    def test_run_download_failure(self, mock_download):
        from src.audio.application.usecases.audio_pipeline import AudioPipelineUseCase

        mock_download.return_value = None

        pipeline = AudioPipelineUseCase(no_publish=True)
        with pytest.raises(RuntimeError, match="Error in audio download"):
            pipeline.run("https://example.com/audio", "Test")


class TestMongoRepositories:
    """Test MongoDB repositories."""

    @patch('src.shared.adapters.mongo_db.get_database')
    def test_mongo_repository_init(self, mock_get_db):
        from src.news.infrastructure.adapters.mongo_repositories import MongoArticleRepository

        mock_db = Mock()
        mock_db.__getitem__ = Mock(return_value=Mock())
        mock_get_db.return_value = mock_db
        repo = MongoArticleRepository()
        assert repo is not None


class TestNewsValidatorAdapter:
    """Test news validator adapter."""

    def test_class_exists(self):
        from src.news.infrastructure.adapters.news_validator_adapter import ClassicNewsValidatorAdapter

        assert ClassicNewsValidatorAdapter is not None


class TestTemplateRenderer:
    """Test template renderer."""

    def test_import(self):
        from src.news.domain.services.template_renderer import TemplateRenderer

        assert TemplateRenderer is not None


class TestValidationRules:
    """Test validation rules."""

    def test_module_exists(self):
        from src.news.domain.services import validation_rules

        assert validation_rules is not None
        assert hasattr(validation_rules, 'DEFAULT_VALIDATION_RULES')
