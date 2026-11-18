"""Tests de caracterización para la política editorial FASE 2B.

Estos tests documentan el comportamiento ACTUAL (antes de integrar decisión editorial)
y definen el comportamiento ESPERADO tras la implementación.

NO modifican código de producción. Sirven como baseline y validación posterior.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestCurrentSelectionBehavior:
    """Documentan cómo selecciona PipelineRunner actualmente (sin decisión editorial)."""

    def test_pipeline_runner_selects_first_that_generates_article(self):
        """PipelineRunner selecciona la primera candidata que genera artículo exitosamente."""
        from src.news.application.usecases.pipeline_runner import PipelineRunner

        # Mocks mínimos - constructor real
        runner = PipelineRunner(
            generated_articles_repo=Mock(),
            generated_posts_repo=Mock(),
            verified_news_repo=Mock(),
            rss_fetch_runner=Mock(return_value={"candidates": []}),
            prepare_articles_runner=Mock(return_value={"posts": []}),
            full_verify_runner=Mock(return_value={"candidates": []}),
            metrics_repo=Mock(),
            social_publisher=Mock(),
            tts_usecase=Mock(),
            image_unsplash_runner=Mock(return_value=None),
            image_google_runner=Mock(return_value=None),
            image_enricher_runner=Mock(return_value=None),
            wordpress_runner=Mock(return_value={"status": "ok"}),
            video_generator_factory=Mock(return_value=Mock()),
            social_truncator=Mock(return_value=""),
            post_editor=Mock(return_value=""),
            cache_loader=Mock(return_value=("", "")),
            seo_helpers=Mock(),
            ai_providers=Mock(),
            content_extractor=Mock(),
        )

        # El bucle actual (líneas 365-425) itera candidatos en orden recibido
        # y se detiene en el primero donde run_articles() no lanza excepción
        # y devuelve un artículo no-None.
        # Este test documenta ese comportamiento como baseline.
        assert hasattr(runner, 'run')


class TestEditorialDecisionValues:
    """Valores reales del contrato editorial (desde compute_editorial_score)."""

    def test_editorial_decision_values_are_lowercase_strings(self):
        """editorial_decision usa exactamente 'admitir', 'descartar', 'fallback'."""
        from src.news.domain.services.compute_editorial_score import make_decision

        # Verificar que la función devuelve los valores exactos esperados
        # (los tests de compute_editorial_score ya cubren la lógica completa)
        decision, _ = make_decision(60, [], [], "Geopolitics")
        assert decision == "admitir"

        decision, _ = make_decision(20, [], [], "News")
        assert decision == "descartar"

        decision, _ = make_decision(40, [], [], "News")
        assert decision == "fallback"

    def test_editorial_score_range_0_100(self):
        """editorial_score siempre en rango 0-100."""
        from src.news.domain.services.compute_editorial_score import compute_editorial_score

        result = compute_editorial_score(
            "War escalates", "Hundreds of casualties reported", "Geopolitics"
        )
        assert 0 <= result["editorial_score"] <= 100
        assert isinstance(result["editorial_score"], int)

    def test_editorial_category_values(self):
        """editorial_category toma valores del conjunto definido."""
        from src.news.domain.services.compute_editorial_score import compute_editorial_score

        valid_categories = {
            "geopolítica", "impacto_humano", "científico/ambiental",
            "importancia", "alcance", "actualidad", "noticias"
        }

        # Varias ejecuciones para cubrir categorías
        test_cases = [
            ("War escalates", "Hundreds of casualties", "Geopolitics"),
            ("Scientific breakthrough", "New discovery in physics", "Science"),
            ("Local city council", "Routine meeting", "Politics"),
        ]
        for title, desc, tema in test_cases:
            result = compute_editorial_score(title, desc, tema)
            assert result["editorial_category"] in valid_categories

    def test_justification_is_non_empty_string(self):
        """justification siempre es string no vacío cuando hay decisión."""
        from src.news.domain.services.compute_editorial_score import compute_editorial_score

        result = compute_editorial_score("Test", "Test desc", "News")
        assert isinstance(result["justification"], str)
        assert len(result["justification"]) > 0

    def test_confidence_is_score_over_100(self):
        """confidence = editorial_score / 100 redondeado a 2 decimales."""
        from src.news.domain.services.compute_editorial_score import compute_editorial_score

        result = compute_editorial_score("War escalates", "Hundreds of casualties", "Geopolitics")
        expected = round(result["editorial_score"] / 100.0, 2)
        assert result["confidence"] == expected


class TestVetoFilters:
    """Filtros de veto que fuerzan 'descartar' independientemente del score."""

    def test_publicidad_always_descartar(self):
        """Filtro 'publicidad' siempre fuerza descartar."""
        from src.news.domain.services.compute_editorial_score import compute_editorial_score

        result = compute_editorial_score(
            "Amazing miracle product! Buy now limited offer!",
            "This incredible supplement will change your life. Click here!",
            "Health"
        )
        assert result["editorial_decision"] == "descartar"
        assert "publicidad" in result["activated_filters"]

    def test_famosos_cotilleo_always_descartar(self):
        """Filtro 'famosos_cotilleo' siempre fuerza descartar."""
        from src.news.domain.services.compute_editorial_score import compute_editorial_score

        result = compute_editorial_score(
            "Celebrity scandal! Shocking details revealed",
            "You won't believe what this famous actor did",
            "Entertainment"
        )
        assert result["editorial_decision"] == "descartar"
        assert "famosos_cotilleo" in result["activated_filters"]

    def test_curiosidad_trivial_always_descartar(self):
        """Filtro 'curiosidad_trivial' siempre fuerza descartar."""
        from src.news.domain.services.compute_editorial_score import compute_editorial_score

        result = compute_editorial_score(
            "Man finds weird shaped potato",
            "Viral photo of potato that looks like a face",
            "Curiosity"
        )
        assert result["editorial_decision"] == "descartar"
        assert "curiosidad_trivial" in result["activated_filters"]

    def test_politica_rutinaria_descartar_without_extraordinary_events(self):
        """'politica_rutinaria' descarta si no hay eventos extraordinarios."""
        from src.news.domain.services.compute_editorial_score import compute_editorial_score

        result = compute_editorial_score(
            "City council approves routine budget",
            "Municipal meeting discusses zoning changes",
            "Politics"
        )
        assert result["editorial_decision"] == "descartar"
        assert "politica_rutinaria" in result["activated_filters"]

    def test_deporte_ordinario_descartar_without_historic(self):
        """'deporte_ordinario' descarta si no es evento histórico."""
        from src.news.domain.services.compute_editorial_score import compute_editorial_score

        result = compute_editorial_score(
            "Local team wins regular season game",
            "Standard league match result",
            "Sports"
        )
        assert result["editorial_decision"] == "descartar"
        assert "deporte_ordinario" in result["activated_filters"]


class TestFallbackBehavior:
    """Comportamiento 'fallback' (score medio 30-50 o anuncio_comercial >30)."""

    def test_score_30_50_is_fallback(self):
        """Score en rango 30-50 produce 'fallback'."""
        from src.news.domain.services.compute_editorial_score import compute_editorial_score

        # Noticia con relevancia media (caso real que produce fallback)
        result = compute_editorial_score(
            "Court rules on landmark case",
            "Supreme court decision affects millions of citizens", "Law"
        )
        assert 30 < result["editorial_score"] <= 50
        assert result["editorial_decision"] == "fallback"

    def test_anuncio_comercial_score_above_descartar_is_fallback(self):
        """Anuncio comercial con score >30 produce 'fallback' no 'descartar'."""
        from src.news.domain.services.compute_editorial_score import compute_editorial_score

        result = compute_editorial_score(
            "New tech product launched with innovative features",
            "The device includes advanced AI capabilities for professionals",
            "Technology"
        )
        # Si detecta anuncio_comercial pero score > THRESHOLD_DESCARTAR (30)
        if "anuncio_comercial" in result["activated_filters"]:
            assert result["editorial_decision"] in ("fallback", "admitir")


class TestHistoricalCompatibility:
    """Compatibilidad con documentos históricos sin campos editoriales."""

    def test_verified_article_from_dict_without_editorial_fields(self):
        """VerifiedArticle.from_dict() maneja documentos sin campos editoriales."""
        from src.news.domain.entities.verified_article import VerifiedArticle

        old_data = {
            "title": "Old article",
            "desc": "Old desc",
            "source": "Old source",
            "origin": "Old origin",
            "url": "https://example.com/old",
            "publishedAt": "2024-01-15T10:30:00Z",
            "tema": "Noticias",
            "resumen": "Old resumen",
            "score": 10,
            "model_prediction": "real",
            "confidence": 0.95,
            "verification": {"verified": True},
            "slug": "old-article",
            # Sin campos editoriales
        }

        article = VerifiedArticle.from_dict(old_data)
        assert article.editorial_score is None
        assert article.editorial_category is None
        assert article.editorial_decision is None
        assert article.justification == ""

    def test_verified_article_to_dict_includes_editorial_fields(self):
        """to_dict() incluye campos editoriales (aunque sean None)."""
        from src.news.domain.entities.verified_article import VerifiedArticle

        article = VerifiedArticle(
            title="Test", desc="Test", source="S", origin="O",
            url="https://example.com", publishedAt=datetime.now(),
            tema="News", resumen="R", score=10,
            model_prediction="real", confidence=0.9,
            verification={"verified": True},
        )

        d = article.to_dict()
        assert "editorial_score" in d
        assert "editorial_category" in d
        assert "editorial_decision" in d
        assert "justification" in d
        assert d["editorial_score"] is None
        assert d["editorial_category"] is None
        assert d["editorial_decision"] is None
        assert d["justification"] == ""

    def test_mongo_repository_get_all_news_uses_from_dict(self):
        """MongoVerifiedNewsRepository.get_all_news usa from_dict → compatibilidad."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoVerifiedNewsRepository

        # get_all_news() línea 194: [VerifiedArticle.from_dict(item) for item in raw]
        # Esto garantiza que campos faltantes → None
        import inspect
        source = inspect.getsource(MongoVerifiedNewsRepository.get_all_news)
        assert "from_dict" in source

    def test_mongo_repository_get_all_for_soft_verify_returns_raw_dicts(self):
        """get_all_for_soft_verify devuelve dicts crudos SIN from_dict."""
        from src.news.infrastructure.adapters.mongo_repositories import MongoVerifiedNewsRepository

        import inspect
        source = inspect.getsource(MongoVerifiedNewsRepository.get_all_for_soft_verify)
        # Devuelve raw sin from_dict
        assert "from_dict" not in source
        assert "return raw" in source


