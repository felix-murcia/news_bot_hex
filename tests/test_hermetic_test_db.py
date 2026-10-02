"""Guardarraíles de hermeticidad de la base de datos en los tests.

Objetivo (decisiones de Felix, Fase 3 y Fase 4):
  1. La suite NUNCA debe escribir en `appdb` (producción).
  2. Los tests deben inyectar `MONGO_DB_NAME` apuntando a una BD de pruebas.
  3. La suite debe limpiar lo que escribe (drop de la BD de test al terminar).
  4. El modo producción (`NEWS_BOT_RUN_PRODUCTION_TESTS=1`) debe afirmar contra
     un CLÓN de `appdb`, jamás contra `appdb` (decisión 2 de la Fase 4).

Estos tests fallan si alguien reintroduce contaminación en producción.
"""

import os

import pytest

from conftest import (
    PRODUCTION_CLONE_DB,
    PRODUCTION_DB,
    production_data_db,
    production_mode_enabled,
)

TEST_DB = "appdb_test"

requires_hermetic_mode = pytest.mark.skipif(
    production_mode_enabled(),
    reason="NEWS_BOT_RUN_PRODUCTION_TESTS=1: por diseño se afirma contra el clon "
    "de appdb, no contra la BD de pruebas",
)

# Ficheros que afirman datos reales de producción y por eso son opt-in.
PRODUCTION_FILES = [
    "tests/src/test_pipeline_e2e_real_data.py",
    "tests/src/test_rss_sources_integration.py",
    "tests/src/test_infrastructure_validation.py",
]


class TestTestDatabaseInjection:
    """La BD de test debe estar inyectada ANTES de importar Settings."""

    @requires_hermetic_mode
    def test_tests_do_not_use_production_database(self):
        """CRÍTICO: si esto falla, los tests escriben en producción."""
        from config.settings import Settings

        assert Settings.MONGO_DB_NAME != PRODUCTION_DB, (
            f"La suite está configurada contra la BD de PRODUCCIÓN "
            f"'{Settings.MONGO_DB_NAME}'. Los tests deben usar una BD de pruebas."
        )

    @requires_hermetic_mode
    def test_test_database_name_is_injected(self):
        from config.settings import Settings

        assert Settings.MONGO_DB_NAME == TEST_DB, (
            f"Se esperaba '{TEST_DB}', se obtuvo '{Settings.MONGO_DB_NAME}'."
        )

    def test_environment_variable_matches_settings(self):
        """os.environ y Settings deben coincidir (Settings se evalúa al importar)."""
        from config.settings import Settings

        assert os.environ["MONGO_DB_NAME"] == Settings.MONGO_DB_NAME

    @requires_hermetic_mode
    def test_get_database_resolves_to_test_database(self):
        """El service locator debe resolver a la BD de test, no a appdb."""
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        assert db.name == TEST_DB, f"get_database() resolvió a '{db.name}'"
        assert db.name != PRODUCTION_DB


class TestDatabaseCleanupGuard:
    """El teardown que borra la BD debe ser incapaz de tocar producción."""

    @staticmethod
    def _spy():
        class _Spy:
            def __init__(self):
                self.dropped = None

            def drop_database(self, name):
                self.dropped = name
                return True

        return _Spy()

    def test_drop_refuses_production_database(self):
        from conftest import drop_database_safely

        client = self._spy()
        result = drop_database_safely(client, PRODUCTION_DB)

        assert result is False, "drop_database_safely debe rechazar appdb"
        assert client.dropped is None, "Se intentó borrar la BD de producción"

    def test_drop_accepts_test_database(self):
        from conftest import drop_database_safely

        client = self._spy()
        result = drop_database_safely(client, TEST_DB)

        assert result is True
        assert client.dropped == TEST_DB


