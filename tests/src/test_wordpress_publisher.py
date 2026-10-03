"""Tests for WordPressPublisher.publish_articles.

Cobertura objetivo: todas las ramas del loop de publicación
sin llamar a WordPress ni MongoDB reales.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path


class TestPublishArticles:
    """Tests de WordPressPublisher.publish_articles."""

    @staticmethod
    def _publisher():
        from src.shared.adapters.wordpress_publisher import WordPressPublisher
        return WordPressPublisher()

    @staticmethod
    def _articles(n=1, **overrides):
        """Genera artículos de prueba deterministas."""
        arts = []
        for i in range(n):
            arts.append({
                "title": f"Artículo {i}",
                "content": f"<p>Contenido del artículo {i}.</p>",
                "url": f"https://example.com/article-{i}",
                "original_url": f"https://source.com/article-{i}",
                "labels": ["Noticias"],
                "tags": [],
                "slug": f"articulo-{i}",
                **overrides,
            })
        return arts

    @staticmethod
    def _posts(articles):
        """Genera posts indexados por la original_url del artículo."""
        return [
            {
                "url": a.get("original_url") or a.get("url"),
                "title_es": a.get("title_es"),
                "hashtags": a.get("hashtags", []),
                "tweet": a.get("tweet"),
            }
            for a in articles
        ]

    # ─── ramas de guardia ───────────────────────────────────────────

    def test_no_articles_returns_warning(self):
        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=[]):
            result = pub.publish_articles(articles=[])
        assert result["status"] == "warning"
        assert "artículos" in result["message"]

    def test_no_posts_returns_warning(self):
        pub = self._publisher()
        articles = self._articles()
        with patch.object(pub, "_load_posts_from_mongo", return_value=[]):
            result = pub.publish_articles(articles=articles, posts=[])
        assert result["status"] == "warning"
        assert "posts" in result["message"]

    def test_empty_articles_uses_mongo_and_gets_none(self):
        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=[]):
            result = pub.publish_articles()
        assert result["status"] == "warning"

    # ─── skip: ya publicado ─────────────────────────────────────────

    def test_skips_already_published(self):
        arts = self._articles(1)
        posts = self._posts(arts)
        posts[0]["wp_url"] = "https://site.com/published"

        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=arts):
            with patch.object(pub, "_load_posts_from_mongo", return_value=posts):
                result = pub.publish_articles()
        assert result["published"] == 0
        assert result["total"] == 1

    # ─── skip: inválido (sin título o contenido) ────────────────────

    @pytest.mark.parametrize("missing", ["title", "content"])
    def test_skips_article_without_title_or_content(self, missing):
        arts = self._articles(1)
        arts[0][missing] = None
        posts = self._posts(arts)

        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=arts):
            with patch.object(pub, "_load_posts_from_mongo", return_value=posts):
                with patch("src.shared.adapters.wordpress_publisher.publish_post", return_value="https://site.com/x"):
                    result = pub.publish_articles()
        assert result["published"] == 0

    # ─── categoría: mapeo Video/Política → Noticias ─────────────────

    @pytest.mark.parametrize("cat", ["Video", "Política", "Política internacional"])
    def test_maps_special_categories_to_noticias(self, cat):
        arts = self._articles(1, labels=[cat])
        posts = self._posts(arts)

        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=arts):
            with patch.object(pub, "_load_posts_from_mongo", return_value=posts):
                with patch("src.shared.adapters.wordpress_publisher.ensure_category", return_value=5) as mock_cat:
                    with patch("src.shared.adapters.wordpress_publisher.ensure_tag", return_value=None):
                        with patch("src.shared.adapters.wordpress_publisher.publish_post", return_value=f"https://site.com/{cat}"):
                            result = pub.publish_articles()
        mock_cat.assert_called_with("Noticias")
        assert result["published"] == 1

    # ─── tags: union etiquetas del artículo + precomputed ────────────

    def test_merges_labels_and_precomputed_tags(self):
        arts = self._articles(1, labels=["Economía"], hashtags=["mercados", "economia"])
        posts = self._posts(arts)

        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=arts):
            with patch.object(pub, "_load_posts_from_mongo", return_value=posts):
                with patch("src.shared.adapters.wordpress_publisher.ensure_category", return_value=3):
                    with patch("src.shared.adapters.wordpress_publisher.ensure_tag", side_effect=lambda t: 1 if t else None) as mock_tag:
                        with patch("src.shared.adapters.wordpress_publisher.publish_post", return_value="https://site.com/x"):
                            result = pub.publish_articles()
        # Etiquetas pasadas: "Economía" + "mercados" + "economia"
        called_with = mock_tag.call_args_list
        tags_passed = {c[0][0] for c in called_with}
        assert tags_passed == {"Economía", "mercados", "economia"}
        assert result["published"] == 1

    # ─── imagen: path local ─────────────────────────────────────────

    def test_uploads_image_from_path(self, tmp_path):
        img = tmp_path / "foto.jpg"
        img.write_bytes(b"\xff\xd8\xff fake jpeg")
        arts = self._articles(1, image_path=str(img), image_url="https://cdn.example.com/foto.jpg")
        posts = self._posts(arts)

        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=arts):
            with patch.object(pub, "_load_posts_from_mongo", return_value=posts):
                with patch("src.shared.adapters.wordpress_publisher.upload_image", return_value=42):
                    with patch("src.shared.adapters.wordpress_publisher.ensure_category", return_value=1):
                        with patch("src.shared.adapters.wordpress_publisher.ensure_tag", return_value=None):
                            with patch("src.shared.adapters.wordpress_publisher.publish_post", return_value="https://site.com/x"):
                                with patch("src.shared.adapters.wordpress_publisher.get_headers", return_value={"Authorization": "Bearer fake"}):
                                    with patch("src.shared.adapters.wordpress_publisher.requests.get") as mock_get:
                                        media = Mock()
                                        media.status_code = 200
                                        media.json.return_value = {"source_url": "https://site.com/wp-media/foto.webp"}
                                        mock_get.return_value = media
                                        result = pub.publish_articles()
        assert result["published"] == 1

    # ─── imagen: URL remota ──────────────────────────────────────────

    def test_uploads_image_from_url(self):
        arts = self._articles(1, image_url="https://cdn.example.com/foto.jpg")
        posts = self._posts(arts)

        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=arts):
            with patch.object(pub, "_load_posts_from_mongo", return_value=posts):
                with patch("src.shared.adapters.wordpress_publisher.upload_image_from_url", return_value=99):
                    with patch("src.shared.adapters.wordpress_publisher.ensure_category", return_value=1):
                        with patch("src.shared.adapters.wordpress_publisher.ensure_tag", return_value=None):
                            with patch("src.shared.adapters.wordpress_publisher.publish_post", return_value="https://site.com/x"):
                                with patch("src.shared.adapters.wordpress_publisher.get_headers", return_value={"Authorization": "Bearer fake"}):
                                    with patch("src.shared.adapters.wordpress_publisher.requests.get") as mock_get:
                                        media = Mock()
                                        media.status_code = 200
                                        media.json.return_value = {"source_url": "https://site.com/wp-media/foto.webp"}
                                        mock_get.return_value = media
                                        result = pub.publish_articles()
        assert result["published"] == 1

    # ─── audio: bloque Gutenberg inyectado ───────────────────────────

    def test_injects_audio_block_when_tts_exists(self, tmp_path):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake mp3")
        arts = self._articles(1, tts_audio_path=str(audio))
        posts = self._posts(arts)

        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=arts):
            with patch.object(pub, "_load_posts_from_mongo", return_value=posts):
                with patch("src.shared.adapters.wordpress_publisher.upload_audio", return_value=7):
                    with patch("src.shared.adapters.wordpress_publisher.ensure_category", return_value=1):
                        with patch("src.shared.adapters.wordpress_publisher.ensure_tag", return_value=None):
                            with patch("src.shared.adapters.wordpress_publisher.publish_post", return_value="https://site.com/x") as mock_post:
                                with patch("src.shared.adapters.wordpress_publisher.requests.get") as mock_get:
                                    mock_resp = Mock()
                                    mock_resp.status_code = 200
                                    mock_resp.json.return_value = {"source_url": "https://audio.example.com/file.mp3"}
                                    mock_get.return_value = mock_resp
                                    with patch("src.shared.adapters.wordpress_publisher.get_headers", return_value={"Authorization": "Bearer fake"}):
                                        result = pub.publish_articles()
        call_args = mock_post.call_args
        content = call_args.kwargs.get("content") or call_args[1].get("content", "")
        assert "wp-block-audio" in content
        assert 'aria-label="Audio del artículo"' in content

    # ─── schema JSON-LD inyectado ────────────────────────────────────

    def test_injects_news_article_schema(self):
        arts = self._articles(1)
        posts = self._posts(arts)

        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=arts):
            with patch.object(pub, "_load_posts_from_mongo", return_value=posts):
                with patch("src.shared.adapters.wordpress_publisher.ensure_category", return_value=1):
                    with patch("src.shared.adapters.wordpress_publisher.ensure_tag", return_value=None):
                        with patch("src.shared.adapters.wordpress_publisher.publish_post", return_value="https://site.com/x") as mock_post:
                            result = pub.publish_articles()
        content = mock_post.call_args.kwargs.get("content", "")
        assert "NewsArticle" in content
        assert "@type" in content or "schema" in content.lower()

    # ─── errors counter: publish_post devuelve None ──────────────────

    def test_errors_incremented_when_publish_post_fails(self):
        arts = self._articles(1)
        posts = self._posts(arts)

        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=arts):
            with patch.object(pub, "_load_posts_from_mongo", return_value=posts):
                with patch("src.shared.adapters.wordpress_publisher.ensure_category", return_value=1):
                    with patch("src.shared.adapters.wordpress_publisher.ensure_tag", return_value=None):
                        with patch("src.shared.adapters.wordpress_publisher.publish_post", return_value=None):
                            result = pub.publish_articles()
        assert result["errors"] == 1
        assert result["published"] == 0

    # ─── draft flag pasa a publish_post ──────────────────────────────

    def test_draft_article_passed_to_publish_post(self):
        arts = self._articles(1, is_draft=True)
        posts = self._posts(arts)

        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=arts):
            with patch.object(pub, "_load_posts_from_mongo", return_value=posts):
                with patch("src.shared.adapters.wordpress_publisher.ensure_category", return_value=1):
                    with patch("src.shared.adapters.wordpress_publisher.ensure_tag", return_value=None):
                        with patch("src.shared.adapters.wordpress_publisher.publish_post", return_value="https://site.com/x") as mock_post:
                            result = pub.publish_articles()
        assert mock_post.call_args.kwargs.get("is_draft") is True

    # ─── múltiples artículos ─────────────────────────────────────────

    def test_publishes_multiple_articles(self):
        arts = self._articles(3)
        posts = self._posts(arts)

        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=arts):
            with patch.object(pub, "_load_posts_from_mongo", return_value=posts):
                with patch("src.shared.adapters.wordpress_publisher.ensure_category", return_value=1):
                    with patch("src.shared.adapters.wordpress_publisher.ensure_tag", return_value=None):
                        with patch("src.shared.adapters.wordpress_publisher.publish_post", side_effect=lambda **kw: f"https://site.com/{kw.get('slug')}"):
                            result = pub.publish_articles()
        assert result["published"] == 3
        assert result["errors"] == 0
        assert len(result["urls"]) == 3

    # ─── matched_post fallback: title_es / tweet ─────────────────────

    def test_uses_matched_post_title_es_when_article_has_no_title(self):
        arts = [{"content": "<p>c</p>", "url": "https://source.com/a", "original_url": "https://source.com/a", "labels": ["Noticias"]}]
        posts = [{"url": "https://source.com/a", "title_es": "Título traducido", "hashtags": []}]

        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=arts):
            with patch.object(pub, "_load_posts_from_mongo", return_value=posts):
                with patch("src.shared.adapters.wordpress_publisher.ensure_category", return_value=1):
                    with patch("src.shared.adapters.wordpress_publisher.ensure_tag", return_value=None):
                        with patch("src.shared.adapters.wordpress_publisher.publish_post", return_value="https://site.com/x") as mock_post:
                            result = pub.publish_articles()
        assert mock_post.call_args.kwargs["title"] == "Título traducido"
        assert result["published"] == 1

    # ─── categoría_id None: no se pasa categories ────────────────────

    def test_skips_categories_when_ensure_category_returns_none(self):
        arts = self._articles(1)
        posts = self._posts(arts)

        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=arts):
            with patch.object(pub, "_load_posts_from_mongo", return_value=posts):
                with patch("src.shared.adapters.wordpress_publisher.ensure_category", return_value=None):
                    with patch("src.shared.adapters.wordpress_publisher.ensure_tag", return_value=None):
                        with patch("src.shared.adapters.wordpress_publisher.publish_post", return_value="https://site.com/x") as mock_post:
                            result = pub.publish_articles()
        assert mock_post.call_args.kwargs.get("categories") is None
        assert result["published"] == 1

    # ─── featured_image_url resolution desde media/{id} ───────────────

    def test_resolves_featured_image_url_from_wp_media(self):
        arts = self._articles(1, image_path="/tmp/fake.jpg")
        posts = self._posts(arts)

        pub = self._publisher()
        mock_media = Mock()
        mock_media.status_code = 200
        mock_media.json.return_value = {"source_url": "https://site.com/wp-content/up.jpg"}

        with patch.object(pub, "_load_articles_from_mongo", return_value=arts):
            with patch.object(pub, "_load_posts_from_mongo", return_value=posts):
                with patch("src.shared.adapters.wordpress_publisher.upload_image", return_value=123):
                    with patch("src.shared.adapters.wordpress_publisher.requests.get", return_value=mock_media):
                        with patch("src.shared.adapters.wordpress_publisher.ensure_category", return_value=1):
                            with patch("src.shared.adapters.wordpress_publisher.ensure_tag", return_value=None):
                                with patch("src.shared.adapters.wordpress_publisher.publish_post") as mock_post:
                                    mock_post.return_value = "https://site.com/x"
                                    result = pub.publish_articles()
        content = mock_post.call_args.kwargs.get("content", "")
        assert "https://site.com/wp-content/up.jpg" in content or "featured_image_url" in str(mock_post.call_args.kwargs)

    # ─── audio local eliminado tras subida (con o sin éxito) ─────────

    def test_deletes_local_audio_after_upload(self, tmp_path):
        audio = tmp_path / "tts.mp3"
        audio.write_bytes(b"fake mp3")
        arts = self._articles(1, tts_audio_path=str(audio))
        posts = self._posts(arts)

        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=arts):
            with patch.object(pub, "_load_posts_from_mongo", return_value=posts):
                with patch("src.shared.adapters.wordpress_publisher.upload_audio", return_value=5):
                    with patch("src.shared.adapters.wordpress_publisher.ensure_category", return_value=1):
                        with patch("src.shared.adapters.wordpress_publisher.ensure_tag", return_value=None):
                            with patch("src.shared.adapters.wordpress_publisher.publish_post", return_value="https://site.com/x"):
                                result = pub.publish_articles()
        assert not audio.exists()
        assert result["published"] == 1

    # ─── schema silenciado cuando build_news_article_schema falla ────

    def test_continues_without_schema_if_schema_builder_raises(self):
        arts = self._articles(1)
        posts = self._posts(arts)

        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=arts):
            with patch.object(pub, "_load_posts_from_mongo", return_value=posts):
                with patch("src.shared.adapters.wordpress_publisher.ensure_category", return_value=1):
                    with patch("src.shared.adapters.wordpress_publisher.ensure_tag", return_value=None):
                        with patch("src.shared.adapters.wordpress_publisher.publish_post", return_value="https://site.com/x") as mock_post:
                            with patch("src.shared.adapters.seo_optimizer.build_news_article_schema", side_effect=Exception("boom")):
                                result = pub.publish_articles()
        assert result["published"] == 1
        # Contenido sin schema JSON-LD
        content = mock_post.call_args.kwargs.get("content", "")
        assert "NewsArticle" not in content

    # ─── respuesta final tiene urls y total ──────────────────────────

    def test_return_dict_shape(self):
        arts = self._articles(2)
        posts = self._posts(arts)

        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=arts):
            with patch.object(pub, "_load_posts_from_mongo", return_value=posts):
                with patch("src.shared.adapters.wordpress_publisher.ensure_category", return_value=1):
                    with patch("src.shared.adapters.wordpress_publisher.ensure_tag", return_value=None):
                        with patch("src.shared.adapters.wordpress_publisher.publish_post", side_effect=lambda **kw: f"https://site.com/{kw.get('slug')}"):
                            result = pub.publish_articles()
        assert set(result.keys()) >= {"status", "published", "errors", "total", "url", "urls"}
        assert result["status"] == "success"
        assert result["total"] == 2
        assert result["published"] == 2
        assert result["errors"] == 0
        assert len(result["urls"]) == 2
        assert result["url"] == result["urls"][0]

    def test_return_url_empty_when_nothing_published(self):
        arts = self._articles(1)
        posts = self._posts(arts)

        pub = self._publisher()
        with patch.object(pub, "_load_articles_from_mongo", return_value=arts):
            with patch.object(pub, "_load_posts_from_mongo", return_value=posts):
                with patch("src.shared.adapters.wordpress_publisher.ensure_category", return_value=None):
                    with patch("src.shared.adapters.wordpress_publisher.ensure_tag", return_value=None):
                        with patch("src.shared.adapters.wordpress_publisher.publish_post", return_value=None):
                            result = pub.publish_articles()
        assert result["status"] == "success"  # loop terminó OK, 0 publicados
        assert result["errors"] == 1
        assert result["url"] == ""
        assert result["urls"] == []
