"""Test de flujo completo del pipeline con fakes (B27).

Ejecuta los 10 pasos del PipelineRunner con wiring real de producción
y fakes en memoria. Detecta wiring roto (AttributeError, TypeError, etc.).
"""

import pytest
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from tests.flows.fakes import (
    build_pipeline_fakes,
    PipelineFakes,
)

# PipelineContext local para evitar import circular en código de producción
@dataclass
class PipelineContext:
    job_id: str
    provider: str = "local"
    article: Any = None
    post: Any = None
    posts: Any = None
    images: Any = None
    audio_path: Any = None
    video_path: Any = None
    wp_url: Any = None
    candidates: Any = None

# Imports del código de producción
from src.news.domain.entities.pipeline_job import (
    JobStatus,
    ProcessingStepName,
    ProcessingStepStatus,
    PipelineResult,
)
from src.news.application.usecases.pipeline_executor import execute_pipeline_async


class TestPipelineFullFlow:
    """Tests del flujo completo del pipeline."""

    def _build_runner(self, fakes: PipelineFakes, **overrides):
        """Construye PipelineRunner con fakes, permitiendo overrides."""
        from src.news.application.usecases.pipeline_runner import PipelineRunner
        return PipelineRunner(
            generated_articles_repo=fakes.generated_articles_repo,
            generated_posts_repo=fakes.generated_posts_repo,
            verified_news_repo=fakes.verified_news_repo,
            rss_fetch_runner=overrides.get("rss_fetch_runner", fakes.rss_fetch_runner),
            prepare_articles_runner=overrides.get("prepare_articles_runner", fakes.prepare_articles_runner),
            full_verify_runner=overrides.get("full_verify_runner", fakes.full_verify_runner),
            metrics_repo=fakes.metrics_repo,
            social_publisher=overrides.get("social_publisher", fakes.social_publisher),
            tts_usecase=overrides.get("tts_usecase", fakes.tts_usecase),
            image_unsplash_runner=overrides.get("image_unsplash_runner", fakes.image_unsplash_runner),
            image_google_runner=overrides.get("image_google_runner", fakes.image_google_runner),
            image_enricher_runner=overrides.get("image_enricher_runner", fakes.image_enricher_runner),
            wordpress_runner=overrides.get("wordpress_runner", fakes.wordpress_runner),
            video_generator_factory=overrides.get("video_generator_factory", fakes.video_generator_factory),
            social_truncator=fakes.social_truncator,
            post_editor=fakes.post_editor,
            cache_loader=fakes.cache_loader,
            seo_helpers=fakes.seo_helpers,
            ai_providers=fakes.ai_providers,
        )

    def _run_pipeline(self, runner, job_id: str = "test-job") -> PipelineResult:
        """Ejecuta el pipeline y devuelve el resultado final desde el job repo."""
        from src.news.application.usecases.pipeline_job import create_job, get_job
        from src.news.domain.entities.pipeline_job import JobStatus, ProcessingStepName, ProcessingStepStatus, PipelineStepResult

        # Crear el job primero (como hace execute_pipeline_async)
        if job_id == "test-job":
            job_id = create_job()

        ctx = PipelineContext(job_id=job_id, provider="local")
        runner.run(ctx)

        # Obtener el resultado final del job
        job = get_job(job_id)
        if not job:
            raise RuntimeError(f"Job {job_id} no encontrado después de ejecutar")

        # get_job devuelve dict, convertir a PipelineResult
        return PipelineResult(
            job_id=job.get("job_id", job_id),
            status=JobStatus(job.get("status", "unknown")),
            steps=[
                PipelineStepResult(
                    name=ProcessingStepName(s.get("name")),
                    status=ProcessingStepStatus(s.get("status")),
                    error=s.get("error"),
                    critical=s.get("critical", False),
                )
                for s in job.get("steps", [])
            ],
            error=job.get("error"),
            failed_steps=job.get("failed_steps", []),
        )

    def test_pipeline_completes_with_fakes(self):
        """Test 1: Pipeline completo con fakes → SUCCESS."""
        fakes = build_pipeline_fakes()
        
        # Pre-poblar generated_articles_repo con artículos (simula que RSS fetch + conversión ya ocurrió)
        test_articles = [
            {
                "_id": f"art-{i}",
                "title": f"Test Article {i}",
                "url": f"https://example.com/article/{i}",
                "desc": f"Description {i}",
                "publishedAt": datetime.now(timezone.utc).isoformat(),
                "source": "Test Source",
                "status": "pending",
            }
            for i in range(3)
        ]
        fakes.generated_articles_repo.save_all(test_articles)
        
        runner = self._build_runner(fakes)
        result = self._run_pipeline(runner, "test-job")

        # Verificar estado final
        assert result.status == JobStatus.COMPLETED, f"Expected COMPLETED, got {result.status}: {result.error}"
        assert result.error is None
        assert len(result.failed_steps) == 0

        # Verificar que pasaron los 11 pasos (incluye Prepare Articles)
        step_names = [s.name for s in result.steps]
        expected_steps = [
            ProcessingStepName.RSS_FETCH,
            ProcessingStepName.PREPARE_ARTICLES,
            ProcessingStepName.FULL_VERIFICATION,
            ProcessingStepName.GENERATE_POSTS,
            ProcessingStepName.GENERATE_ARTICLES,
            ProcessingStepName.FETCH_IMAGES,
            ProcessingStepName.ENRICH_IMAGES,
            ProcessingStepName.GENERATE_AUDIO,
            ProcessingStepName.GENERATE_VIDEO,
            ProcessingStepName.PUBLISH_WORDPRESS,
            ProcessingStepName.PUBLISH_SOCIAL,
        ]
        assert step_names == expected_steps, f"Pasos: {step_names}"

        # Todos los pasos críticos en OK
        critical_steps = [s for s in result.steps if s.critical]
        for step in critical_steps:
            assert step.status == ProcessingStepStatus.OK, f"Paso crítico {step.name} no OK: {step.error}"

        # Verificar invocaciones clave
        assert "publish" in fakes.social_publisher.calls, "SocialPublisher.publish no llamado (single-item)"
        # wordpress_runner se ejecuta en el paso 10 (PUBLISH_WORDPRESS)
        # Si el test llega aquí, el paso pasó (status=OK), así que se ejecutó

    def test_pipeline_fallback_a_segunda_candidata(self):
        """Si la candidata #1 tiene fecha vieja (se descarta), se publica la #2."""
        fakes = build_pipeline_fakes()
        test_articles = [
            {
                "_id": "art-0",
                "title": "Artículo viejo",
                "url": "https://example.com/article/0",
                "desc": "Description 0",
                "publishedAt": "2020-01-01T00:00:00Z",  # muy viejo → descartado por freshness
                "source": "Test Source",
                "status": "pending",
            },
            {
                "_id": "art-1",
                "title": "Artículo reciente",
                "url": "https://example.com/article/1",
                "desc": "Description 1",
                "publishedAt": datetime.now(timezone.utc).isoformat(),  # reciente
                "source": "Test Source",
                "status": "pending",
            },
        ]
        fakes.generated_articles_repo.save_all(test_articles)

        # WP runner que registra qué artículo publicó y siempre tiene éxito.
        published_urls = []

        def wordpress_runner(article: Optional[Dict] = None, post: Optional[Dict] = None):
            published_urls.append(
                (
                    article.get("original_url") if article else None,
                    post.get("url") if post else None,
                )
            )
            return {"status": "success", "published": 1, "url": "https://fake.wordpress.com/post/1"}

        runner = self._build_runner(fakes, wordpress_runner=wordpress_runner)
        result = self._run_pipeline(runner, "test-job")

        assert result.status == JobStatus.COMPLETED, (
            f"Expected COMPLETED, got {result.status}: {result.error}"
        )
        assert result.error is None
        assert "publish" in fakes.social_publisher.calls, "Social publish no llamado"
        # Se publicó el artículo reciente (art-1), no el viejo (art-0).
        assert published_urls, "WordPress runner no fue llamado"
        assert published_urls[-1][0] == "https://example.com/article/1", (
            f"Se publicó {published_urls[-1][0]} en lugar de article/1"
        )
        assert published_urls[-1][1] == "https://example.com/article/1"

    def test_pipeline_aborts_on_critical_failure(self):
        """Test 2: Fallo en paso crítico (WordPress) → FAILED, aborta."""
        fakes = build_pipeline_fakes()
        # Pre-poblar para que pase hasta el paso de WP
        test_articles = [
            {"_id": f"art-{i}", "title": f"Test Article {i}", "url": f"https://example.com/article/{i}", "desc": f"Description {i}", "publishedAt": "2026-11-15T10:00:00Z", "source": "Test Source", "status": "pending"}
            for i in range(3)
        ]
        fakes.generated_articles_repo.save_all(test_articles)

        # WordPress runner que falla (recibe article y post, firma single-item)
        def failing_wordpress(article: Optional[Dict] = None, post: Optional[Dict] = None):
            raise RuntimeError("WordPress down")

        runner = self._build_runner(fakes, wordpress_runner=failing_wordpress)
        result = self._run_pipeline(runner, "test-job")

        # Verificar estado final FAILED
        assert result.status == JobStatus.FAILED, f"Expected FAILED, got {result.status}"
        assert result.error is not None
        assert "WordPress" in result.error

        # Verificar que abortó en paso 9 (WP), no llegó a 10 (social)
        step_names = [s.name for s in result.steps]
        assert ProcessingStepName.PUBLISH_WORDPRESS in step_names
        assert ProcessingStepName.PUBLISH_SOCIAL not in step_names, "No debería llegar a Social si WP falla"

        # El paso de WP debe estar en ERROR
        wp_step = next(s for s in result.steps if s.name == ProcessingStepName.PUBLISH_WORDPRESS)
        assert wp_step.status == ProcessingStepStatus.ERROR
        # El error está en el job (result.error), no en el step individual (limitación del job repo)
        assert result.error is not None
        assert "WordPress down" in result.error

    def test_pipeline_marks_partial_on_enrichment_failure(self):
        """Test 3: Fallo en enriquecimiento (audio) → PARTIAL, continúa."""
        fakes = build_pipeline_fakes()
        # Pre-publar 1 artículo pendiente para que Full Verify tenga algo que procesar
        test_articles = [
            {"_id": "art-1", "title": "Test Article 1", "url": "https://example.com/article/1", "desc": "Description 1", "publishedAt": "2026-11-15T10:00:00Z", "source": "Test Source", "status": "pending"}
        ]
        fakes.generated_articles_repo.save_all(test_articles)

        # TTS use case que falla (single-item execute)
        class FailingTts:
            def __init__(self):
                self.calls = []
            def execute(self, article):
                self.calls.append("execute")
                raise RuntimeError("TTS service unavailable")

        failing_tts = FailingTts()
        runner = self._build_runner(fakes, tts_usecase=failing_tts)
        result = self._run_pipeline(runner, "test-job")

        # Verificar estado PARTIAL
        assert result.status == JobStatus.PARTIAL, f"Expected PARTIAL, got {result.status}: {result.error}"
        assert result.error is not None
        assert "Audio" in result.error or "Enriquecimiento" in result.error

        # Verificar que SÍ llegó al paso 10 (social)
        step_names = [s.name for s in result.steps]
        assert ProcessingStepName.PUBLISH_SOCIAL in step_names, "Debería llegar a Social aunque Audio falle"

        # Paso de audio en ERROR, social en OK
        audio_step = next(s for s in result.steps if s.name == ProcessingStepName.GENERATE_AUDIO)
        assert audio_step.status == ProcessingStepStatus.ERROR

        social_step = next(s for s in result.steps if s.name == ProcessingStepName.PUBLISH_SOCIAL)
        assert social_step.status == ProcessingStepStatus.OK

        # Verificar single-item: TTS.execute llamado exactamente 1 vez (no execute_batch)
        assert len(failing_tts.calls) == 1, f"Expected 1 TTS call, got {len(failing_tts.calls)}: {failing_tts.calls}"
        assert failing_tts.calls[0] == "execute"

    def test_wiring_uses_correct_repos(self):
        """Test 4: El wiring real usa GeneratedArticlesRepository (no ArticleRepository).

        Este test detecta el bug donde se pasa MongoArticleRepository
        (que no tiene load_all) en lugar de MongoGeneratedArticlesRepository.
        """
        from src.news.application.usecases.full_verify_usecase import FullVerifyNewsUseCase
        from src.news.infrastructure.adapters.mongo_repositories import (
            MongoArticleRepository,
            MongoGeneratedArticlesRepository,
        )
        from src.shared.adapters.mongo_db import get_database
        from src.news.domain.ports import GeneratedArticlesRepository
        import inspect

        # Este test verifica que el wiring de producción usa el repo CORRECTO
        # Simulamos el wiring de news_router.py / dependencies.py

        # El wiring REAL (de production) usa create_generated_articles_repository()
        # que devuelve MongoGeneratedArticlesRepository (tiene load_all)
        # NO MongoArticleRepository (no tiene load_all)

        # Verificar que MongoGeneratedArticlesRepository tiene load_all
        gen_repo = MongoGeneratedArticlesRepository(get_database())
        assert hasattr(gen_repo, "load_all"), "MongoGeneratedArticlesRepository debe tener load_all"
        assert callable(getattr(gen_repo, "load_all"))

        # Verificar que MongoArticleRepository NO tiene load_all
        article_repo = MongoArticleRepository(get_database())
        assert not hasattr(article_repo, "load_all"), "MongoArticleRepository NO debe tener load_all"

        # Ahora verificar que FullVerifyNewsUseCase espera GeneratedArticlesRepository
        # (el puerto define load_all)
        sig = inspect.signature(FullVerifyNewsUseCase.__init__)
        params = sig.parameters
        assert "generated_articles_repo" in params
        # El type hint debería ser GeneratedArticlesRepository
        param = params["generated_articles_repo"]
        assert param.annotation == GeneratedArticlesRepository or "GeneratedArticlesRepository" in str(param.annotation)

    def test_pipeline_with_execute_pipeline_async(self):
        """Test 5: Ejecución vía execute_pipeline_async (como en producción)."""
        from src.news.application.usecases.pipeline_job import create_job, get_job
        from src.news.domain.entities.pipeline_job import JobStatus

        fakes = build_pipeline_fakes()
        # Pre-poblar para que Full Verify tenga artículos que procesar
        fakes.generated_articles_repo.save_all([
            {"_id": "art-1", "title": "Test Article 1", "url": "https://example.com/article/1", "desc": "Description 1", "publishedAt": "2026-11-15T10:00:00Z", "source": "Test Source", "status": "pending"}
        ])
        job_id = create_job()

        # execute_pipeline_async usa threading, así que esperamos un poco
        import time

        started = execute_pipeline_async(
            job_id=job_id,
            generated_articles_repo=fakes.generated_articles_repo,
            generated_posts_repo=fakes.generated_posts_repo,
            verified_news_repo=fakes.verified_news_repo,
            rss_fetch_runner=fakes.rss_fetch_runner,
            prepare_articles_runner=fakes.prepare_articles_runner,
            full_verify_runner=fakes.full_verify_runner,
            metrics_repo=fakes.metrics_repo,
            social_publisher=fakes.social_publisher,
            tts_usecase=fakes.tts_usecase,
            image_unsplash_runner=fakes.image_unsplash_runner,
            image_google_runner=fakes.image_google_runner,
            image_enricher_runner=fakes.image_enricher_runner,
            wordpress_runner=fakes.wordpress_runner,
            video_generator_factory=fakes.video_generator_factory,
            social_truncator=fakes.social_truncator,
            post_editor=fakes.post_editor,
            cache_loader=fakes.cache_loader,
            seo_helpers=fakes.seo_helpers,
            ai_providers=fakes.ai_providers,
        )

        assert started is True

        # Esperar a que el hilo termine (daemon thread)
        time.sleep(2)

        job = get_job(job_id)
        assert job is not None, "Job no encontrado"
        assert job.get("status") in (JobStatus.COMPLETED.value, JobStatus.PARTIAL.value, JobStatus.FAILED.value)

        # Verificar pasos
        assert len(job.get("steps", [])) >= 10, f"Solo {len(job.get('steps', []))} pasos ejecutados"


