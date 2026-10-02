"""Guard: dead use-cases and their unused providers must stay deleted.

Context (T-DELETE): ``ProcessUrlCompleteUseCase`` had zero references, and the
``publishing_pipeline`` trio was wired into ``dependencies.py`` but injected by
no router. Per the project decision "if a use-case is unused, delete it so no
residue remains", the modules and their providers are removed.

This test fails if any of them is reintroduced.
"""

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DELETED_MODULES = [
    "src/news/application/usecases/process_url_complete.py",
    "src/news/application/usecases/publishing_pipeline.py",
]

DELETED_SYMBOLS = [
    "ProcessUrlCompleteUseCase",
    "ImageFetcherUseCase",
    "ImageEnricherUseCase",
    "PublishersUseCase",
]

DELETED_PROVIDERS = [
    "get_image_fetcher_usecase",
    "get_image_enricher_usecase",
    "get_publishers_usecase",
]

SRC = PROJECT_ROOT / "src"
TESTS = PROJECT_ROOT / "tests"


class TestDeadCodeStaysDeleted:
    def test_modules_are_gone(self):
        existing = [
            rel for rel in DELETED_MODULES if (PROJECT_ROOT / rel).exists()
        ]
        assert not existing, f"dead modules reintroduced: {existing}"

    def test_no_python_file_references_the_symbols(self):
        # This guard necessarily spells the symbols out, so it excludes itself.
        self_path = Path(__file__).resolve()

        offenders = []
        for path in list(SRC.rglob("*.py")) + list(TESTS.rglob("*.py")):
            if "__pycache__" in str(path) or path.resolve() == self_path:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for symbol in DELETED_SYMBOLS:
                if symbol in text:
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)} -> {symbol}")
        assert not offenders, "dead symbols still referenced:\n" + "\n".join(offenders)

    def test_providers_are_not_defined_in_dependencies(self):
        deps = PROJECT_ROOT / "src/news/entrypoints/api/dependencies.py"
        assert deps.exists()
        tree = ast.parse(deps.read_text(encoding="utf-8"))
        defined = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        still_there = sorted(set(DELETED_PROVIDERS) & defined)
        assert not still_there, f"unused providers still defined: {still_there}"