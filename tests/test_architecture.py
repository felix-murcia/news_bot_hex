"""Architecture tests — verify hexagonal layer boundaries.

These tests enforce that:
1. Domain layer never imports from infrastructure or adapters
2. Application layer never imports Settings at module level
3. All key adapters implement their port ABCs
4. No inline imports (inside functions/classes) in domain/ or application/
5. No config.* imports in domain/ or application/
6. No infrastructure.adapters imports in application/
7. Inline imports inside try/except that catch ImportError are allowed (optional deps)

Allowed imports (top-level + inline) in application/ + domain/ are allowlisted in
ALLOWED_IMPORTS with # TODO B20 until B20 removes them.
Clave (fichero, módulo), robusta al desplazamiento de líneas.
"""

import ast
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent / "src"

DOMAIN_DIRS = [
    PROJECT_ROOT / "news" / "domain",
    PROJECT_ROOT / "audio" / "domain",
    PROJECT_ROOT / "video" / "domain",
    PROJECT_ROOT / "shared" / "domain",
]

APPLICATION_DIRS = [
    PROJECT_ROOT / "news" / "application",
    PROJECT_ROOT / "audio" / "application",
    PROJECT_ROOT / "video" / "application",
    PROJECT_ROOT / "shared" / "application",
]

INFRASTRUCTURE_PREFIXES = (
    "src.news.infrastructure",
    "src.audio.infrastructure",
    "src.video.infrastructure",
    "src.shared.adapters",
)