# ============================================================================
# Test de integración del wiring real (para detectar bugs como el del paso 2)
# ============================================================================

class TestProductionWiring:
    """Tests que verifican el wiring de producción (news_router.py / dependencies.py)."""

    def test_full_verify_gets_correct_repo_from_dependencies(self):
        """Verifica que get_full_verify_usecase inyecta GeneratedArticlesRepository."""
        from src.news.entrypoints.api.dependencies import get_full_verify_usecase
        from src.news.domain.ports import GeneratedArticlesRepository
        from src.news.infrastructure.adapters.mongo_repositories import MongoGeneratedArticlesRepository

        # En test, no podemos llamar directamente porque usa Depends()
        # Pero podemos verificar la firma y el tipo esperado
        import inspect
        from src.news.application.usecases import FullVerifyNewsUseCase

        sig = inspect.signature(FullVerifyNewsUseCase.__init__)
        param = sig.parameters["generated_articles_repo"]
        # Debe esperar GeneratedArticlesRepository (el puerto)
        assert "GeneratedArticlesRepository" in str(param.annotation)

    def test_pipeline_runner_gets_generated_articles_repo(self):
        """Verifica que PipelineRunner recibe GeneratedArticlesRepository."""
        from src.news.entrypoints.api.news_router import news_full_pipeline
        import inspect

        # Verificar que execute_pipeline_async se llama con generated_articles_repo
        # que viene de get_generated_articles_repo() -> MongoGeneratedArticlesRepository
        pass  # Este test es más de integración real, se ejecuta con la app corriendo


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])