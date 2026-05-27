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
        mock_extractor.extract = Mock(return_value=("Content from Jina", "jina"))

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
        mock_extractor.extract = Mock(return_value=("Content from Jina", "jina"))

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
    """Test /news/providers endpoint."""

    def test_providers_endpoint_returns_list(self):
        """Endpoint should return list of supported providers."""
        from fastapi.testclient import TestClient
        from src.news.entrypoints.api.news_router import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/news")
        client = TestClient(app)

        response = client.get("/news/providers")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "providers" in data["data"]
        assert isinstance(data["data"]["providers"], list)

    def test_providers_endpoint_has_valid_providers(self):
        """Endpoint should return at least one valid provider."""
        from fastapi.testclient import TestClient
        from src.news.entrypoints.api.news_router import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/news")
        client = TestClient(app)

        response = client.get("/news/providers")
        data = response.json()
        providers = data["data"]["providers"]

        # Should have providers available
        assert len(providers) > 0
        # All should be strings
        assert all(isinstance(p, str) for p in providers)


class TestProcessUrlInputValidation:
    """Test /process_url endpoint input validation."""

    @patch("src.news.entrypoints.api.news_router.get_content_extractor")
    def test_rejects_empty_url(self, mock_get_extractor):
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

    @patch("src.news.entrypoints.api.news_router.get_content_extractor")
    def test_rejects_none_url(self, mock_get_extractor):
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

    @patch("src.news.entrypoints.api.news_router.get_content_extractor")
    def test_accepts_valid_url_and_forces_fresh_extraction(self, mock_get_extractor):
        """Endpoint should always force fresh extraction (no cache) for manual URL processing."""
        from fastapi.testclient import TestClient
        from src.news.entrypoints.api.news_router import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/news")

        mock_extractor = Mock()
        mock_get_extractor.return_value = mock_extractor

        with patch(
            "src.news.application.usecases.news_to_news.process_news_url"
        ) as mock_process:
            mock_process.return_value = {
                "article_data": {"article": {"title": "Test"}},
                "post": "Test",
                "mode": "local",
            }

            client = TestClient(app)

            response = client.post(
                "/news/process_url",
                json={
                    "url": "https://example.com/article",
                    "use_ai": True,
                },
            )

            # Should succeed
            assert response.status_code == 200
            # Verify process_news_url was called with force_extract=True (always)
            call_kwargs = mock_process.call_args[1]
            assert call_kwargs["force_extract"] is True


class TestProcessUrlErrorHandling:
    """Test error handling in /process_url endpoint."""

    @patch("src.news.entrypoints.api.news_router.get_content_extractor")
    def test_unsupported_provider_returns_400(self, mock_get_extractor):
        """Unsupported provider should return 400 error."""
        from fastapi.testclient import TestClient
        from src.news.entrypoints.api.news_router import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/news")

        mock_extractor = Mock()
        mock_get_extractor.return_value = mock_extractor

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