# Allowlist por fichero: ruta relativa -> set de módulo (sin línea).
# Cada entrada con comentario # TODO B20. No incluir imports dentro de try/except
# que capturen ImportError/ModuleNotFoundError (están permitidos por el helper).
# Imports inline existentes en application/ + domain/ allowlisteados hasta B20.
ALLOWED_IMPORTS: dict[str, set[str]] = {
    "audio/application/usecases/audio_pipeline.py": {
        "src.shared.adapters.tts_text_processor",  # TODO B20
        "pathlib",  # TODO B20
        "src.shared.adapters.social_post_adapter",  # TODO B20
    },
    "audio/application/usecases/audio_to_news.py": {
        "config.settings",  # TODO B20
        "src.shared.adapters.ai.ai_factory",  # TODO B20
        "src.shared.adapters.ai.agents",  # TODO B20
        "src.shared.adapters.social_post_adapter",  # TODO B20
        "src.shared.adapters.content_post_editor",  # TODO B20
        "argparse",  # TODO B20
    },
    "news/application/usecases/__init__.py": set(),
    "news/application/usecases/article.py": {
        "src.shared.adapters.ai.agents",  # TODO B20
        "src.shared.adapters.seo_optimizer",  # TODO B20
        "src.shared.adapters.ai.ai_factory",  # TODO B20
        "config.settings",  # TODO B11c (argparse)
        "src.shared.infrastructure.composition_root",  # TODO B11c (main/argparse)
        "argparse",  # TODO B20
    },
    "news/application/usecases/article_from_news.py": {
        "src.shared.adapters.translator",  # TODO B20
        "src.shared.adapters.ai.ai_factory",  # TODO B20
        "config.settings",  # TODO B11c (argparse)
        "src.shared.adapters.content_post_editor",  # TODO B20
        "re",  # TODO B20
        "src.shared.adapters.social_post_adapter",  # TODO B20
        "argparse",  # TODO B20
        "time",  # TODO B20
        "traceback",  # TODO B20
    },
    "news/application/usecases/cleanup.py": {
        "src.news.infrastructure.adapters",  # TODO B20
    },
    "news/application/usecases/content.py": {
        "src.shared.adapters.ai.agents",  # TODO B20
        "src.shared.adapters.social_post_adapter",  # TODO B20
        "src.shared.adapters.content_post_editor",  # TODO B20
        "src.shared.adapters.ai.ai_factory",  # TODO B20
        "src.shared.adapters.cache_manager",  # TODO B20
        "config.settings",  # TODO B11c (argparse)
        "src.shared.infrastructure.composition_root",  # TODO B11c (main/argparse)
        "argparse",  # TODO B20
    },
    "news/application/usecases/full_verify_usecase.py": set(),
    "news/application/usecases/news_to_news.py": {
        "src.news.application.usecases.article_from_news",  # TODO B20
        "src.shared.adapters.cache_manager",  # TODO B20
        "src.shared.adapters.ai.agents",  # TODO B20
        "src.shared.adapters.social_post_adapter",  # TODO B20
        "src.shared.adapters.ai.ai_factory",  # TODO B20
        "src.shared.application.usecases.tts_from_article",  # TODO B20
        "argparse",  # TODO B20
        "src.shared.infrastructure.composition_root",  # TODO B20
        "src.news.infrastructure.adapters",  # TODO B20
        "traceback",  # TODO B20
    },
    "news/application/usecases/pipeline_log_handler.py": {
        "src.news.application.usecases.pipeline_job",  # TODO B20
    },
    "news/application/usecases/pipeline_runner.py": {
        "src.news.application.usecases.pipeline_executor",  # TODO B20
        "os",  # TODO B20
    },
    "news/application/usecases/process_url_pipeline.py": {
        "src.news.domain.entities.verified_article",  # TODO B20
        "src.news.application.usecases.content",  # TODO B20
        "src.news.application.usecases.article",  # TODO B20
    },
    "news/application/usecases/soft_verify.py": {
        "src.shared.adapters.cache_manager",  # TODO B20
        "src.news.infrastructure.adapters",  # TODO B11c (main/argparse repos)
    },
    "news/domain/services/template_renderer.py": {
        "urllib.parse",  # TODO B20
    },
    "shared/application/usecases/article_from_transcript.py": {
        "unicodedata",  # TODO B20
        "src.shared.adapters.ai.agents",  # TODO B20
        "src.shared.adapters.web_search",  # TODO B20
        "src.shared.adapters.content_post_editor",  # TODO B20
        "src.shared.adapters.social_post_adapter",  # TODO B20
    },
    "shared/application/usecases/base_pipeline.py": {
        "src.shared.adapters.wordpress_token_manager",  # TODO B20
        "src.shared.adapters.image_enricher",  # TODO B20
        "src.shared.adapters.publishers.social",  # TODO B20
        "src.shared.adapters.wikimedia_fetcher",  # TODO B20
        "src.shared.adapters.google_images_fetcher",  # TODO B20
        "src.shared.adapters.unsplash_fetcher",  # TODO B20
        "src.shared.adapters.wordpress_publisher",  # TODO B20
    },
    "shared/application/usecases/tts_from_article.py": {
        "src.shared.adapters.tts_text_processor",  # TODO B20
        "shutil",  # TODO B20
        "uuid",  # TODO B20
        "datetime",  # TODO B20
        "src.shared.adapters.audio_converter_factory",  # TODO B20
    },
    "video/application/usecases/video_pipeline.py": {
        "src.shared.adapters.tts_text_processor",  # TODO B20
        "pathlib",  # TODO B20
        "src.shared.adapters.social_post_adapter",  # TODO B20
    },
    "video/application/usecases/video_to_news.py": {
        "config.settings",  # TODO B20
        "src.shared.adapters.ai.ai_factory",  # TODO B20
        "src.shared.adapters.ai.agents",  # TODO B20
        "src.shared.adapters.social_post_adapter",  # TODO B20
        "src.shared.adapters.content_post_editor",  # TODO B20
        "argparse",  # TODO B20
    },
}



def _collect_python_files(dirs):
    files = []
    for d in dirs:
        if d.exists():
            for f in d.rglob("*.py"):
                if "__pycache__" not in str(f):
                    files.append(f)
    return files


def _get_top_level_imports(filepath):
    """Extract top-level import module names from a Python file."""
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=str(filepath))
        except SyntaxError:
            return []

    imports = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.module, node.lineno))
    return imports


def _get_all_imports(tree: ast.Module) -> list[tuple[int, str]]:
    """Todos los imports (módulo + inline) como (línea, módulo)."""
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
    return imports


def _get_inline_imports(tree: ast.Module) -> list[tuple[int, str]]:
    """Imports inline = todos menos los de nivel de módulo.

    Reutiliza _get_top_level_imports para la comparación de nivel de módulo.
    """
    all_imports = set(_get_all_imports(tree))
    top_level = set(_get_top_level_imports_from_tree(tree))
    return sorted(all_imports - top_level)


def _get_top_level_imports_from_tree(tree: ast.Module) -> list[tuple[int, str]]:
    """Imports a nivel de módulo directamente desde un árbol AST."""
    imports = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
    return imports