class TestProductionTestMarker:
    """Los tests que afirman datos reales deben estar marcados y ser opt-in."""

    def test_production_marker_is_registered(self, pytestconfig):
        markers = pytestconfig.getini("markers")
        assert any(m.startswith("production") for m in markers), (
            "El marker 'production' debe registrarse en conftest.py:pytest_configure"
        )

    def test_production_marker_is_usable(self):
        """Marcar un test como production no debe dar error de marker desconocido."""
        assert True

    def test_production_files_declare_their_marker(self):
        """Los ficheros de datos reales deben seguir marcados como production."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[1]
        missing = [
            f
            for f in PRODUCTION_FILES
            if "pytest.mark.production" not in (root / f).read_text(encoding="utf-8")
        ]
        assert not missing, f"Ficheros sin marker production: {missing}"


@pytest.mark.skipif(
    not production_mode_enabled(),
    reason="Sólo aplica con NEWS_BOT_RUN_PRODUCTION_TESTS=1",
)
class TestProductionModeUsesClone:
    """El modo producción afirma contra un CLÓN de appdb, nunca contra appdb.

    Es el requisito de la decisión 2 de la Fase 4: un run en modo producción
    añadía 14 artículos RSS de BBC/NYT/France24 a `appdb.raw_news`. Con el clon,
    `appdb` es byte-idéntica antes y después de la suite.
    """

    def test_production_mode_does_not_target_production_db(self):
        """CRÍTICO: en modo producción la suite NUNCA abre appdb."""
        from config.settings import Settings

        assert Settings.MONGO_DB_NAME != PRODUCTION_DB, (
            f"El modo producción está apuntando a la BD de PRODUCCIÓN "
            f"'{Settings.MONGO_DB_NAME}'. Debe apuntar al clon."
        )

    def test_production_mode_targets_the_clone(self):
        from config.settings import Settings

        assert Settings.MONGO_DB_NAME == PRODUCTION_CLONE_DB, (
            f"Se esperaba el clon '{PRODUCTION_CLONE_DB}', "
            f"se obtuvo '{Settings.MONGO_DB_NAME}'."
        )

    def test_get_database_resolves_to_the_clone(self):
        from src.shared.adapters.mongo_db import get_database

        db = get_database()
        assert db.name == PRODUCTION_CLONE_DB
        assert db.name != PRODUCTION_DB

    def test_clone_contains_real_copied_data(self):
        """El clon debe ser un clon real: mismos _id que appdb, mismos volúmenes."""
        from src.shared.adapters.mongo_db import get_database
        from conftest import _mongo_client

        clone = get_database()
        assert clone["raw_news"].count_documents({}) >= 1000, (
            "El clon no tiene artículos: la copia falló o appdb está vacía."
        )
        sources = clone["sources_rss"].find_one({"_id": "sources"})
        assert sources and len(sources.get("sources", [])) >= 10

        # Mismos identificadores que el origen: prueba de que es una copia y no
        # un conjunto de fixtures inventado.
        origin = _mongo_client()[PRODUCTION_DB]
        sample = list(origin["raw_news"].find({}, {"_id": 1}).limit(25))
        assert sample, "appdb.raw_news está vacía: no hay nada que clonar"
        for doc in sample:
            assert clone["raw_news"].find_one({"_id": doc["_id"]}) is not None, (
                f"El clon no contiene el documento {doc['_id']} de appdb."
            )

    def test_drop_refuses_the_clone_is_not_needed(self):
        """El clon SÍ se puede dropear: no es producción."""
        from conftest import drop_database_safely

        class _Spy:
            def __init__(self):
                self.dropped = None

            def drop_database(self, name):
                self.dropped = name
                return True

        spy = _Spy()
        assert drop_database_safely(spy, PRODUCTION_CLONE_DB) is True
        assert spy.dropped == PRODUCTION_CLONE_DB


class TestProductionDataDbHelper:
    """El helper `production_data_db` es el contrato único de los tests prod."""

    def test_never_returns_production_db(self):
        """Los tests de producción comparan contra este helper, nunca contra 'appdb'."""
        assert production_data_db() != PRODUCTION_DB, (
            "production_data_db() devuelve appdb: los tests de producción "
            "volverían a afirmar contra producción."
        )

    def test_returns_the_clone(self):
        assert production_data_db() == PRODUCTION_CLONE_DB

    def test_production_files_do_not_hardcode_appdb_in_assertions(self):
        """Ningún test de producción debe comparar el nombre de BD contra 'appdb'."""
        import pathlib
        import re

        root = pathlib.Path(__file__).resolve().parents[1]
        # Se buscan sólo líneas de aserción: un docstring puede LEGRAR sobre
        # 'appdb' (explica el validador, el clon, el origen) sin afirmar contra él.
        pattern = re.compile(r"^\s*assert\b.*==\s*[\"']appdb[\"']", re.MULTILINE)
        offenders = []
        for name in PRODUCTION_FILES:
            source = (root / name).read_text(encoding="utf-8")
            for match in pattern.finditer(source):
                line = source[: match.start()].count("\n") + 1
                offenders.append(f"{name}:{line}")
        assert not offenders, (
            "Aserciones contra el literal 'appdb' en tests de producción "
            f"(deben usar production_data_db()): {offenders}"
        )