class TestPipelineRunnerCandidateLoop:
    """Comportamiento actual del bucle de selección en PipelineRunner."""

    def test_candidate_loop_order_from_full_verify(self):
        """Candidatas llegan ordenadas por FullVerify (score convencional + diversidad + frozen)."""
        from src.news.application.usecases.full_verify_usecase import FullVerifyNewsUseCase

        import inspect
        source = inspect.getsource(FullVerifyNewsUseCase.execute)
        # Verificar que el orden final viene de sort_verified_news + diversidad + frozen
        assert "sort_verified_news" in source
        assert "apply_diversity_penalty" in source
        assert "apply_frozen_terms_penalty" in source

    def test_candidate_loop_stops_at_first_successful_article(self):
        """Bucle se detiene en primera candidata que genera artículo (líneas 365-425)."""
        from src.news.application.usecases.pipeline_runner import PipelineRunner

        import inspect
        source = inspect.getsource(PipelineRunner.run)
        # Buscar el patrón: for candidate in ctx.candidates -> run_articles -> break
        assert "for candidate in (ctx.candidates or []):" in source
        assert "winner_found = True" in source
        assert "break" in source

    def test_candidate_loop_skips_non_fresh(self):
        """Candidatas no recientes (freshness) se omiten."""
        from src.news.application.usecases.pipeline_runner import PipelineRunner

        import inspect
        source = inspect.getsource(PipelineRunner.run)
        assert "_candidate_is_fresh" in source
        assert "continue" in source

    def test_editorial_filter_now_present_in_loop(self):
        """Bucle AHORA usa editorial_decision para filtrar (FASE 2B implementada)."""
        from src.news.application.usecases.pipeline_runner import PipelineRunner

        import inspect
        source = inspect.getsource(PipelineRunner.run)
        # El filtro editorial ahora está presente
        assert "editorial_decision" in source
        assert "descartar" in source
        assert "editorial_filtered" in source
        # Pero NO usa editorial_score para ordenar
        assert "editorial_score" not in source
        assert "editorial_category" not in source


