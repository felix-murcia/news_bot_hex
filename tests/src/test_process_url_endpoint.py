"""Tests for /news/process_url endpoint and NewsToNewsUseCase flow."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path


class TestNewsToNewsUseCaseForceExtractParameter:
    """Test force_extract parameter in NewsToNewsUseCase."""

    def test_force_extract_parameter_defaults_to_false(self):
        """force_extract should default to False."""
        from src.news.application.usecases.news_to_news import NewsToNewsUseCase

        mock_extractor = Mock()
        use_case = NewsToNewsUseCase(content_extractor=mock_extractor)
        assert use_case.force_extract is False

    def test_force_extract_parameter_can_be_set_true(self):
        """force_extract should be settable to True."""
        from src.news.application.usecases.news_to_news import NewsToNewsUseCase

        mock_extractor = Mock()
        use_case = NewsToNewsUseCase(content_extractor=mock_extractor, force_extract=True)
        assert use_case.force_extract is True

    def test_force_extract_parameter_can_be_set_false(self):
        """force_extract should be explicitly settable to False."""
        from src.news.application.usecases.news_to_news import NewsToNewsUseCase

        mock_extractor = Mock()
        use_case = NewsToNewsUseCase(
            content_extractor=mock_extractor, force_extract=False
        )
        assert use_case.force_extract is False

    def test_extract_content_respects_force_extract_flag(self):
        """_extract_content should check force_extract flag."""
        from src.news.application.usecases.news_to_news import NewsToNewsUseCase

        mock_extractor = Mock()
        mock_extractor.extract = Mock(return_value=("Content from Jina", "jina", ""))

        # Test with force_extract=True
        use_case_force = NewsToNewsUseCase(
            content_extractor=mock_extractor, force_extract=True
        )

        with patch.object(NewsToNewsUseCase, "_load_from_cache") as mock_cache:
            with patch.object(NewsToNewsUseCase, "_save_to_cache"):
                # When force_extract=True, cache check is skipped
                content, path = use_case_force._extract_content("https://example.com")

                # _load_from_cache should not be called when force_extract=True
                mock_cache.assert_not_called()
                # But extractor should be called
                mock_extractor.extract.assert_called_once()

    def test_extract_content_checks_cache_when_force_extract_false(self):
        """_extract_content should check cache when force_extract=False."""
        from src.news.application.usecases.news_to_news import NewsToNewsUseCase

        mock_extractor = Mock()
        mock_extractor.extract = Mock(return_value=("Content from Jina", "jina", ""))

        # Test with force_extract=False (default)
        use_case = NewsToNewsUseCase(
            content_extractor=mock_extractor, force_extract=False
        )

        with patch.object(
            NewsToNewsUseCase, "_load_from_cache", return_value=None
        ) as mock_cache:
            with patch.object(NewsToNewsUseCase, "_save_to_cache"):
                # When cache misses
                content, path = use_case._extract_content("https://example.com")

                # _load_from_cache SHOULD be called when force_extract=False
                mock_cache.assert_called_once()
                # And if cache misses, extractor is called
                mock_extractor.extract.assert_called_once()


class TestProcessUrlRequestModel:
    """Test ProcessUrlRequest Pydantic model."""

    def test_process_url_request_has_required_fields(self):
        """ProcessUrlRequest should have required fields."""
        from src.news.entrypoints.api.news_router import ProcessUrlRequest

        request = ProcessUrlRequest(
            url="https://example.com",
            provider="gemini",
            use_ai=True,
        )
        assert request.url == "https://example.com"
        assert request.provider == "gemini"
        assert request.use_ai is True

    def test_process_url_request_use_ai_defaults_to_true(self):
        """use_ai should default to True."""
        from src.news.entrypoints.api.news_router import ProcessUrlRequest

        request = ProcessUrlRequest(url="https://example.com")
        assert request.use_ai is True

    def test_process_url_request_provider_optional(self):
        """provider should be optional."""
        from src.news.entrypoints.api.news_router import ProcessUrlRequest

        request = ProcessUrlRequest(
            url="https://example.com/article",
            use_ai=False,
        )
        assert request.url == "https://example.com/article"
        assert request.provider is None
        assert request.use_ai is False


class TestProcessNewsUrlFunction:
    """Test process_news_url function signature."""

    def test_process_news_url_accepts_force_extract(self):
        """process_news_url should accept force_extract parameter."""
        from src.news.application.usecases.news_to_news import process_news_url
        import inspect

        sig = inspect.signature(process_news_url)
        params = sig.parameters

        # Verify parameter exists
        assert "force_extract" in params
        # Verify default value is False
        assert params["force_extract"].default is False

    def test_process_news_url_passes_force_extract_to_usecase(self):
        """process_news_url should pass force_extract to NewsToNewsUseCase."""
        from src.news.application.usecases.news_to_news import process_news_url

        mock_extractor = Mock()

        with patch(
            "src.news.application.usecases.news_to_news.NewsToNewsUseCase"
        ) as mock_usecase_class:
            mock_usecase_instance = Mock()
            mock_usecase_instance.process_url = Mock(
                return_value={"article_data": {"article": {"title": "Test"}}}
            )
            mock_usecase_class.return_value = mock_usecase_instance

            # Call with force_extract=True
            process_news_url(
                url="https://example.com",
                content_extractor=mock_extractor,
                force_extract=True,
            )

            # Verify usecase was instantiated with force_extract=True
            call_kwargs = mock_usecase_class.call_args[1]
            assert "force_extract" in call_kwargs
            assert call_kwargs["force_extract"] is True


class TestProvidersEndpoint:
    """Test /admin/providers endpoint.

    The route lives in admin_router (remediation H5: admin endpoints moved out
    of news_router), mounted with prefix /admin in server.py:71. The frontend
    already calls /admin/providers (frontend/src/api/news.ts:30).
    """

    @staticmethod
    def _client():
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from src.news.entrypoints.api.admin_router import router

        app = FastAPI()
        app.include_router(router, prefix="/admin")
        return TestClient(app)

    def test_providers_endpoint_returns_list(self):
        """Endpoint should return list of supported providers."""
        client = self._client()

        response = client.get("/admin/providers")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "providers" in data["data"]
        assert isinstance(data["data"]["providers"], list)

    def test_providers_endpoint_has_valid_providers(self):
        """Endpoint should return at least one valid provider."""
        client = self._client()

        response = client.get("/admin/providers")
        assert response.status_code == 200
        data = response.json()
        providers = data["data"]["providers"]

        # Should have providers available
        assert len(providers) > 0
        # All should be strings
        assert all(isinstance(p, str) for p in providers)

    def test_providers_endpoint_matches_ai_adapter_map(self):
        """The endpoint must expose exactly the providers in Settings.AI_ADAPTER_MAP.

        Guards against hardcoding a provider list in the frontend or the router.
        """
        from config.settings import Settings

        client = self._client()
        providers = client.get("/admin/providers").json()["data"]["providers"]

        assert sorted(providers) == sorted(Settings.AI_ADAPTER_MAP.keys())


class TestProcessUrlInputValidation:
    """Test /process_url endpoint input validation."""

    def test_rejects_empty_url(self):
        """Endpoint should reject empty URLs."""
        from fastapi.testclient import TestClient
        from src.news.entrypoints.api.news_router import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/news")
        client = TestClient(app)

        response = client.post("/news/process_url", json={"url": ""})

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert data["detail"]["error_code"] == "INVALID_URL"

    def test_rejects_none_url(self):
        """Endpoint should reject None URLs."""
        from fastapi.testclient import TestClient
        from src.news.entrypoints.api.news_router import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/news")
        client = TestClient(app)

        # Pydantic will handle missing required field
        response = client.post("/news/process_url", json={})

        # Should return validation error
        assert response.status_code in [422, 400]

    def test_accepts_valid_url_and_forces_fresh_extraction(self):
        """Endpoint composition must always force fresh extraction (no cache).

        The POST /news/process_url endpoint is asynchronous (it creates a job
        and hands off to ProcessUrlJobCoordinator), so it never calls
        process_news_url inline any more. The "always fresh" guarantee now lives
        in the composition root: get_process_url_content_processor wires
        force_extract=True (see docs/CACHE_EXTRACTION_FIX.md).
        """
        from src.news.entrypoints.api.dependencies import (
            get_process_url_content_processor,
        )

        mock_extractor = Mock()

        with patch(
            "src.news.application.usecases.news_to_news.process_news_url"
        ) as mock_process:
            mock_process.return_value = {
                "article_data": {"article": {"title": "Test"}},
                "post": "Test",
                "mode": "local",
            }

            process_url = get_process_url_content_processor(
                content_extractor=mock_extractor
            )
            result = process_url("https://example.com/article")

        # process_news_url must have been invoked with force_extract=True (always)
        call_kwargs = mock_process.call_args[1]
        assert call_kwargs["force_extract"] is True
        assert call_kwargs["url"] == "https://example.com/article"
        assert call_kwargs["content_extractor"] is mock_extractor
        assert result == mock_process.return_value

    def test_process_url_endpoint_returns_job_id_for_polling(self):
        """POST /news/process_url is async: it must return a job_id, not results."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from src.news.entrypoints.api.news_router import router

        app = FastAPI()
        app.include_router(router, prefix="/news")

        mock_repo = Mock()
        mock_repo.create.return_value = "job-123"
        mock_coordinator = Mock()

        app.dependency_overrides = {}
        from src.news.entrypoints.api.news_router import (
            get_process_url_job_coordinator,
            get_process_url_job_repository,
        )

        app.dependency_overrides[get_process_url_job_repository] = lambda: mock_repo
        app.dependency_overrides[get_process_url_job_coordinator] = lambda: mock_coordinator

        client = TestClient(app)
        response = client.post(
            "/news/process_url", json={"url": "https://example.com/article"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["job_id"] == "job-123"
        mock_coordinator.execute_async.assert_called_once_with(
            job_id="job-123", url="https://example.com/article"
        )


class ProcessUrlPipelineTestBase:
    """Base para los tests de ProcessUrlPipeline: helper _run_pipeline + url."""

    PIPELINE_URL = "https://example.com/en/article"

    def _run_pipeline(self, jina_title="", run_content_result=None,
                      run_article_result=None, articles_in_db=None):
        """Ejecuta el pipeline con mocks. Devuelve (inserted, ctx).

        `ctx` es un dict con los mocks (run_content, run_article, tts,
        wordpress, ...) para poder asertar qué pasos llegaron a ejecutarse.
        `articles_in_db` simula el contenido de generated_articles (F12).
        """
        import contextlib
        from unittest.mock import patch, Mock
        from src.news.application.usecases.process_url_pipeline import ProcessUrlPipeline

        inserted = []
        fake_db = MagicMock()
        # list(db["generated_articles"].find({})) debe iterar -> []
        fake_db.__getitem__.return_value.find.return_value = (
            [] if articles_in_db is None else articles_in_db
        )

        content = "English Headline Here\n\n" + "Body text about the story. " * 20
        extractor = Mock()
        # Port ContentExtractor.extract -> (contenido, metodo, titulo_jina)
        extractor.extract.return_value = (content, "jina", jina_title)

        ctx = {}
        with contextlib.ExitStack() as stack:
            p = lambda *a, **k: stack.enter_context(patch(*a, **k))  # noqa: E731
            ctx["run_content"] = p("src.news.application.usecases.content.run_content")
            ctx["run_article"] = p("src.news.application.usecases.article.run")
            ctx["images_unsplash"] = p(
                "src.shared.infrastructure.composition_root.run_image_unsplash")
            ctx["images_google"] = p(
                "src.shared.infrastructure.composition_root.run_image_google")
            ctx["image_enricher"] = p(
                "src.shared.infrastructure.composition_root.run_image_enricher")
            ctx["tts"] = p(
                "src.shared.application.usecases.tts_from_article.run_tts_from_articles",
                return_value=[])
            ctx["video_gen"] = p(
                "src.shared.infrastructure.composition_root.create_video_generator",
                return_value=Mock(is_available=Mock(return_value=False)))
            ctx["wordpress"] = p(
                "src.shared.infrastructure.composition_root.run_wordpress")
            ctx["bluesky"] = p(
                "src.shared.infrastructure.composition_root.run_bluesky")
            ctx["mastodon"] = p(
                "src.shared.infrastructure.composition_root.run_mastodon")
            ctx["facebook"] = p(
                "src.shared.infrastructure.composition_root.run_facebook")
            p("src.shared.adapters.mongo_db.get_database", return_value=fake_db)
            ctx["translate"] = p("src.shared.adapters.translator.translate_text")

            if run_content_result is not None:
                ctx["run_content"].return_value = run_content_result
            if run_article_result is not None:
                ctx["run_article"].return_value = run_article_result

            mock_repo_cls = stack.enter_context(
                patch("src.news.infrastructure.adapters.MongoVerifiedNewsRepository")
            )
            mock_repo_cls.return_value.insert_news.side_effect = (
                lambda arts: inserted.extend(arts)
            )

            pipeline = ProcessUrlPipeline(content_extractor=extractor, metrics_repo=None)
            try:
                pipeline.execute(self.PIPELINE_URL)
            except Exception as e:
                ctx["error"] = e  # los tests fail-fast asertan sobre ella

        return inserted, ctx


class TestProcessUrlPipelineTitleEs(ProcessUrlPipelineTestBase):
    """save_verified ya no traduce el título por API de Google: deja title_es
    vacío. El LLM genera el título en español al escribir el artículo
    (article.py lo extrae del <h1> del LLM y lo escribe de vuelta en el post).
    """

    def test_title_es_is_left_empty_and_no_google_call(self):
        inserted, ctx = self._run_pipeline()
        assert inserted, "save_verified debe insertar un VerifiedArticle"
        article = inserted[0]
        assert article.title == "English Headline Here"
        # El LLM lo rellena más adelante (paso Generate Articles)
        assert article.title_es == ""
        ctx["translate"].assert_not_called()

    def test_jina_title_takes_precedence_over_first_content_line(self):
        """El campo 'Title:' de Jina manda sobre la primera línea del cuerpo
        (que en páginas con banner de cookies sería el banner, no el titular).
        """
        inserted, _ = self._run_pipeline(
            jina_title="Azerbaijan, Turkey and Uzbekistan join forces in major military exercise"
        )
        assert inserted
        assert inserted[0].title == (
            "Azerbaijan, Turkey and Uzbekistan join forces in major military exercise"
        )

    def test_falls_back_to_first_line_when_jina_title_is_empty(self):
        inserted, _ = self._run_pipeline(jina_title="")
        assert inserted
        assert inserted[0].title == "English Headline Here"


class TestProcessUrlPipelineFailFastNoContent(ProcessUrlPipelineTestBase):
    """El pipeline URL es de UNA sola url: si la IA no publica contenido
    (negación / baja calidad) no hay nada que publicar y el pipeline debe
    terminar AHÍ, sin quemar recursos en imágenes, audio, vídeo y WP/social.
    El skip por-item es legítimo en el pipeline automático (N artículos RSS),
    no aquí.
    """

    def test_aborts_when_no_post_is_generated(self):
        """run_content -> [] (la IA se negó) => Generate Posts aborta y
        NINGÚN paso posterior se ejecuta."""
        inserted, ctx = self._run_pipeline(run_content_result=[])
        assert isinstance(ctx.get("error"), RuntimeError)
        assert "No se generó ningún post" in str(ctx["error"])
        ctx["run_content"].assert_called_once()
        ctx["run_article"].assert_not_called()
        ctx["images_unsplash"].assert_not_called()
        ctx["image_enricher"].assert_not_called()
        ctx["tts"].assert_not_called()
        ctx["wordpress"].assert_not_called()
        ctx["bluesky"].assert_not_called()
        ctx["mastodon"].assert_not_called()
        ctx["facebook"].assert_not_called()
        assert ctx.get("error") is not None

    def test_run_content_with_post_does_not_abort(self):
        """Con al menos un post, el pipeline completa (no aborta)."""
        inserted, ctx = self._run_pipeline(
            run_content_result=[{"tweet": "x", "url": self.PIPELINE_URL}]
        )
        assert inserted
        assert ctx.get("error") is None
        ctx["run_article"].assert_called()
        ctx["wordpress"].assert_called()
        ctx["facebook"].assert_called()

    def test_aborts_when_no_article_is_generated(self):
        """Post OK pero run_article -> [] => aborta antes de audio/vídeo/WP."""
        inserted, ctx = self._run_pipeline(
            run_content_result=[{"tweet": "x", "url": self.PIPELINE_URL}],
            run_article_result=[],
        )
        assert isinstance(ctx.get("error"), RuntimeError)
        assert "No se generó artículo" in str(ctx["error"])
        ctx["run_article"].assert_called_once()
        ctx["tts"].assert_not_called()
        ctx["wordpress"].assert_not_called()
        ctx["bluesky"].assert_not_called()

    def test_audio_only_processes_articles_of_this_url(self):
        """generated_articles puede contener restos de ejecuciones anteriores
        (save_all solo sustituye si hubo generación). El paso F12 debe filtrar
        por original_url para no procesar contenido ajeno a la url."""
        this_url = self.PIPELINE_URL
        arts = [
            {"original_url": "https://otra-noticia.com/x",
             "tts_audio_path": "/tmp/otro.mp3"},
            {"original_url": this_url,
             "tts_audio_path": "/tmp/este.mp3"},
        ]
        inserted, ctx = self._run_pipeline(articles_in_db=arts)
        assert ctx.get("error") is None
        # El TTS solo debe ver el artículo de ESTA url, no el resto:
        tts_arg = ctx["tts"].call_args.args[0]
        assert tts_arg == [arts[1]]


class TestProcessUrlErrorHandling:
    """Test error handling in /process_url endpoint."""

    def test_unsupported_provider_returns_400(self):
        """Unsupported provider should return 400 error."""
        from fastapi.testclient import TestClient
        from src.news.entrypoints.api.news_router import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/news")

        client = TestClient(app)

        response = client.post(
            "/news/process_url",
            json={
                "url": "https://example.com",
                "provider": "definitely_not_a_real_provider",
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert data["detail"]["error_code"] == "INVALID_REQUEST"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
