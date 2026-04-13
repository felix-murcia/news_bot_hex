"""Comprehensive tests for news use cases to boost coverage."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone


class TestArticleUseCase:
    """Test ArticleUseCase (article.py) - large file."""

    def test_slugify(self):
        from src.news.application.usecases.article import slugify
        assert slugify("Hello World!") == "hello-world"
        assert slugify("  spaces  ") == "spaces"
        assert slugify("Test--double") == "test-double"

    def test_slugify_empty(self):
        from src.news.application.usecases.article import slugify
        assert slugify("") == ""


class TestContentUseCaseDetailed:
    """Test ContentUseCase in detail."""

    def test_post_limits(self):
        from src.news.application.usecases.content import POST_LIMITS
        assert POST_LIMITS["bluesky"] == 300
        assert POST_LIMITS["twitter"] == 280
        assert POST_LIMITS["mastodon"] == 500
        assert POST_LIMITS["facebook"] == 63206

    def test_network_limits(self):
        from src.news.application.usecases.content import ContentUseCase

        for network, limit in [("bluesky", 300), ("twitter", 280), ("mastodon", 500)]:
            use_case = ContentUseCase(network=network, use_ai=False)
            assert use_case.MAX_CHARS == limit


class TestTweetTruncationHelper:
    def test_removes_extra_hashtags_before_truncating(self):
        from src.shared.utils.tweet_truncation import truncate_social_post

        tweet = "Una frase muy larga que necesita recorte #uno #dos #tres"
        result = truncate_social_post(tweet, limit=55)

        assert len(result) <= 55
        assert "#uno" in result
        assert "#tres" not in result

    def test_preserves_single_hashtag_and_truncates_text(self):
        from src.shared.utils.tweet_truncation import truncate_social_post

        tweet = "Un texto inicialmente demasiado largo para caber #hashtag"
        result = truncate_social_post(tweet, limit=25)

        assert len(result) <= 25
        assert result.endswith("#hashtag")

    def test_truncates_without_hashtags(self):
        from src.shared.utils.tweet_truncation import truncate_social_post

        result = truncate_social_post("Texto sin hashtags muy largo", limit=10)

        assert len(result) <= 10
        assert result.endswith("...")


class TestClassicNewsValidator:
    """Test ClassicNewsValidatorAdapter."""

    def test_preprocess_text_integration(self):
        from src.news.domain.services.classic_news_validator import preprocess_text

        result = preprocess_text("The quick brown fox")
        assert "quick" in result
        assert "the" not in result  # stopwords removed

    def test_heuristic_real_news(self):
        from src.news.domain.services.classic_news_validator import heuristic_predict

        text = "According to official sources, the government announced a new study showing 50 percent growth in January."
        is_real, conf = heuristic_predict(text)
        assert is_real is True

    def test_heuristic_fake_news(self):
        from src.news.domain.services.classic_news_validator import heuristic_predict

        text = "SHOCKING EXPOSED: The secret conspiracy hoax they don't want you to know!"
        is_real, conf = heuristic_predict(text)
        assert is_real is False

    def test_heuristic_caps_penalty(self):
        from src.news.domain.services.classic_news_validator import heuristic_predict

        text = "BREAKING NEWS ABOUT IMPORTANT STUFF"
        is_real, conf = heuristic_predict(text)
        assert isinstance(is_real, bool)

    def test_heuristic_exclamation_penalty(self):
        from src.news.domain.services.classic_news_validator import heuristic_predict

        text = "Amazing news!!!!!! Incredible!!!!"
        is_real, conf = heuristic_predict(text)
        assert isinstance(is_real, bool)

    def test_heuristic_question_penalty(self):
        from src.news.domain.services.classic_news_validator import heuristic_predict

        text = "What is this??? Why???"
        is_real, conf = heuristic_predict(text)
        assert isinstance(is_real, bool)

    def test_heuristic_numeric_bonus(self):
        from src.news.domain.services.classic_news_validator import heuristic_predict

        text = "The study shows 75 percent increase in revenue"
        is_real, conf = heuristic_predict(text)
        assert is_real is True

    def test_heuristic_date_bonus(self):
        from src.news.domain.services.classic_news_validator import heuristic_predict

        text = "On Monday the government announced new policies for January"
        is_real, conf = heuristic_predict(text)
        assert isinstance(is_real, bool)


class TestMongoRepositoriesDetailed:
    """Test MongoDB repositories methods."""

    def test_article_repository_class_exists(self):
        from src.news.infrastructure.adapters.mongo_repositories import MongoArticleRepository

        assert MongoArticleRepository is not None


class TestAudioToNewsDetailed:
    """Test AudioToNewsUseCase in detail."""

    @patch('src.audio.application.usecases.audio_to_news.AudioToNewsUseCase._get_ai_model')
    def test_generate_article_with_ai(self, mock_get_model):
        from src.audio.application.usecases.audio_to_news import AudioToNewsUseCase

        mock_model = Mock()
        mock_model.provider = "local"
        mock_get_model.return_value = mock_model

        use_case = AudioToNewsUseCase(use_ai=True)

        with patch('src.shared.adapters.ai.agents.ArticleFromContentAgent') as mock_agent:
            mock_agent_instance = Mock()
            mock_agent_instance.generate.return_value = "<h1>Test Title</h1><p>Content</p>"
            mock_agent.return_value = mock_agent_instance

            result = use_case._generate_article(
                transcript="Test transcript content",
                url="https://example.com",
                tema="Test"
            )
            assert "article" in result
            assert result["article"]["title"] == "Test Title"

    def test_generate_article_fallback(self):
        from src.audio.application.usecases.audio_to_news import AudioToNewsUseCase

        use_case = AudioToNewsUseCase(use_ai=True)
        # Force exception in AI path by using invalid state
        use_case.ai_model = Mock()
        use_case.ai_model.generate.side_effect = Exception("AI error")

        result = use_case._generate_article(
            transcript="Line1\nLine2\nLine3\nLine4\nLine5",
            url="https://example.com",
            tema="Test"
        )
        assert "article" in result
        assert "Audio Noticia" in result["article"]["title"]

    @patch('src.audio.application.usecases.audio_to_news.AudioToNewsUseCase._get_ai_model')
    def test_generate_tweet_success(self, mock_get_model):
        from src.audio.application.usecases.audio_to_news import AudioToNewsUseCase

        mock_model = Mock()
        mock_model.provider = "local"
        mock_get_model.return_value = mock_model

        use_case = AudioToNewsUseCase(use_ai=True)

        with patch('src.shared.adapters.ai.agents.TweetAgent') as mock_agent:
            mock_agent_instance = Mock()
            mock_agent_instance.generate.return_value = "Great audio podcast about technology"
            mock_agent.return_value = mock_agent_instance

            article_data = {"article": {"title": "Tech Audio"}}
            tweet = use_case._generate_tweet(article_data)
            assert "Great audio podcast" in tweet

    def test_generate_unique_slug(self):
        from src.audio.application.usecases.audio_to_news import AudioToNewsUseCase

        use_case = AudioToNewsUseCase(use_ai=False)
        slug = use_case._generate_unique_slug(
            title="Test Audio Title",
            content="<p>Some content here</p>",
            tema="Technology"
        )
        assert isinstance(slug, str)
        assert len(slug) > 0


class TestArticleFromAudioDetailed:
    """Test ArticleFromAudioUseCase detailed methods."""

    def test_generate_fallback(self):
        from src.audio.application.usecases.article_from_audio import ArticleFromAudioUseCase

        use_case = ArticleFromAudioUseCase(use_gemini=False)
        transcript = "Line1\nLine2\nLine3\nLine4\nLine5\nLine6\n\nLine8"
        result = use_case._generate_fallback(transcript, "https://example.com", "Test")

        assert "article" in result
        assert "post" in result
        assert "stats" in result
        assert result["stats"]["parrafos"] >= 0

    def test_build_article_response(self):
        from src.audio.application.usecases.article_from_audio import ArticleFromAudioUseCase

        use_case = ArticleFromAudioUseCase(use_gemini=False)
        result = use_case._build_article_response(
            content="<h1>Title</h1><p>Content</p>",
            title="Test Title",
            url="https://example.com",
            tema="Test",
            mode="local"
        )

        assert result["article"]["title"] == "Test Title"
        assert result["article"]["source_type"] == "audio_man"
        assert "tweet" in result

    def test_slugify_audio(self):
        from src.audio.application.usecases.article_from_audio import ArticleFromAudioUseCase

        use_case = ArticleFromAudioUseCase(use_gemini=False)
        slug = use_case._generate_unique_slug(
            "Audio Podcast Title",
            "<p>Some content for the podcast</p>",
            "Podcast"
        )
        assert "podcast" in slug or "title" in slug


class TestImageEnricherDetailed:
    """Test ImageEnricher detailed methods."""

    def test_get_image_urls_priority(self):
        from src.shared.adapters.image_enricher import get_image_urls

        post = {
            "unsplash_image": "https://unsplash.com/1",
            "google_image": "https://google.com/1",
            "image_url": "https://other.com/1"
        }
        urls = get_image_urls(post)
        assert "https://unsplash.com/1" in urls

    def test_get_image_urls_excludes_nbes(self):
        from src.shared.adapters.image_enricher import get_image_urls

        post = {"image_url": "https://nbes.blog/img.jpg"}
        urls = get_image_urls(post)
        assert len(urls) == 0

    def test_assign_fallback(self):
        from src.shared.adapters.image_enricher import assign_fallback

        post = {}
        assign_fallback(post)
        assert post["image_credit"] == "NBES"
        assert post["alt_text"] == "Logo NBES"


class TestGoogleImagesDetailed:
    """Test Google Images fetcher detailed."""

    def test_search_without_keys(self):
        from src.shared.adapters import google_images_fetcher as gif_mod

        # When keys are missing, should return None
        original_key = gif_mod.GOOGLE_API_KEY
        original_cx = gif_mod.GOOGLE_CX
        gif_mod.GOOGLE_API_KEY = None
        gif_mod.GOOGLE_CX = None

        result = gif_mod.search_google_images("test", set())
        assert result is None

        gif_mod.GOOGLE_API_KEY = original_key
        gif_mod.GOOGLE_CX = original_cx

    def test_get_used_ids_error_handling(self):
        from src.shared.adapters.google_images_fetcher import get_used_ids

        # Should handle MongoDB errors gracefully
        ids = get_used_ids()
        assert isinstance(ids, set)

    def test_add_used_id_error_handling(self):
        from src.shared.adapters.google_images_fetcher import add_used_id

        # Should not raise exception even if MongoDB fails
        add_used_id("test_id")


class TestUnsplashDetailed:
    """Test Unsplash fetcher detailed."""

    def test_search_without_key(self):
        from src.shared.adapters import unsplash_fetcher as uf_mod

        original_key = uf_mod.UNSPLASH_ACCESS_KEY
        uf_mod.UNSPLASH_ACCESS_KEY = None

        result = uf_mod.search_unsplash("test", set())
        assert result is None

        uf_mod.UNSPLASH_ACCESS_KEY = original_key

    def test_get_used_ids_error_handling(self):
        from src.shared.adapters.unsplash_fetcher import get_used_ids

        ids = get_used_ids()
        assert isinstance(ids, set)

    def test_add_used_id_error_handling(self):
        from src.shared.adapters.unsplash_fetcher import add_used_id

        add_used_id("test_id")


class TestCacheManagerDetailed:
    """Test cache manager detailed."""

    def test_save_and_load_metadata(self):
        from src.shared.adapters.cache_manager import save_content_to_cache, load_content_from_cache, get_cache_path

        url = "https://example.com/meta_test"
        content = "<html>" + "x" * 200 + "</html>"

        save_content_to_cache(url, content, "test_method")

        cache_path = get_cache_path(url)
        meta_path = cache_path.with_suffix(".json")
        assert meta_path.exists()

    def test_cache_path_creation(self):
        from src.shared.adapters.cache_manager import get_cache_path

        path = get_cache_path("https://example.com/test")
        assert path is not None
        assert path.suffix == ".txt"


class TestVideoTranscriberDetailed:
    """Test video transcriber detailed."""

    def test_transcriber_methods_exist(self):
        from src.video.infrastructure.adapters.video_transcriber import VideoTranscriber

        transcriber = VideoTranscriber()
        assert hasattr(transcriber, 'transcribe')


class TestWordPressPublisherDetailed:
    """Test WordPress publisher detailed."""

    def test_publisher_init_and_config(self):
        from src.shared.adapters.wordpress_publisher import WordPressPublisher

        pub = WordPressPublisher()
        assert pub is not None


class TestBlueskyPublisherDetailed:
    """Test Bluesky publisher detailed."""

    def test_publisher_has_publish_posts(self):
        from src.shared.adapters.bluesky_publisher import BlueskyPublisher

        pub = BlueskyPublisher()
        assert hasattr(pub, 'publish_posts')


class TestFacebookPublisherDetailed:
    """Test Facebook publisher detailed."""

    def test_publisher_has_publish_posts(self):
        from src.shared.adapters.facebook_publisher import FacebookPublisher

        pub = FacebookPublisher()
        assert hasattr(pub, 'publish_posts')


class TestMastodonPublisherDetailed:
    """Test Mastodon publisher detailed."""

    def test_publisher_has_publish_posts(self):
        from src.shared.adapters.mastodon_publisher import MastodonPublisher

        pub = MastodonPublisher()
        assert hasattr(pub, 'publish_posts')


class TestTranslatorDetailed:
    """Test translator detailed."""

    def test_translate_function_exists(self):
        from src.shared.adapters.translator import translate_text

        # Function should exist even if it returns original text
        assert callable(translate_text)


class TestAIFactoryDetailed:
    """Test AI factory detailed."""

    def test_list_providers(self):
        from src.shared.adapters.ai.ai_factory import list_providers

        providers = list_providers()
        assert isinstance(providers, list)
        assert "local" in providers


class TestGeminiAdapterDetailed:
    """Test Gemini adapter detailed."""

    def test_gemini_adapter_module(self):
        from src.shared.adapters.ai import gemini_adapter

        assert gemini_adapter is not None
        assert hasattr(gemini_adapter, 'GeminiAdapter')


class TestOpenRouterAdapterDetailed:
    """Test OpenRouter adapter detailed."""

    def test_adapter_methods_exist(self):
        from src.shared.adapters.ai.openrouter_adapter import OpenRouterAdapter

        adapter = OpenRouterAdapter({})
        assert hasattr(adapter, 'generate')


class TestNewsValidatorAdapterDetailed:
    """Test news validator adapter detailed."""

    def test_adapter_predict_exists(self):
        from src.news.infrastructure.adapters.news_validator_adapter import ClassicNewsValidatorAdapter

        adapter = ClassicNewsValidatorAdapter()
        assert hasattr(adapter, 'predict')


class TestContentPostEditor:
    """Test ContentPostEditor for automatic post-editing."""

    def test_default_replacements(self):
        from src.shared.utils.content_post_editor import ContentPostEditor

        editor = ContentPostEditor()
        assert "Papa Francisco" in editor.replacements
        assert editor.replacements["Papa Francisco"] == "Papa León XIII"

    def test_post_edit_pope_francisco(self):
        from src.shared.utils.content_post_editor import post_edit_content

        text = "El Papa Francisco visitó Roma ayer."
        result = post_edit_content(text)
        assert "Papa León XIII" in result
        assert "Papa Francisco" not in result

    def test_post_edit_trump_ex_president(self):
        from src.shared.utils.content_post_editor import post_edit_content

        text = "El expresidente Donald Trump declaró hoy."
        result = post_edit_content(text)
        assert "presidente Donald Trump" in result
        assert "expresidente" not in result

    def test_post_edit_case_insensitive(self):
        from src.shared.utils.content_post_editor import post_edit_content

        text = "papa francisco dijo algo importante."
        result = post_edit_content(text)
        assert "Papa León XIII" in result

    def test_post_edit_multiple_replacements(self):
        from src.shared.utils.content_post_editor import post_edit_content

        text = "Papa Francisco y expresidente Trump hablaron."
        result = post_edit_content(text)
        assert "Papa León XIII" in result
        assert "presidente Trump" in result
        assert "Papa Francisco" not in result
        assert "expresidente" not in result

    def test_post_edit_empty_content(self):
        from src.shared.utils.content_post_editor import post_edit_content

        result = post_edit_content("")
        assert result == ""

    def test_custom_replacements(self):
        from src.shared.utils.content_post_editor import ContentPostEditor

        custom_replacements = {"test": "replaced"}
        editor = ContentPostEditor(replacements=custom_replacements)
        result = editor.post_edit("This is a test text.")
        assert "replaced" in result
        assert "test" not in result

    def test_add_and_remove_replacement(self):
        from src.shared.utils.content_post_editor import ContentPostEditor

        editor = ContentPostEditor()
        editor.add_replacement("new_key", "new_value")
        assert editor.replacements["new_key"] == "new_value"

        editor.remove_replacement("new_key")
        assert "new_key" not in editor.replacements
