"""Hermeticidad de credenciales en la suite de tests.

Decisión de Felix (Fase 4, decisión 4): la suite DEBE pasar sola, sin depender
de que el `.env` del desarrollador tenga las variables de redes sociales puestas.

Por qué:
    `src/shared/adapters/facebook_publisher.py:22` y
    `src/shared/adapters/mastodon_publisher.py:26` lanzan en el **import** si
    falta la credencial. Cualquier test que importe (directa o indirectamente)
    `src.news.entrypoints.cli` reventaba con 23 ValueError/RuntimeError cuando el
    `.env` local traía las variables vacías. El fallo no era del código bajo
    prueba: era del entorno.

Qué se inyecta:
    Valores INERTES, deliberadamente no secretos, sólo para que el import no
    reviente. Ningún test hace llamadas de red con ellos.

Cómo se sobreescribe:
    Exportando la variable real ANTES de pytest; conftest sólo rellena lo que
    esté ausente o vacío.
"""

import importlib
import os

import pytest

# Mismas variables que la inyección de conftest.py declara como inertes.
INERT_CREDENTIALS = (
    "FACEBOOK_PAGE_ID",
    "FACEBOOK_PAGE_ACCESS_TOKEN",
    "MASTODON_INSTANCE_URL",
    "MASTODON_ACCESS_TOKEN",
    "BLUESKY_HANDLE",
    "BLUESKY_APP_PASSWORD",
)

# Publicadores que lanzan en el import si su credencial está vacía.
IMPORT_GATED_MODULES = (
    "src.shared.adapters.facebook_publisher",
    "src.shared.adapters.mastodon_publisher",
)


class TestInertCredentialsArePresent:
    """El entorno de test debe tener credenciales inertes disponibles."""

    @pytest.mark.parametrize("var_name", INERT_CREDENTIALS)
    def test_credential_is_non_empty(self, var_name):
        """Cada credencial usada por los publicadores debe estar presente."""
        value = os.environ.get(var_name, "")
        assert value.strip(), (
            f"{var_name} está vacía en el entorno de test. conftest.py debe "
            f"inyectar un valor inerte para las que falten."
        )

    def test_injected_values_are_clearly_inert(self):
        """Los valores por defecto no deben parecer secretos ni endpoints reales."""
        from conftest import INERT_PLACEHOLDERS

        for name, placeholder in INERT_PLACEHOLDERS.items():
            # Cada placeholder debe delatar que es de test: prefijo 'test-' para
            # tokens/handles, o dominio reservado '.test' (RFC 6761) para URLs.
            # Un dominio reservado nunca resuelve en DNS, así que un intento de
            # red accidental falla de inmediato y en local.
            is_inert = placeholder.startswith("test-") or ".test" in placeholder
            assert is_inert, (
                f"El placeholder de {name} no es reconocible como inerte: "
                f"{placeholder!r}. Debe empezar por 'test-' o usar un dominio "
                f"reservado '.test'."
            )
            assert len(placeholder) < 40, f"{name}: placeholder sospechosamente largo"


class TestPublisherModulesImport:
    """Los módulos que lancaban en el import deben importar sin credenciales."""

    @pytest.mark.parametrize("module_path", IMPORT_GATED_MODULES)
    def test_module_imports(self, module_path):
        module = importlib.import_module(module_path)
        assert module is not None

    def test_cli_entrypoint_package_imports(self):
        """El paquete que arrastraba a los 4 publicadores debe importar."""
        module = importlib.import_module("src.news.entrypoints.cli")
        assert module is not None


class TestNoRealNetworkFromUnitTests:
    """Los tests unitarios no deben salir a la red con credenciales reales."""

    def test_openrouter_adapter_test_mocks_the_network(self):
        """El test del adaptador de OpenRouter no puede llamar a la API real."""
        import inspect
        import pathlib

        import tests.src.test_shared_adapters as mod

        root = pathlib.Path(inspect.getfile(mod))
        source = root.read_text(encoding="utf-8")
        body = _class_body(source, "TestOpenRouterAdapter")

        # Si el test exercises `generate_content`/`generate`, la red queda abierta.
        for network_call in ("adapter.generate", "generate_content(", "requests.post"):
            assert network_call not in body, (
                f"TestOpenRouterAdapter llama a red real ({network_call}). "
                f"Debe mockear el cliente HTTP o usar el proveedor `mock`."
            )

    def test_ai_provider_is_never_a_live_provider_in_unit_tests(self):
        """El proveedor por defecto de la suite debe ser `mock` o estar vacío."""
        provider = os.environ.get("AI_PROVIDER", "").strip().lower()
        # La suite es hermética: si el .env del dev trae openrouter/gemini, la
        # inyección debe reemplazarlo por `mock`.
        assert provider == "mock", (
            f"AI_PROVIDER='{provider}' en la suite de tests: eso habilita llamadas "
            f"de red reales. conftest.py debe forzarlo a 'mock'."
        )


def _class_body(source: str, class_name: str) -> str:
    """Extrae el cuerpo de una clase de un fichero de tests (test TDD)."""
    lines = source.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith(f"class {class_name}"))
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("class "):
            return "\n".join(lines[start + 1 : i])
    return "\n".join(lines[start + 1 :])