def _captures_import_error(handler: ast.ExceptHandler) -> bool:
    """True si el handler captura ImportError o ModuleNotFoundError (o todo)."""
    if handler.type is None:
        return True
    if isinstance(handler.type, ast.Name):
        return handler.type.id in ("ImportError", "ModuleNotFoundError")
    if isinstance(handler.type, ast.Tuple):
        return any(
            isinstance(e, ast.Name) and e.id in ("ImportError", "ModuleNotFoundError")
            for e in handler.type.elts
        )
    return False


def _import_inside_optional_try(tree: ast.Module, target_line: int) -> bool:
    """True si el import en target_line está dentro de un ast.Try cuyo
    handler captura ImportError/ModuleNotFoundError."""

    def _walk(node: ast.AST, inside_optional_try: bool) -> bool:
        if isinstance(node, (ast.Import, ast.ImportFrom)) and node.lineno == target_line:
            return inside_optional_try
        if isinstance(node, ast.Try):
            is_optional = any(_captures_import_error(h) for h in node.handlers)
            for child in ast.iter_child_nodes(node):
                if _walk(child, inside_optional_try or is_optional):
                    return True
            return False
        for child in ast.iter_child_nodes(node):
            if _walk(child, inside_optional_try):
                return True
        return False

    return _walk(tree, False)


def _relative_path(filepath: Path) -> str:
    """Ruta relativa del fichero respecto a PROJECT_ROOT."""
    return str(filepath.relative_to(PROJECT_ROOT))


