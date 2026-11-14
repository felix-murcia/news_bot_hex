"""Tests for PrepareArticlesUseCase and pipeline data flow fix.

These tests verify:
1. PrepareArticlesUseCase transforms raw_news -> generated_articles correctly
2. _execute_step detects error dict returns (fail-fast)
3. ArticleUseCase doesn't recycle old URLs (freshness check)
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta

from src.news.application.usecases.prepare_articles_for_verify import PrepareArticlesUseCase
from src.news.application.usecases.pipeline_runner import _execute_step
from src.news.application.usecases.article import ArticleUseCase
from src.news.domain.entities.pipeline_job import (
    ProcessingStepName,
    ProcessingStepStatus,
    PipelineStepResult,
)
from src.news.domain.entities.verified_article import VerifiedArticle


class TestPrepareArticlesUseCase:
    """Tests for the raw_news -> generated_articles transformation."""

    def test_execute_success(self):
        """Transforma artículos de raw_news y los guarda en generated_articles."""
        # Setup mocks
        raw_repo = Mock()
        generated_repo = Mock()

        # Create sample Article objects
        articles = [
            Mock(spec=["to_dict"], to_dict=lambda: {"title": "Test 1", "url": "http://test1.com", "source": "NBES", "desc": "Desc 1", "publishedAt": "2024-01-01T00:00:00Z", "origin": "RSS", "published": False, "filtered": True}),
            Mock(spec=["to_dict"], to_dict=lambda: {"title": "Test 2", "url": "http://test2.com", "source": "NBES", "desc": "Desc 2", "publishedAt": "2024-01-01T00:00:00Z", "origin": "RSS", "published": False, "filtered": True}),
        ]
        raw_repo.get_all_articles.return_value = articles
        generated_repo.save_all.return_value = True

        use_case = PrepareArticlesUseCase(raw_repo, generated_repo)
        result = use_case.execute()

        assert result["status"] == "success"
        assert result["processed"] == 2
        generated_repo.save_all.assert_called_once()
        saved_articles = generated_repo.save_all.call_args[0][0]
        assert len(saved_articles) == 2
        assert saved_articles[0]["title"] == "Test 1"

    def test_execute_empty_raw_news(self):
        """Devuelve error si raw_news está vacío."""
        raw_repo = Mock()
        generated_repo = Mock()
        raw_repo.get_all_articles.return_value = []

        use_case = PrepareArticlesUseCase(raw_repo, generated_repo)
        result = use_case.execute()

        assert result["status"] == "error"
        assert result["processed"] == 0
        assert "No hay artículos" in result["message"]
        generated_repo.save_all.assert_not_called()

    def test_execute_save_failure(self):
        """Devuelve error si falla el guardado en generated_articles."""
        raw_repo = Mock()
        generated_repo = Mock()
        articles = [Mock(spec=["to_dict"], to_dict=lambda: {"title": "Test", "url": "http://test.com"})]
        raw_repo.get_all_articles.return_value = articles
        generated_repo.save_all.return_value = False

        use_case = PrepareArticlesUseCase(raw_repo, generated_repo)
        result = use_case.execute()

        assert result["status"] == "error"
        assert "Error guardando" in result["message"]


class TestExecuteStepFailFast:
    """Tests for _execute_step detecting error dict returns."""

    def test_execute_step_detects_error_dict(self):
        """_execute_step debe detectar dict con status=error y marcar como fallo."""
        job_id = "test-job"
        step_name = ProcessingStepName.FULL_VERIFICATION
        metrics_steps = []
        step_results = []

        def failing_step():
            return {"status": "error", "message": "No hay artículos nuevos"}

        success, error = _execute_step(job_id, step_name, failing_step, metrics_steps, step_results)

        assert success is False
        assert error == "No hay artículos nuevos"
        assert len(step_results) == 1
        assert step_results[0].status == ProcessingStepStatus.ERROR
        assert step_results[0].critical is True  # FULL_VERIFICATION is critical

    def test_execute_step_success_dict(self):
        """_execute_step debe aceptar dict con status=success."""
        job_id = "test-job"
        step_name = ProcessingStepName.PREPARE_ARTICLES
        metrics_steps = []
        step_results = []

        def success_step():
            return {"status": "success", "processed": 5}

        success, error = _execute_step(job_id, step_name, success_step, metrics_steps, step_results)

        assert success is True
        assert error is None
        assert step_results[0].status == ProcessingStepStatus.OK

    def test_execute_step_exception(self):
        """_execute_step debe capturar excepciones."""
        job_id = "test-job"
        step_name = ProcessingStepName.RSS_FETCH
        metrics_steps = []
        step_results = []

        def raising_step():
            raise RuntimeError("Connection failed")

        success, error = _execute_step(job_id, step_name, raising_step, metrics_steps, step_results)

        assert success is False
        assert "Connection failed" in error
        assert step_results[0].status == ProcessingStepStatus.ERROR


class TestArticleUseCaseFreshness:
    """Tests for ArticleUseCase not recycling old URLs."""

    def test_get_current_verified_url_recent(self):
        """Debe devolver URL si la noticia verificada es reciente (<24h)."""
        from src.news.domain.ports import VerifiedNewsRepository, GeneratedPostsRepository, GeneratedArticlesRepository
        from src.shared.domain.services.ai_providers import AiProviders
        from src.shared.domain.services.seo_helpers import SeoHelpers

        # Setup mocks
        verified_repo = Mock(spec=VerifiedNewsRepository)
        generated_posts_repo = Mock(spec=GeneratedPostsRepository)
        generated_articles_repo = Mock(spec=GeneratedArticlesRepository)
        ai_providers = Mock(spec=AiProviders)
        seo_helpers = Mock(spec=SeoHelpers)

        # Create a recent verified article
        recent_article = VerifiedArticle(
            title="Recent News",
            desc="Description",
            source="NBES",
            origin="RSS",
            url="http://recent.com",
            publishedAt=datetime.utcnow() - timedelta(hours=2),
            tema="Noticias",
            resumen="Summary",
            score=10,
            model_prediction="real",
            confidence=0.95,
            verification={"verified": True},
        )
        verified_repo.get_all_news.return_value = [recent_article]

        use_case = ArticleUseCase(
            verified_repo=verified_repo,
            generated_posts_repo=generated_posts_repo,
            generated_articles_repo=generated_articles_repo,
            ai_providers=ai_providers,
            seo_helpers=seo_helpers,
        )

        url = use_case.get_current_verified_url(max_age_hours=24)
        assert url == "http://recent.com"

    def test_get_current_verified_url_old(self):
        """NO debe devolver URL si la noticia verificada es antigua (>24h)."""
        from src.news.domain.ports import VerifiedNewsRepository, GeneratedPostsRepository, GeneratedArticlesRepository
        from src.shared.domain.services.ai_providers import AiProviders
        from src.shared.domain.services.seo_helpers import SeoHelpers

        verified_repo = Mock(spec=VerifiedNewsRepository)
        generated_posts_repo = Mock(spec=GeneratedPostsRepository)
        generated_articles_repo = Mock(spec=GeneratedArticlesRepository)
        ai_providers = Mock(spec=AiProviders)
        seo_helpers = Mock(spec=SeoHelpers)

        # Create an old verified article (from manual run days ago)
        old_article = VerifiedArticle(
            title="Old News",
            desc="Description",
            source="NBES",
            origin="RSS",
            url="http://old.com",
            publishedAt=datetime.utcnow() - timedelta(hours=48),
            tema="Noticias",
            resumen="Summary",
            score=10,
            model_prediction="real",
            confidence=0.95,
            verification={"verified": True},
        )
        verified_repo.get_all_news.return_value = [old_article]

        use_case = ArticleUseCase(
            verified_repo=verified_repo,
            generated_posts_repo=generated_posts_repo,
            generated_articles_repo=generated_articles_repo,
            ai_providers=ai_providers,
            seo_helpers=seo_helpers,
        )

        url = use_case.get_current_verified_url(max_age_hours=24)
        assert url == ""

    def test_get_current_verified_url_empty(self):
        """Debe devolver string vacío si no hay noticias verificadas."""
        from src.news.domain.ports import VerifiedNewsRepository, GeneratedPostsRepository, GeneratedArticlesRepository
        from src.shared.domain.services.ai_providers import AiProviders
        from src.shared.domain.services.seo_helpers import SeoHelpers

        verified_repo = Mock(spec=VerifiedNewsRepository)
        generated_posts_repo = Mock(spec=GeneratedPostsRepository)
        generated_articles_repo = Mock(spec=GeneratedArticlesRepository)
        ai_providers = Mock(spec=AiProviders)
        seo_helpers = Mock(spec=SeoHelpers)

        verified_repo.get_all_news.return_value = []

        use_case = ArticleUseCase(
            verified_repo=verified_repo,
            generated_posts_repo=generated_posts_repo,
            generated_articles_repo=generated_articles_repo,
            ai_providers=ai_providers,
            seo_helpers=seo_helpers,
        )

        url = use_case.get_current_verified_url(max_age_hours=24)
        assert url == ""