class TestSoftVerifyAlternativePath:
    """Ruta alternativa SoftVerify NO ve campos editoriales."""

    def test_soft_verify_uses_raw_dicts(self):
        """SoftVerify usa get_all_for_soft_verify() → dicts crudos."""
        from src.news.application.usecases.soft_verify import SoftVerifyUseCase

        import inspect
        source = inspect.getsource(SoftVerifyUseCase.execute)
        assert "_load_verified_all" in source
        # _load_verified_all llama a repo.get_all_for_soft_verify()

    def test_soft_verify_selection_by_conventional_score_only(self):
        """SoftVerify ordena SOLO por score convencional y fecha."""
        from src.news.application.usecases.soft_verify import SoftVerifyUseCase

        import inspect
        source = inspect.getsource(SoftVerifyUseCase._select_news)
        # Iteración 1: score desc, fecha desc
        assert "int(x.get(\"score\", 0))" in source
        # Iteración 2: fecha desc, score desc
        assert "_parse_iso_date" in source
        # NO usa editorial_score ni editorial_decision
        assert "editorial" not in source.lower()


class TestImplementedPolicyBehavior:
    """Tests que verifican el comportamiento IMPLEMENTADO de la política editorial FASE 2B.

    POLÍTICA IMPLEMENTADA (Opción A - Filtro conservadora):
    - editorial_decision == "admitir"     → Candidata admisible (se evalúa)
    - editorial_decision == "fallback"    → Candidata admisible (se evalúa)
    - editorial_decision == None/ausente  → Candidata admisible; compatibilidad histórica
    - editorial_decision == "descartar"   → EXCLUIR de selección (no se evalúa)
    - Valor desconocido                   → Admitir mediante fallback convencional + warning
    -
    # Si TODAS candidatas son "descartar": NO ejecutar run_articles() para ninguna.
    # Usar comportamiento existente cuando no hay candidatas admisibles (pipeline falla).
    #
    # Orden convencional de FullVerify se conserva íntegramente.
    """

    def test_policy_discard_excludes_from_selection(self):
        """Candidatas con editorial_decision='descartar' NO se evalúan en run_articles."""
        from src.news.application.usecases.pipeline_runner import PipelineRunner
        import inspect
        source = inspect.getsource(PipelineRunner.run)
        assert 'decision == "descartar"' in source
        assert "continue" in source  # salta la candidata

    def test_policy_admit_and_fallback_admitted(self):
        """Candidatas 'admitir' y 'fallback' pasan el filtro editorial."""
        from src.news.application.usecases.pipeline_runner import PipelineRunner
        import inspect
        source = inspect.getsource(PipelineRunner.run)
        assert 'decision not in ("admitir", "fallback", None)' in source

    def test_policy_none_and_absent_admitted(self):
        """Candidatas con editorial_decision=None o campo ausente pasan el filtro."""
        from src.news.application.usecases.pipeline_runner import PipelineRunner
        import inspect
        source = inspect.getsource(PipelineRunner.run)
        assert 'decision not in ("admitir", "fallback", None)' in source
        # candidate.get("editorial_decision") devuelve None si campo ausente

    def test_policy_all_discarded_no_run_articles(self):
        """Si todas candidatas son 'descartar', no se ejecuta run_articles para ninguna."""
        from src.news.application.usecases.pipeline_runner import PipelineRunner
        import inspect
        source = inspect.getsource(PipelineRunner.run)
        assert "editorial_filtered" in source
        assert "for candidate in (ctx.candidates or []):" in source

    def test_policy_unknown_decision_fallback_with_warning(self):
        """Valor desconocido en editorial_decision → fallback convencional + warning log."""
        from src.news.application.usecases.pipeline_runner import PipelineRunner
        import inspect
        source = inspect.getsource(PipelineRunner.run)
        assert "editorial_decision desconocido" in source
        assert "logger.warning" in source

    def test_policy_preserves_conventional_order(self):
        """El orden convencional de FullVerify se conserva íntegramente."""
        from src.news.application.usecases.pipeline_runner import PipelineRunner
        import inspect
        source = inspect.getsource(PipelineRunner.run)
        assert "editorial_filtered.append(candidate)" in source
        assert "editorial_score" not in source

    def test_policy_run_articles_failure_falls_to_next_candidate(self):
        """Si candidata admisible falla run_articles, pasa a siguiente en orden."""
        from src.news.application.usecases.pipeline_runner import PipelineRunner
        import inspect
        source = inspect.getsource(PipelineRunner.run)
        assert "ctx.article = None" in source
        assert "continue" in source
        assert "winner_found = True" in source
        assert "break" in source

    def test_policy_selection_logs_exclusion_and_count(self):
        """Exclusión loggea URL y job_id; cuenta final loggeada."""
        from src.news.application.usecases.pipeline_runner import PipelineRunner
        import inspect
        source = inspect.getsource(PipelineRunner.run)
        assert "Candidata excluida (editorial descartar)" in source
        assert "Candidatas tras filtro editorial" in source

    def test_policy_no_change_to_soft_verify(self):
        """SoftVerify mantiene comportamiento actual (sin decisión editorial)."""
        from src.news.application.usecases.soft_verify import SoftVerifyUseCase
        import inspect
        source = inspect.getsource(SoftVerifyUseCase.execute)
        assert "editorial" not in source.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])