class TestDomainLayerBoundary:
    """Domain must never import from infrastructure or adapters."""

    @pytest.mark.parametrize("filepath", _collect_python_files(DOMAIN_DIRS),
                             ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
    def test_no_infrastructure_imports(self, filepath):
        imports = _get_top_level_imports(filepath)
        violations = [
            (mod, line) for mod, line in imports
            if any(mod.startswith(prefix) for prefix in INFRASTRUCTURE_PREFIXES)
        ]
        assert violations == [], (
            f"{filepath.relative_to(PROJECT_ROOT)}: domain imports infrastructure: "
            + ", ".join(f"{mod} (line {line})" for mod, line in violations)
        )

    @pytest.mark.parametrize("filepath", _collect_python_files(DOMAIN_DIRS),
                             ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
    def test_no_settings_import(self, filepath):
        imports = _get_top_level_imports(filepath)
        violations = [
            (mod, line) for mod, line in imports
            if mod == "config.settings"
        ]
        assert violations == [], (
            f"{filepath.relative_to(PROJECT_ROOT)}: domain imports Settings"
        )

    @pytest.mark.parametrize("filepath", _collect_python_files(DOMAIN_DIRS),
                             ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
    def test_no_inline_imports_in_domain(self, filepath):
        """No imports inline (dentro de funciones/clases) en domain/."""
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=str(filepath))
            except SyntaxError:
                pytest.skip(f"Syntax error in {filepath}")
        inline = _get_inline_imports(tree)
        rel = _relative_path(filepath)
        allowed = ALLOWED_IMPORTS.get(rel, set())
        violations = [
            (line, mod) for line, mod in inline
            if mod not in allowed
            and not _import_inside_optional_try(tree, line)
        ]
        assert violations == [], (
            f"{rel}: domain tiene imports inline no allowlisteados: "
            + ", ".join(f"{mod} (line {line})" for line, mod in violations)
        )

    @pytest.mark.parametrize("filepath", _collect_python_files(DOMAIN_DIRS),
                             ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
    def test_no_config_imports_in_domain(self, filepath):
        """Ningún import de config.* en domain/ (top-level o inline)."""
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=str(filepath))
            except SyntaxError:
                pytest.skip(f"Syntax error in {filepath}")
        all_imports = _get_all_imports(tree)
        rel = _relative_path(filepath)
        allowed = ALLOWED_IMPORTS.get(rel, set())
        violations = [
            (line, mod) for line, mod in all_imports
            if mod.startswith("config.")
            and mod not in allowed
            and not _import_inside_optional_try(tree, line)
        ]
        assert violations == [], (
            f"{rel}: domain importa config.*: "
            + ", ".join(f"{mod} (line {line})" for line, mod in violations)
        )


class TestApplicationLayerBoundary:
    """Application layer must not import Settings at module level."""

    @pytest.mark.parametrize("filepath", _collect_python_files(APPLICATION_DIRS),
                             ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
    def test_no_top_level_settings(self, filepath):
        imports = _get_top_level_imports(filepath)
        violations = [
            (mod, line) for mod, line in imports
            if mod == "config.settings"
        ]
        assert violations == [], (
            f"{filepath.relative_to(PROJECT_ROOT)}: top-level Settings import at "
            + ", ".join(f"line {line}" for _, line in violations)
        )

    @pytest.mark.parametrize("filepath", _collect_python_files(APPLICATION_DIRS),
                             ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
    def test_no_inline_imports_in_application(self, filepath):
        """No imports inline (dentro de funciones/clases) en application/."""
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=str(filepath))
            except SyntaxError:
                pytest.skip(f"Syntax error in {filepath}")
        inline = _get_inline_imports(tree)
        rel = _relative_path(filepath)
        allowed = ALLOWED_IMPORTS.get(rel, set())
        violations = [
            (line, mod) for line, mod in inline
            if mod not in allowed
            and not _import_inside_optional_try(tree, line)
        ]
        assert violations == [], (
            f"{rel}: application tiene imports inline no allowlisteados: "
            + ", ".join(f"{mod} (line {line})" for line, mod in violations)
        )

    @pytest.mark.parametrize("filepath", _collect_python_files(APPLICATION_DIRS),
                             ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
    def test_no_config_imports_in_application(self, filepath):
        """Ningún import de config.* en application/ (top-level o inline)."""
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=str(filepath))
            except SyntaxError:
                pytest.skip(f"Syntax error in {filepath}")
        all_imports = _get_all_imports(tree)
        rel = _relative_path(filepath)
        allowed = ALLOWED_IMPORTS.get(rel, set())
        violations = [
            (line, mod) for line, mod in all_imports
            if mod.startswith("config.")
            and mod not in allowed
            and not _import_inside_optional_try(tree, line)
        ]
        assert violations == [], (
            f"{rel}: application importa config.*: "
            + ", ".join(f"{mod} (line {line})" for line, mod in violations)
        )

    @pytest.mark.parametrize("filepath", _collect_python_files(APPLICATION_DIRS),
                             ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
    def test_no_infrastructure_imports_in_application(self, filepath):
        """Ningún import de infrastructure.adapters en application/ (ni top-level ni inline)."""
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=str(filepath))
            except SyntaxError:
                pytest.skip(f"Syntax error in {filepath}")
        all_imports = _get_all_imports(tree)
        rel = _relative_path(filepath)
        allowed = ALLOWED_IMPORTS.get(rel, set())
        violations = [
            (line, mod) for line, mod in all_imports
            if (".infrastructure.adapters" in mod or ".adapters" in mod)
            and "composition_root" not in mod
            and mod not in allowed
            and not _import_inside_optional_try(tree, line)
        ]
        assert violations == [], (
            f"{rel}: application importa infrastructure.adapters: "
            + ", ".join(f"{mod} (line {line})" for line, mod in violations)
        )


class TestAdapterPortCompliance:
    """Key adapters must inherit from their port ABC."""

    ADAPTER_PORT_PAIRS = [
        ("src/shared/adapters/audio_converter.py", "AudioConverterPort"),
        ("src/shared/adapters/audio_post_processor.py", "AudioPostProcessorPort"),
        ("src/audio/infrastructure/adapters/audio_fetcher.py", "AudioFetcherPort"),
        ("src/audio/infrastructure/adapters/audio_transcriber.py", "AudioTranscriberPort"),
        ("src/video/infrastructure/adapters/video_fetcher.py", "VideoFetcherPort"),
        ("src/video/infrastructure/adapters/video_transcriber.py", "VideoTranscriberPort"),
        ("src/shared/adapters/ai/gemini_adapter.py", "AIModelPort"),
        ("src/shared/adapters/ai/groq_adapter.py", "AIModelPort"),
        ("src/shared/adapters/ai/openrouter_adapter.py", "AIModelPort"),
        ("src/shared/adapters/ai/local_adapter.py", "AIModelPort"),
    ]

    @pytest.mark.parametrize("adapter_path,port_name", ADAPTER_PORT_PAIRS,
                             ids=lambda p: p if isinstance(p, str) else "")
    def test_adapter_implements_port(self, adapter_path, port_name):
        full_path = PROJECT_ROOT.parent / adapter_path
        assert full_path.exists(), f"Adapter file not found: {adapter_path}"
        content = full_path.read_text(encoding="utf-8")
        assert port_name in content, (
            f"{adapter_path} does not reference {port_name}"
        )
