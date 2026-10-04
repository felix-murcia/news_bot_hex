"""Tests de la Tanda 1 de optimización del pipeline: F3, F6, F8, F9.

- F3: video_path se propaga a generated_posts (Facebook lee post["video_path"]).
- F6: caché de keywords LLM en image_query_generator (2ª llamada = hit).
- F8: caché del cliente Bluesky (login una vez por proceso).
- F9: caché de categorías/tags WordPress (2ª llamada = sin REST GET).

Los tests de caché limpian el caché de módulo antes y después de cada caso
para que no haya estado residual entre tests.
"""

import pytest
from unittest.mock import MagicMock, Mock, call, patch


# ─── F6: caché de keywords LLM (image_query_generator) ────────────────────


class TestKeywordsCache:
    """F6: generar_keywords_visuales_con_llm cachea el éxito del LLM."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        from src.shared.adapters import image_query_generator

        image_query_generator._KEYWORDS_CACHE.clear()
        yield
        image_query_generator._KEYWORDS_CACHE.clear()

    def test_second_call_is_cache_hit(self):
        """La 2ª llamada con el mismo title+content no repite la llamada LLM."""
        from src.shared.adapters.image_query_generator import (
            generar_keywords_visuales_con_llm,
        )

        mock_model = Mock()
        mock_model.generate.return_value = "Gaza, bombing, explosion"

        with patch(
            "src.shared.adapters.ai.ai_factory.get_ai_adapter",
            return_value=mock_model,
        ):
            first = generar_keywords_visuales_con_llm("Título", "contenido")
            second = generar_keywords_visuales_con_llm("Título", "contenido")

        assert first == ["Gaza", "bombing", "explosion"]
        assert second == first
        assert mock_model.generate.call_count == 1

    def test_failure_is_not_cached(self):
        """Si el LLM falla, la siguiente llamada reintenta (sin caché negativa)."""
        from src.shared.adapters.image_query_generator import (
            generar_keywords_visuales_con_llm,
        )

        mock_model = Mock()
        mock_model.generate.side_effect = [RuntimeError("boom"), "Gaza, bombing"]

        with patch(
            "src.shared.adapters.ai.ai_factory.get_ai_adapter",
            return_value=mock_model,
        ):
            first = generar_keywords_visuales_con_llm("Título", "contenido")
            second = generar_keywords_visuales_con_llm("Título", "contenido")

        assert first is None
        assert second == ["Gaza", "bombing"]
        assert mock_model.generate.call_count == 2

    def test_empty_title_returns_none_without_llm(self):
        """Sin título no hay llamada LLM ni caché."""
        from src.shared.adapters.image_query_generator import (
            generar_keywords_visuales_con_llm,
        )

        with patch("src.shared.adapters.ai.ai_factory.get_ai_adapter") as mock_factory:
            assert generar_keywords_visuales_con_llm("") is None
            mock_factory.assert_not_called()


# ─── F8: caché del cliente Bluesky ────────────────────────────────────────


class TestBlueskyClientCache:
    """F8: get_client() autentica una sola vez por proceso."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        from src.shared.adapters import bluesky_publisher

        bluesky_publisher._client_cache = None
        yield
        bluesky_publisher._client_cache = None

    def test_client_is_cached(self):
        """La 2ª llamada reutiliza el cliente: Client() y login() una sola vez."""
        from src.shared.adapters import bluesky_publisher

        mock_client = Mock()
        with patch.object(bluesky_publisher, "HANDLE", "test.bsky.social"), \
             patch.object(bluesky_publisher, "PASSWORD", "test-password"), \
             patch.object(bluesky_publisher, "Client", return_value=mock_client) as mock_cls:
            first = bluesky_publisher.get_client()
            second = bluesky_publisher.get_client()

        assert first is second
        assert mock_cls.call_count == 1
        mock_client.login.assert_called_once_with("test.bsky.social", "test-password")

    def test_missing_credentials_raise(self):
        """Sin credenciales, get_client() lanza ValueError (sin caché)."""
        from src.shared.adapters import bluesky_publisher

        with patch.object(bluesky_publisher, "HANDLE", ""), \
             patch.object(bluesky_publisher, "PASSWORD", ""):
            with pytest.raises(ValueError, match="Credenciales"):
                bluesky_publisher.get_client()


