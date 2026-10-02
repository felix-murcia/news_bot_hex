"""Contrato del fixture de CI (`scripts/seed_ci_production_db.py`).

El job de producción en CI (decisión 5 de Felix, Fase 4) siembra `appdb` para que
el clon tenga datos. Estos tests comprueban que ese fixture cumple EXACTAMENTE lo
que afirman los tests marcados `production`. Si el seed se queda corto o cambia
de forma, el job de CI falla aquí y no all dial del pipeline.

El seed se siembra en una BD propia (`appdb_seed_probe`), nunca en la BD de
pruebas ni en `appdb`, y se dropea al terminar.
"""

import importlib.util
import pathlib
import sys

import pytest

SEED_SCRIPT = (
    pathlib.Path(__file__).resolve().parents[1] / "scripts" / "seed_ci_production_db.py"
)
PROBE_DB = "appdb_seed_probe"

# Por encima de `StartupValidator.MIN_ARTICLES` (1000), igual que el seed de CI.
SEED_ARTICLE_COUNT = 1200


def _load_seed_module():
    spec = importlib.util.spec_from_file_location("seed_ci_production_db", SEED_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def seeded_db():
    """Siembra el fixture en una BD desechable y la devuelve."""
    from conftest import _mongo_client, drop_database_safely

    module = _load_seed_module()
    client = _mongo_client()
    db = client[PROBE_DB]
    module.seed(db, SEED_ARTICLE_COUNT)
    try:
        yield db
    finally:
        drop_database_safely(client, PROBE_DB)


class TestSeedMeetsStartupValidatorThresholds:
    """El seed debe satisfacer `StartupValidator`, que aborta el boot si no."""

    def test_articles_meet_minimum(self, seeded_db):
        from src.shared.infrastructure.startup_validator import StartupValidator

        count = seeded_db["raw_news"].count_documents({})
        assert count >= StartupValidator.MIN_ARTICLES, (
            f"El seed deja {count:,} artículos; el validador exige "
            f"{StartupValidator.MIN_ARTICLES:,}."
        )

    def test_rss_sources_meet_minimum(self, seeded_db):
        from src.shared.infrastructure.startup_validator import StartupValidator

        doc = seeded_db["sources_rss"].find_one({"_id": "sources"})
        assert doc is not None, "sources_rss debe contener el documento _id='sources'"
        assert len(doc["sources"]) >= StartupValidator.MIN_RSS_SOURCES, (
            f"El seed deja {len(doc['sources'])} fuentes; el validador exige "
            f"{StartupValidator.MIN_RSS_SOURCES}."
        )

    def test_required_collections_exist_including_empty_ones(self, seeded_db):
        from src.shared.infrastructure.startup_validator import StartupValidator

        existing = set(seeded_db.list_collection_names())
        missing = set(StartupValidator.REQUIRED_COLLECTIONS) - existing
        assert not missing, (
            f"Faltan colecciones obligatorias en el seed: {missing}. Sin ellas el "
            f"clon tampoco las tendría y el job de CI fallaría."
        )


class TestSeedSatisfiesProductionAssertions:
    """Los tests de producción afirman sobre esto; el seed debe cumplirlas."""

    def test_known_quality_sources_are_present(self, seeded_db):
        """test_rss_sources_are_from_production_appdb exige uno de estos cuatro."""
        doc = seeded_db["sources_rss"].find_one({"_id": "sources"})
        names = {s["source"] for s in doc["sources"]}
        expected = {"BBC World", "New York Times", "Reuters", "NPR"}
        assert names & expected, (
            f"El seed no incluye ninguna fuente de {expected}. "
            f"test_rss_sources_are_from_production_appdb fallaría en CI."
        )

    def test_at_least_one_quality_outlet(self, seeded_db):
        """test_rss_sources_are_production_quality cuenta salidas conocidas."""
        doc = seeded_db["sources_rss"].find_one({"_id": "sources"})
        names = {s["source"] for s in doc["sources"]}
        known = {"BBC", "Reuters", "AP", "New York Times", "NPR", "CNN"}
        assert any(any(k in name for k in known) for name in names), (
            "test_rss_sources_are_production_quality fallaría: ninguna fuente "
            f"reconocida en {sorted(names)}"
        )

    def test_no_sensationalist_sources(self, seeded_db):
        """test_no_hardcoded_default_sources_in_production prohíbe estas tres."""
        doc = seeded_db["sources_rss"].find_one({"_id": "sources"})
        names = {s["source"] for s in doc["sources"]}
        forbidden = {"El Mundo", "El Español", "La Vanguardia"}
        assert not (names & forbidden), f"Fuentes prohibidas en el seed: {names & forbidden}"

    def test_no_hardcoded_placeholder_sources(self, seeded_db):
        """test_no_pipeline_uses_hardcoded_test_data prohíbe estos nombres."""
        doc = seeded_db["sources_rss"].find_one({"_id": "sources"})
        names = {s["source"] for s in doc["sources"]}
        forbidden = {"TestSource", "MockFeed", "DefaultSource"}
        assert not (names & forbidden), f"Fuentes de test en el seed: {names & forbidden}"

    def test_every_source_has_valid_fields(self, seeded_db):
        """test_sources_urls_are_valid / test_all_sources_have_non_empty_names."""
        doc = seeded_db["sources_rss"].find_one({"_id": "sources"})
        for index, source in enumerate(doc["sources"]):
            name = source.get("source", "").strip()
            url = source.get("url", "").strip()
            assert name, f"Fuente {index} sin nombre"
            assert len(name) >= 3, f"Fuente {index} con nombre demasiado corto: {name!r}"
            assert url.startswith("http"), f"Fuente {index} con URL inválida: {url!r}"
            assert len(url) > 10, f"Fuente {index} con URL demasiado corta: {url!r}"
            assert "." in url, f"Fuente {index} con URL sin dominio: {url!r}"

    def test_every_article_has_valid_fields(self, seeded_db):
        """test_article_urls_are_valid y el mapeo de `Article.from_dict`."""
        from datetime import datetime

        doc = seeded_db["sources_rss"].find_one({"_id": "sources"})
        valid_sources = {s["source"] for s in doc["sources"]}

        sample = list(seeded_db["raw_news"].find({}).limit(200))
        assert len(sample) == 200
        for article in sample:
            url = article.get("url")
            assert url and url.startswith("http"), f"URL inválida: {url!r}"
            assert len(url) > 10, f"URL demasiado corta: {url!r}"
            assert article.get("source") in valid_sources, (
                f"Artículo cita '{article.get('source')}', que no está en "
                f"sources_rss (test_article_sources_match_rss_sources fallaría)."
            )
            # publishedAt debe ser parseable: get_recent_articles lo compara.
            datetime.fromisoformat(article["publishedAt"].replace("Z", ""))

    def test_articles_map_to_domain_entities(self, seeded_db):
        """`Article.from_dict` debe producir entidades con los atributos que
        test_article_repository_loads_real_articles comprueba."""
        from src.news.domain.entities.article import Article

        for raw in seeded_db["raw_news"].find({}).limit(20):
            article = Article.from_dict(raw)
            assert hasattr(article, "title") and article.title
            assert hasattr(article, "url") and article.url
            assert hasattr(article, "source") and article.source

    def test_repository_reads_the_seed(self, seeded_db):
        """Los repositorios reales deben poder leer el fixture."""
        from src.news.infrastructure.adapters import (
            MongoArticleRepository,
            MongoRSSSourceRepository,
        )

        article_repo = MongoArticleRepository(db=seeded_db)
        source_repo = MongoRSSSourceRepository(db=seeded_db)

        assert article_repo.count_articles() >= 1000
        assert len(source_repo.get_all_sources()) >= 10
        assert len(article_repo.get_all_articles()) > 0


class TestSeedGuardrails:
    """El seed no debe poder tocar appdb por accidente."""

    def test_refuses_appdb_without_explicit_flag(self):
        module = _load_seed_module()

        assert module.main(["--db", "appdb"]) == 2, (
            "Sembrar appdb sin --allow-production debe abortar con código 2."
        )

    def test_allows_other_databases(self):
        """Sin el flag, una BD que no sea appdb sí puede sembrarse."""
        module = _load_seed_module()
        assert module.main(["--db", PROBE_DB, "--count", "5"]) == 0

    def test_seed_is_deterministic(self):
        """Dos invocaciones producen exactamente el mismo contenido."""
        module = _load_seed_module()
        assert module.build_articles(50) == module.build_articles(50)

    def test_seed_is_ascii_only(self):
        """Sin no-ASCII: el fixture no depende de la codificación del runner."""
        module = _load_seed_module()
        for article in module.build_articles(50):
            for value in article.values():
                assert str(value).isascii(), f"Caracter no-ASCII en el seed: {value!r}"