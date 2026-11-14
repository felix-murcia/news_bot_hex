"""Tests for news application use cases."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from ai_helpers import build_ai_providers
from wp_helpers import build_wp_helpers
from image_helpers import build_image_providers


class TestNewsToNewsUseCase:
    """Test NewsToNewsUseCase."""

    @staticmethod
    def _n2n_kwargs(mock_extractor, mock_articles_repo, mock_posts_repo, **extra):
        kwargs = dict(
            ai_providers=build_ai_providers(),
            content_extractor=mock_extractor,
            generated_articles_repo=mock_articles_repo,
            generated_posts_repo=mock_posts_repo,
            social_truncator=lambda t, limit=None: t,
            post_editor=lambda c, editor=None: c,
            tts_text_processor=Mock(),
            cache_loader=Mock(return_value=(None, "no_cache")),
            cache_saver=Mock(return_value=True),
            translator=lambda text, target_lang="es": text,
        )
        kwargs.update(extra)
        return kwargs

    def test_init(self):
        from src.news.application.usecases.news_to_news import NewsToNewsUseCase
        from src.news.domain.ports import GeneratedArticlesRepository, GeneratedPostsRepository

        mock_extractor = Mock()
        mock_articles_repo = Mock(spec=GeneratedArticlesRepository)
        mock_posts_repo = Mock(spec=GeneratedPostsRepository)
        use_case = NewsToNewsUseCase(**self._n2n_kwargs(mock_extractor, mock_articles_repo, mock_posts_repo, use_ai=False))
        assert use_case.use_ai is False
        assert use_case.content_extractor is mock_extractor

    def test_init_with_video_generator(self):
        from src.news.application.usecases.news_to_news import NewsToNewsUseCase
        from src.shared.domain.ports.video_generator_port import VideoGeneratorPort
        from src.news.domain.ports import GeneratedArticlesRepository, GeneratedPostsRepository

        mock_extractor = Mock()
        mock_video_gen = Mock(spec=VideoGeneratorPort)
        mock_articles_repo = Mock(spec=GeneratedArticlesRepository)
        mock_posts_repo = Mock(spec=GeneratedPostsRepository)
        use_case = NewsToNewsUseCase(
            **self._n2n_kwargs(
                mock_extractor, mock_articles_repo, mock_posts_repo,
                use_ai=False, video_generator=mock_video_gen,
            )
        )
        assert use_case.video_generator is mock_video_gen

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

    def test_load_from_cache_hit(self):
        from src.news.application.usecases.news_to_news import NewsToNewsUseCase
        from src.news.domain.ports import GeneratedArticlesRepository, GeneratedPostsRepository

        mock_loader = Mock(return_value=("Cached content", "cache_hit"))
        mock_extractor = Mock()
        mock_articles_repo = Mock(spec=GeneratedArticlesRepository)
        mock_posts_repo = Mock(spec=GeneratedPostsRepository)
        use_case = NewsToNewsUseCase(
            **self._n2n_kwargs(
                mock_extractor,
                mock_articles_repo,
                mock_posts_repo,
                use_ai=False,
                cache_loader=mock_loader,
            )
        )

        result = use_case._load_from_cache("https://example.com")
        assert result is not None
        assert result[0] == "Cached content"
        mock_loader.assert_called_once_with("https://example.com", max_age_hours=24)

    def test_load_from_cache_miss(self):
        from src.news.application.usecases.news_to_news import NewsToNewsUseCase
        from src.news.domain.ports import GeneratedArticlesRepository, GeneratedPostsRepository

        mock_loader = Mock(return_value=(None, "no_cache"))
        mock_extractor = Mock()
        mock_articles_repo = Mock(spec=GeneratedArticlesRepository)
        mock_posts_repo = Mock(spec=GeneratedPostsRepository)
        use_case = NewsToNewsUseCase(
            **self._n2n_kwargs(
                mock_extractor,
                mock_articles_repo,
                mock_posts_repo,
                use_ai=False,
                cache_loader=mock_loader,
            )
        )

        result = use_case._load_from_cache("https://example.com")
        assert result is None

    def test_save_to_cache(self):
        from src.news.application.usecases.news_to_news import NewsToNewsUseCase
        from src.news.domain.ports import GeneratedArticlesRepository, GeneratedPostsRepository

        mock_saver = Mock(return_value=True)
        mock_extractor = Mock()
        mock_articles_repo = Mock(spec=GeneratedArticlesRepository)
        mock_posts_repo = Mock(spec=GeneratedPostsRepository)
        use_case = NewsToNewsUseCase(
            **self._n2n_kwargs(
                mock_extractor,
                mock_articles_repo,
                mock_posts_repo,
                use_ai=False,
                cache_saver=mock_saver,
            )
        )

        use_case._save_to_cache("https://example.com", "content")
        mock_saver.assert_called_once_with("https://example.com", "content", "news_to_news")


class TestContentUseCase:
    """Test ContentUseCase."""

    def test_init(self):
        from src.news.application.usecases.content import ContentUseCase
        from unittest.mock import Mock

        use_case = ContentUseCase(verified_repo=Mock(), generated_posts_repo=Mock(), ai_providers=build_ai_providers(), social_truncator=lambda t, limit=None: t, post_editor=lambda c, editor=None: c, cache_loader=Mock(return_value=(None, "no_cache")), network="bluesky", use_ai=False)
        assert use_case.network == "bluesky"
        assert use_case.use_ai is False
        assert use_case.MAX_CHARS == 300

    def test_init_twitter(self):
        from src.news.application.usecases.content import ContentUseCase
        from unittest.mock import Mock

        use_case = ContentUseCase(verified_repo=Mock(), generated_posts_repo=Mock(), ai_providers=build_ai_providers(), social_truncator=lambda t, limit=None: t, post_editor=lambda c, editor=None: c, cache_loader=Mock(return_value=(None, "no_cache")), network="twitter", use_ai=False)
        assert use_case.MAX_CHARS == 280

    def test_init_mastodon(self):
        from src.news.application.usecases.content import ContentUseCase
        from unittest.mock import Mock

        use_case = ContentUseCase(verified_repo=Mock(), generated_posts_repo=Mock(), ai_providers=build_ai_providers(), social_truncator=lambda t, limit=None: t, post_editor=lambda c, editor=None: c, cache_loader=Mock(return_value=(None, "no_cache")), network="mastodon", use_ai=False)
        assert use_case.MAX_CHARS == 500

    def test_init_facebook(self):
        from src.news.application.usecases.content import ContentUseCase
        from unittest.mock import Mock

        use_case = ContentUseCase(verified_repo=Mock(), generated_posts_repo=Mock(), ai_providers=build_ai_providers(), social_truncator=lambda t, limit=None: t, post_editor=lambda c, editor=None: c, cache_loader=Mock(return_value=(None, "no_cache")), network="facebook", use_ai=False)
        assert use_case.MAX_CHARS == 63206

    def test_validate_social_text_passes_clean_text(self):
        """Texto plano limpio pasa la validación."""
        from src.news.application.usecases.content import ContentUseCase
        from unittest.mock import Mock

        use_case = ContentUseCase(verified_repo=Mock(), generated_posts_repo=Mock(), ai_providers=build_ai_providers(), social_truncator=lambda t, limit=None: t, post_editor=lambda c, editor=None: c, cache_loader=Mock(return_value=(None, "no_cache")), network="bluesky", use_ai=False)
        
        clean_text = "El #BCE subió los #TiposDeInteres 25 puntos básicos. #Economía"
        result = use_case._validate_social_text(clean_text, "Título de prueba")
        assert result == clean_text

    def test_validate_social_text_fails_on_json(self):
        """JSON del LLM lanza ValueError."""
        from src.news.application.usecases.content import ContentUseCase
        from unittest.mock import Mock
        import pytest

        use_case = ContentUseCase(verified_repo=Mock(), generated_posts_repo=Mock(), ai_providers=build_ai_providers(), social_truncator=lambda t, limit=None: t, post_editor=lambda c, editor=None: c, cache_loader=Mock(return_value=(None, "no_cache")), network="bluesky", use_ai=False)
        
        with pytest.raises(ValueError, match="FAIL-FAST"):
            use_case._validate_social_text('{"publicable": true, "tweet": "Hola"}', "Título")

    def test_validate_social_text_fails_on_newline(self):
        """Saltos de línea lanzan ValueError."""
        from src.news.application.usecases.content import ContentUseCase
        from unittest.mock import Mock
        import pytest

        use_case = ContentUseCase(verified_repo=Mock(), generated_posts_repo=Mock(), ai_providers=build_ai_providers(), social_truncator=lambda t, limit=None: t, post_editor=lambda c, editor=None: c, cache_loader=Mock(return_value=(None, "no_cache")), network="bluesky", use_ai=False)
        
        with pytest.raises(ValueError, match="FAIL-FAST"):
            use_case._validate_social_text("Hola\nmundo", "Título")

    def test_validate_social_text_fails_on_html(self):
        """Etiquetas HTML lanzan ValueError."""
        from src.news.application.usecases.content import ContentUseCase
        from unittest.mock import Mock
        import pytest

        use_case = ContentUseCase(verified_repo=Mock(), generated_posts_repo=Mock(), ai_providers=build_ai_providers(), social_truncator=lambda t, limit=None: t, post_editor=lambda c, editor=None: c, cache_loader=Mock(return_value=(None, "no_cache")), network="bluesky", use_ai=False)
        
        with pytest.raises(ValueError, match="FAIL-FAST"):
            use_case._validate_social_text("<p>Hola</p>", "Título")

    def test_validate_social_text_fails_on_markdown(self):
        """Markdown (asteriscos, backticks) lanza ValueError."""
        from src.news.application.usecases.content import ContentUseCase
        from unittest.mock import Mock
        import pytest

        use_case = ContentUseCase(verified_repo=Mock(), generated_posts_repo=Mock(), ai_providers=build_ai_providers(), social_truncator=lambda t, limit=None: t, post_editor=lambda c, editor=None: c, cache_loader=Mock(return_value=(None, "no_cache")), network="bluesky", use_ai=False)
        
        with pytest.raises(ValueError, match="FAIL-FAST"):
            use_case._validate_social_text("**Bold** text", "Título")
        
        with pytest.raises(ValueError, match="FAIL-FAST"):
            use_case._validate_social_text("`code`", "Título")

    def test_validate_social_text_fails_on_pipes(self):
        """Pipes (tablas markdown) lanzan ValueError."""
        from src.news.application.usecases.content import ContentUseCase
        from unittest.mock import Mock
        import pytest

        use_case = ContentUseCase(verified_repo=Mock(), generated_posts_repo=Mock(), ai_providers=build_ai_providers(), social_truncator=lambda t, limit=None: t, post_editor=lambda c, editor=None: c, cache_loader=Mock(return_value=(None, "no_cache")), network="bluesky", use_ai=False)
        
        with pytest.raises(ValueError, match="FAIL-FAST"):
            use_case._validate_social_text("Col1 | Col2", "Título")

    def test_validate_social_text_fails_on_empty(self):
        """Texto vacío lanza ValueError."""
        from src.news.application.usecases.content import ContentUseCase
        from unittest.mock import Mock
        import pytest

        use_case = ContentUseCase(verified_repo=Mock(), generated_posts_repo=Mock(), ai_providers=build_ai_providers(), social_truncator=lambda t, limit=None: t, post_editor=lambda c, editor=None: c, cache_loader=Mock(return_value=(None, "no_cache")), network="bluesky", use_ai=False)
        
        with pytest.raises(ValueError, match="FAIL-FAST"):
            use_case._validate_social_text("", "Título")
        
        with pytest.raises(ValueError, match="FAIL-FAST"):
            use_case._validate_social_text("   ", "Título")

    def test_validate_social_text_allows_valid_hashtags(self):
        """Hashtags válidos (# al inicio o tras espacio) son permitidos."""
        from src.news.application.usecases.content import ContentUseCase
        from unittest.mock import Mock

        use_case = ContentUseCase(verified_repo=Mock(), generated_posts_repo=Mock(), ai_providers=build_ai_providers(), social_truncator=lambda t, limit=None: t, post_editor=lambda c, editor=None: c, cache_loader=Mock(return_value=(None, "no_cache")), network="bluesky", use_ai=False)
        
        # Hashtags válidos
        valid = "#Noticias importante #Economía hoy"
        result = use_case._validate_social_text(valid, "Título")
        assert result == valid
        
        # Hashtag al inicio
        valid2 = "#Primera noticia del día"
        result = use_case._validate_social_text(valid2, "Título")
        assert result == valid2

    def test_validate_social_text_rejects_invalid_hashtag(self):
        """# en medio de palabra (no hashtag válido) lanza ValueError."""
        from src.news.application.usecases.content import ContentUseCase
        from unittest.mock import Mock
        import pytest

        use_case = ContentUseCase(verified_repo=Mock(), generated_posts_repo=Mock(), ai_providers=build_ai_providers(), social_truncator=lambda t, limit=None: t, post_editor=lambda c, editor=None: c, cache_loader=Mock(return_value=(None, "no_cache")), network="bluesky", use_ai=False)
        
        with pytest.raises(ValueError, match="FAIL-FAST"):
            use_case._validate_social_text("Hola#mundo", "Título")
        
        with pytest.raises(ValueError, match="FAIL-FAST"):
            use_case._validate_social_text("test#hash", "Título")


class TestSoftVerifyUseCase:
    """Test SoftVerifyUseCase."""

    def test_module_exists(self):
        from src.news.application.usecases import soft_verify

        assert soft_verify is not None


class TestArticleFromNewsUseCase:
    """Test ArticleFromNewsUseCase."""

    def test_init(self):
        from src.news.application.usecases.article_from_news import (
            ArticleFromNewsUseCase,
        )

        use_case = ArticleFromNewsUseCase(ai_providers=build_ai_providers(), use_ai=False, social_truncator=lambda t, limit=None: t, post_editor=lambda c, editor=None: c, translator=lambda text, target_lang="es": text)
        assert use_case.use_ai is False

    def test_seo_slugify_from_article(self):
        """seo_optimizer.slugify (used by article pipeline)."""
        from src.shared.adapters.seo_optimizer import slugify as seo_slugify

        assert seo_slugify("Test Article Title") == "test-article-title"


class TestAudioToNewsUseCase:
    """Test AudioToNewsUseCase."""

    def test_init(self):
        from src.audio.application.usecases.audio_to_news import AudioToNewsUseCase

        use_case = AudioToNewsUseCase(debug_output_repo=Mock(), cache_dir=Path("/tmp"), wp_site_url="https://test.example", copyright_domains=[], download_audio=Mock(return_value="/tmp/fake.mp3"), transcribe_audio=Mock(return_value="transcript"), has_audio_stream=Mock(return_value=True), social_truncator=lambda t, limit=None: t, post_editor=lambda c, editor=None: c, ai_providers=build_ai_providers(), use_ai=False)
        assert use_case.use_ai is False

    def test_slugify(self):
        from src.audio.application.usecases.audio_to_news import slugify

        assert slugify("Test Audio Title") == "test-audio-title"

    def test_check_copyright(self):
        from config.settings import Settings
        from src.audio.application.usecases.audio_to_news import check_copyright

        result = check_copyright(
            "https://youtube.com/test", Settings.VIDEO_COPYRIGHT_DOMAINS
        )
        assert isinstance(result, bool)


class TestArticleFromAudioUseCase:
    """Test ArticleFromAudioUseCase (redirected to shared ArticleFromTranscriptUseCase)."""

    def test_init(self):
        from src.audio.application.usecases import ArticleFromAudioUseCase

        use_case = ArticleFromAudioUseCase(ai_providers=build_ai_providers(), llm_provider="mock", social_truncator=lambda t, limit=None: t, post_editor=lambda c, editor=None: c, context_enricher=lambda t, tema="": None)
        assert use_case.llm_provider == "mock"

    def test_slugify(self):
        from src.shared.application.usecases.article_from_transcript import _slugify

        assert _slugify("Test Audio") == "test-audio"


class TestAudioPipelineUseCase:
    """Test AudioPipelineUseCase with run method."""

    @patch("src.audio.application.usecases.audio_pipeline.ArticleFromTranscriptUseCase")
    def test_run_success(self, mock_article_uc_cls):
        from src.audio.application.usecases.audio_pipeline import AudioPipelineUseCase

        mock_fetcher = Mock()
        mock_fetcher.fetch.return_value = "/tmp/test.mp3"
        mock_transcriber = Mock()
        mock_transcriber.transcribe.return_value = "Test transcript"
        mock_article_uc = Mock()
        mock_article_uc.execute.return_value = {
            "article": {"title": "Test", "content": "<p>Content</p>"},
            "tweet": "Test tweet",
            "article_file": "/tmp/article.json",
        }
        mock_article_uc_cls.return_value = mock_article_uc

        pipeline = AudioPipelineUseCase(
            no_publish=True,
            video_generator=Mock(),
            audio_fetcher_factory=lambda: mock_fetcher,
            audio_transcriber_factory=lambda: mock_transcriber,
            tts_adapter_factory=lambda: Mock(text_to_speech=Mock(return_value=None), is_available=Mock(return_value=True)),
            audio_converter=Mock(),
            ai_providers=build_ai_providers(),
            social_truncator=lambda t, limit=None: t,
            post_editor=lambda c, editor=None: c,
            tts_text_processor=Mock(),
            context_enricher=lambda t, tema="": None,
            wp_helpers=build_wp_helpers(),
            image_providers=build_image_providers(),
            social_publisher=Mock(),
        )
        with patch.object(pipeline, "_enrich_with_images", side_effect=lambda arts: arts), \
             patch.object(pipeline, "_track_temp_file"):
            result = pipeline.run("https://example.com/audio", "Test")

        assert result["mode"] == "audio"
        assert result["transcript"] == "Test transcript"

    def test_run_download_failure(self):
        from src.audio.application.usecases.audio_pipeline import AudioPipelineUseCase

        mock_fetcher = Mock()
        mock_fetcher.fetch.return_value = None
        mock_transcriber = Mock()

        pipeline = AudioPipelineUseCase(
            no_publish=True,
            video_generator=Mock(),
            audio_fetcher_factory=lambda: mock_fetcher,
            audio_transcriber_factory=lambda: mock_transcriber,
            tts_adapter_factory=lambda: Mock(),
            audio_converter=Mock(),
            ai_providers=build_ai_providers(),
            social_truncator=lambda t, limit=None: t,
            post_editor=lambda c, editor=None: c,
            tts_text_processor=Mock(),
            context_enricher=lambda t, tema="": None,
            wp_helpers=build_wp_helpers(),
            image_providers=build_image_providers(),
            social_publisher=Mock(),
        )
        with pytest.raises(RuntimeError, match="Error in audio download"):
            pipeline.run("https://example.com/audio", "Test")


class TestMongoRepositories:
    """Test MongoDB repositories."""

    @patch("src.shared.adapters.mongo_db.get_database")
    def test_mongo_repository_init(self, mock_get_db):
        from src.news.infrastructure.adapters.mongo_repositories import (
            MongoArticleRepository,
        )

        mock_db = Mock()
        mock_db.__getitem__ = Mock(return_value=Mock())
        mock_get_db.return_value = mock_db
        repo = MongoArticleRepository()
        assert repo is not None


class TestNewsValidatorAdapter:
    """Test news validator adapter."""

    def test_class_exists(self):
        from src.news.infrastructure.adapters.news_validator_adapter import (
            ClassicNewsValidatorAdapter,
        )

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
        assert hasattr(validation_rules, "DEFAULT_VALIDATION_RULES")