# ─── F9: caché de categorías/tags WordPress ───────────────────────────────


class TestWordPressCategoryTagCache:
    """F9: ensure_category/ensure_tag cachean la resolución exitosa."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        from src.shared.adapters import wordpress_publisher

        wordpress_publisher._CATEGORY_CACHE.clear()
        wordpress_publisher._TAG_CACHE.clear()
        yield
        wordpress_publisher._CATEGORY_CACHE.clear()
        wordpress_publisher._TAG_CACHE.clear()

    def test_ensure_category_second_call_is_hit(self):
        """La 2ª llamada con la misma categoría no hace REST GET."""
        from src.shared.adapters import wordpress_publisher

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"id": 42}]

        with patch.object(wordpress_publisher, "get_headers", return_value={}), \
             patch.object(wordpress_publisher, "rest_url", return_value="http://wp.test/wp/v2"), \
             patch("src.shared.adapters.wordpress_publisher._wp_session.get",
                   return_value=mock_resp) as mock_get:
            first = wordpress_publisher.ensure_category("Noticias")
            second = wordpress_publisher.ensure_category("Noticias")

        assert first == 42
        assert second == 42
        assert mock_get.call_count == 1

    def test_ensure_tag_second_call_is_hit(self):
        """La 2ª llamada con el mismo tag no hace REST GET."""
        from src.shared.adapters import wordpress_publisher

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"id": 7}]

        with patch.object(wordpress_publisher, "get_headers", return_value={}), \
             patch.object(wordpress_publisher, "rest_url", return_value="http://wp.test/wp/v2"), \
             patch("src.shared.adapters.wordpress_publisher._wp_session.get",
                   return_value=mock_resp) as mock_get:
            first = wordpress_publisher.ensure_tag("Economía")
            second = wordpress_publisher.ensure_tag("Economía")

        assert first == 7
        assert second == 7
        assert mock_get.call_count == 1

    def test_ensure_category_failure_not_cached(self):
        """Si el REST falla, la siguiente llamada reintenta (sin caché negativa)."""
        from src.shared.adapters import wordpress_publisher

        with patch.object(wordpress_publisher, "get_headers", return_value={}), \
             patch.object(wordpress_publisher, "rest_url", return_value="http://wp.test/wp/v2"), \
             patch("src.shared.adapters.wordpress_publisher._wp_session.get",
                   side_effect=Exception("boom")) as mock_get, \
             patch("src.shared.adapters.wordpress_publisher._wp_session.post",
                   side_effect=Exception("boom")):
            first = wordpress_publisher.ensure_category("Noticias")
            second = wordpress_publisher.ensure_category("Noticias")

        assert first is None
        assert second is None
        assert mock_get.call_count == 2


# ─── F3: video_path → generated_posts (Facebook) ──────────────────────────


class TestVideoPathPropagation:
    """F3: generate_video escribe video_path en generated_posts por url."""

    def test_video_path_propagated_to_generated_posts(self, tmp_path):
        """Al generar el video, generated_posts recibe video_path (lo lee Facebook)."""
        from src.news.application.usecases.process_url_pipeline import ProcessUrlPipeline

        audio_file = tmp_path / "audio.mp3"
        audio_file.write_bytes(b"fake audio")

        articles = [
            {
                "_id": 1,
                "original_url": "https://example.com/news/1",
                "tts_audio_path": str(audio_file),
            }
        ]

        articles_coll = Mock()
        articles_coll.find.return_value = iter(articles)
        posts_coll = Mock()
        posts_coll.find_one.return_value = {"tweet": "tweet de prueba"}

        mock_db = MagicMock()
        mock_db.__getitem__.side_effect = {
            "generated_articles": articles_coll,
            "generated_posts": posts_coll,
        }.get

        extractor = Mock()
        extractor.extract.return_value = ("x" * 200, "meta", "")

        pipeline = ProcessUrlPipeline(content_extractor=extractor)

        video_gen = Mock()
        video_gen.is_available.return_value = True
        video_gen.create_video_from_audio.return_value = "/tmp/video.mp4"

        with patch("src.shared.adapters.mongo_db.get_database", return_value=mock_db), \
             patch("src.news.infrastructure.adapters.MongoVerifiedNewsRepository"), \
             patch("src.news.application.usecases.content.run_content"), \
             patch("src.news.application.usecases.article.run"), \
             patch("src.shared.infrastructure.composition_root.run_image_unsplash"), \
             patch("src.shared.infrastructure.composition_root.run_image_google"), \
             patch("src.shared.infrastructure.composition_root.run_image_enricher"), \
             patch(
                 "src.shared.application.usecases.tts_from_article.run_tts_from_articles",
                 side_effect=lambda arts: arts,
             ), \
             patch(
                 "src.shared.infrastructure.composition_root.create_video_generator",
                 return_value=video_gen,
             ), \
             patch("src.shared.infrastructure.composition_root.run_wordpress"), \
             patch("src.shared.infrastructure.composition_root.run_bluesky"), \
             patch("src.shared.infrastructure.composition_root.run_mastodon"), \
             patch("src.shared.infrastructure.composition_root.run_facebook"):
            result = pipeline.execute("https://example.com/news/1")

        # F3: video_path escrito en generated_posts indexado por url
        posts_coll.update_one.assert_called_once_with(
            {"url": "https://example.com/news/1"},
            {"$set": {"video_path": "/tmp/video.mp4"}},
        )
        # generated_articles también recibe generated_video_path
        assert call(
            {"_id": 1}, {"$set": {"generated_video_path": "/tmp/video.mp4"}}
        ) in articles_coll.update_one.call_args_list
        assert result["post"] == "tweet de prueba"

    def test_no_video_when_generator_unavailable(self, tmp_path):
        """Si el generador no está disponible, no se escribe video_path en posts."""
        from src.news.application.usecases.process_url_pipeline import ProcessUrlPipeline

        audio_file = tmp_path / "audio.mp3"
        audio_file.write_bytes(b"fake audio")

        articles = [
            {
                "_id": 1,
                "original_url": "https://example.com/news/1",
                "tts_audio_path": str(audio_file),
            }
        ]

        articles_coll = Mock()
        articles_coll.find.return_value = iter(articles)
        posts_coll = Mock()
        posts_coll.find_one.return_value = {"tweet": "tweet"}

        mock_db = MagicMock()
        mock_db.__getitem__.side_effect = {
            "generated_articles": articles_coll,
            "generated_posts": posts_coll,
        }.get

        extractor = Mock()
        extractor.extract.return_value = ("x" * 200, "meta", "")

        pipeline = ProcessUrlPipeline(content_extractor=extractor)

        video_gen = Mock()
        video_gen.is_available.return_value = False

        with patch("src.shared.adapters.mongo_db.get_database", return_value=mock_db), \
             patch("src.news.infrastructure.adapters.MongoVerifiedNewsRepository"), \
             patch("src.news.application.usecases.content.run_content"), \
             patch("src.news.application.usecases.article.run"), \
             patch("src.shared.infrastructure.composition_root.run_image_unsplash"), \
             patch("src.shared.infrastructure.composition_root.run_image_google"), \
             patch("src.shared.infrastructure.composition_root.run_image_enricher"), \
             patch(
                 "src.shared.application.usecases.tts_from_article.run_tts_from_articles",
                 side_effect=lambda arts: arts,
             ), \
             patch(
                 "src.shared.infrastructure.composition_root.create_video_generator",
                 return_value=video_gen,
             ), \
             patch("src.shared.infrastructure.composition_root.run_wordpress"), \
             patch("src.shared.infrastructure.composition_root.run_bluesky"), \
             patch("src.shared.infrastructure.composition_root.run_mastodon"), \
             patch("src.shared.infrastructure.composition_root.run_facebook"):
            pipeline.execute("https://example.com/news/1")

        posts_coll.update_one.assert_not_called()
