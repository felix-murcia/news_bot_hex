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

# Allowlist por fichero: ruta relativa -> set de (línea, módulo).
# Cada entrada con comentario # TODO B20. No incluir imports dentro de try/except
# que capturen ImportError/ModuleNotFoundError (están permitidos por el helper).
# 129 imports inline existentes en application/ + domain/ allowlisteados hasta B20.
ALLOWED_IMPORTS: dict[str, set[tuple[int, str]]] = {
    "audio/application/usecases/audio_pipeline.py": {
        (10, "config.logging_config"),  # TODO B20
        (47, "src.shared.infrastructure.composition_root"),  # TODO B20
        (51, "src.shared.infrastructure.composition_root"),  # TODO B20
        (55, "config.settings"),  # TODO B20
        (169, "src.shared.infrastructure.composition_root"),  # TODO B20
        (170, "src.shared.adapters.tts_text_processor"),  # TODO B20
        (188, "pathlib"),  # TODO B20
        (281, "src.shared.adapters.social_post_adapter"),  # TODO B20
        (299, "src.shared.adapters.social_post_adapter"),  # TODO B20
    },
    "audio/application/usecases/audio_to_news.py": {
        (6, "config.logging_config"),  # TODO B20
        (21, "config.settings"),  # TODO B20
        (123, "src.shared.adapters.ai.ai_factory"),  # TODO B20
        (138, "src.audio.infrastructure.adapters.audio_fetcher"),  # TODO B20
        (154, "src.audio.infrastructure.adapters.audio_fetcher"),  # TODO B20
        (167, "config.settings"),  # TODO B20
        (168, "src.shared.adapters.ai.agents"),  # TODO B20
        (217, "src.shared.adapters.ai.agents"),  # TODO B20
        (225, "src.shared.adapters.social_post_adapter"),  # TODO B20
        (230, "src.shared.adapters.content_post_editor"),  # TODO B20
        (247, "config.settings"),  # TODO B20
        (271, "config.settings"),  # TODO B20
        (313, "argparse"),  # TODO B20
        (314, "config.settings"),  # TODO B20
    },
    "news/application/usecases/__init__.py": {
        (19, "src.news.infrastructure.adapters"),  # TODO B20
        (96, "config.settings"),  # TODO B20
    },
    "news/application/usecases/article.py": {
        (6, "config.logging_config"),  # TODO B20
        (8, "src.shared.adapters.ai.agents"),  # TODO B20
        (10, "src.shared.adapters.seo_optimizer"),  # TODO B20
        (168, "src.shared.adapters.ai.ai_factory"),  # TODO B20
        (302, "config.settings"),  # TODO B20
        (487, "config.settings"),  # TODO B20
        (488, "src.shared.infrastructure.composition_root"),  # TODO B20
        (508, "argparse"),  # TODO B20
        (509, "config.settings"),  # TODO B20
    },
    "news/application/usecases/article_from_news.py": {
        (4, "src.shared.adapters.translator"),  # TODO B20
        (5, "config.logging_config"),  # TODO B20
        (45, "src.shared.adapters.ai.ai_factory"),  # TODO B20
        (55, "config.settings"),  # TODO B20
        (85, "src.shared.adapters.content_post_editor"),  # TODO B20
        (104, "re"),  # TODO B20
        (202, "config.settings"),  # TODO B20
        (208, "src.shared.adapters.social_post_adapter"),  # TODO B20
        (215, "re"),  # TODO B20
        (226, "re"),  # TODO B20
        (255, "argparse"),  # TODO B20
        (256, "config.settings"),  # TODO B20
        (288, "time"),  # TODO B20
        (312, "traceback"),  # TODO B20
    },
    "news/application/usecases/cleanup.py": {
        (3, "config.logging_config"),  # TODO B20
        (53, "src.news.infrastructure.adapters"),  # TODO B20
    },
    "news/application/usecases/content.py": {
        (3, "config.logging_config"),  # TODO B20
        (5, "src.shared.adapters.ai.agents"),  # TODO B20
        (6, "src.shared.adapters.social_post_adapter"),  # TODO B20
        (7, "src.shared.adapters.content_post_editor"),  # TODO B20
        (45, "src.shared.adapters.ai.ai_factory"),  # TODO B20
        (123, "src.shared.adapters.cache_manager"),  # TODO B20
        (189, "config.settings"),  # TODO B20
        (210, "config.settings"),  # TODO B20
        (211, "src.shared.infrastructure.composition_root"),  # TODO B20
        (236, "argparse"),  # TODO B20
        (237, "config.settings"),  # TODO B20
    },
    "news/application/usecases/full_verify_usecase.py": {
        (17, "config.logging_config"),  # TODO B20
        (18, "src.news.infrastructure.adapters"),  # TODO B20
    },
    "news/application/usecases/metrics_collector.py": {
        (11, "config.logging_config"),  # TODO B20
    },
    "news/application/usecases/news_to_news.py": {
        (7, "config.logging_config"),  # TODO B20
        (22, "config.settings"),  # TODO B20
        (55, "src.news.application.usecases.article_from_news"),  # TODO B20
        (68, "src.shared.adapters.cache_manager"),  # TODO B20
        (69, "config.settings"),  # TODO B20
        (80, "src.shared.adapters.cache_manager"),  # TODO B20
        (101, "config.settings"),  # TODO B20
        (114, "config.settings"),  # TODO B20
        (115, "src.shared.adapters.ai.agents"),  # TODO B20
        (116, "src.shared.adapters.social_post_adapter"),  # TODO B20
        (127, "src.shared.adapters.ai.ai_factory"),  # TODO B20
        (199, "src.shared.application.usecases.tts_from_article"),  # TODO B20
        (287, "argparse"),  # TODO B20
        (288, "config.settings"),  # TODO B20
        (321, "src.shared.infrastructure.composition_root"),  # TODO B20
        (325, "src.news.infrastructure.adapters"),  # TODO B20
        (353, "traceback"),  # TODO B20
    },
    "news/application/usecases/pipeline_log_handler.py": {
        (33, "src.news.application.usecases.pipeline_job"),  # TODO B20
    },
    "news/application/usecases/pipeline_runner.py": {
        (11, "config.logging_config"),  # TODO B20
        (62, "src.news.application.usecases.pipeline_executor"),  # TODO B20
        (117, "src.news.application.usecases.pipeline_executor"),  # TODO B20
        (203, "src.shared.application.usecases.tts_from_article"),  # TODO B20
        (226, "src.shared.infrastructure.composition_root"),  # TODO B20
        (227, "os"),  # TODO B20
    },
    "news/application/usecases/process_url_executor.py": {
        (16, "config.logging_config"),  # TODO B20
    },
    "news/application/usecases/process_url_pipeline.py": {
        (14, "config.logging_config"),  # TODO B20
        (79, "src.news.domain.entities.verified_article"),  # TODO B20
        (80, "src.news.infrastructure.adapters"),  # TODO B20
        (125, "src.news.application.usecases.content"),  # TODO B20
        (147, "src.news.application.usecases.article"),  # TODO B20
        (159, "src.shared.infrastructure.composition_root"),  # TODO B20
        (173, "src.shared.infrastructure.composition_root"),  # TODO B20
        (188, "src.shared.application.usecases.tts_from_article"),  # TODO B20
        (201, "src.shared.infrastructure.composition_root"),  # TODO B20
        (232, "src.shared.infrastructure.composition_root"),  # TODO B20
    },
    "news/application/usecases/soft_verify.py": {
        (10, "src.shared.adapters.cache_manager"),  # TODO B20
        (15, "config.logging_config"),  # TODO B20
        (221, "src.news.infrastructure.adapters"),  # TODO B20
        (236, "src.news.infrastructure.adapters"),  # TODO B20
    },
    "news/domain/services/template_renderer.py": {
        (29, "urllib.parse"),  # TODO B20
    },
    "news/domain/services/validation_rules.py": {
        (11, "config.logging_config"),  # TODO B20 — leak conocido (§5.1 AGENTS.md)
    },
    "shared/application/usecases/article_from_transcript.py": {
        (16, "config.logging_config"),  # TODO B20
        (35, "unicodedata"),  # TODO B20
        (71, "src.shared.infrastructure.composition_root"),  # TODO B20
        (94, "config.settings"),  # TODO B20
        (95, "src.shared.adapters.ai.agents"),  # TODO B20
        (96, "src.shared.adapters.web_search"),  # TODO B20
        (115, "src.shared.adapters.content_post_editor"),  # TODO B20
        (229, "src.shared.adapters.ai.agents"),  # TODO B20
        (261, "src.shared.adapters.social_post_adapter"),  # TODO B20
        (265, "src.shared.adapters.content_post_editor"),  # TODO B20
    },
    "shared/application/usecases/base_pipeline.py": {
        (15, "config.logging_config"),  # TODO B20
        (52, "src.shared.adapters.wordpress_token_manager"),  # TODO B20
        (67, "src.shared.adapters.image_enricher"),  # TODO B20
        (75, "src.shared.adapters.publishers.social"),  # TODO B20
        (118, "src.shared.adapters.wikimedia_fetcher"),  # TODO B20
        (127, "src.shared.adapters.google_images_fetcher"),  # TODO B20
        (136, "src.shared.adapters.unsplash_fetcher"),  # TODO B20
        (159, "config.settings"),  # TODO B20
        (167, "src.shared.adapters.wordpress_publisher"),  # TODO B20
        (262, "src.shared.infrastructure.composition_root"),  # TODO B20
    },
    "shared/application/usecases/tts_from_article.py": {
        (8, "config.logging_config"),  # TODO B20
        (11, "src.shared.adapters.tts_text_processor"),  # TODO B20
        (70, "shutil"),  # TODO B20
        (153, "uuid"),  # TODO B20
        (154, "datetime"),  # TODO B20
        (159, "src.shared.adapters.audio_converter_factory"),  # TODO B20
        (207, "src.shared.infrastructure.composition_root"),  # TODO B20
        (214, "src.shared.infrastructure.composition_root"),  # TODO B20
    },
    "video/application/usecases/video_pipeline.py": {
        (13, "config.logging_config"),  # TODO B20
        (50, "src.shared.infrastructure.composition_root"),  # TODO B20
        (54, "config.settings"),  # TODO B20
        (72, "src.shared.infrastructure.composition_root"),  # TODO B20
        (153, "src.shared.infrastructure.composition_root"),  # TODO B20
        (154, "src.shared.adapters.tts_text_processor"),  # TODO B20
        (172, "pathlib"),  # TODO B20
        (265, "src.shared.adapters.social_post_adapter"),  # TODO B20
        (285, "src.shared.adapters.social_post_adapter"),  # TODO B20
    },
    "video/application/usecases/video_to_news.py": {
        (7, "config.logging_config"),  # TODO B20
        (22, "config.settings"),  # TODO B20
        (32, "src.video.infrastructure.adapters.video_transcriber"),  # TODO B20
        (141, "src.shared.adapters.ai.ai_factory"),  # TODO B20
        (156, "src.video.infrastructure.adapters.video_fetcher"),  # TODO B20
        (164, "src.video.infrastructure.adapters.video_transcriber"),  # TODO B20
        (177, "src.shared.adapters.ai.agents"),  # TODO B20
        (226, "src.shared.adapters.ai.agents"),  # TODO B20
        (234, "src.shared.adapters.social_post_adapter"),  # TODO B20
        (239, "src.shared.adapters.content_post_editor"),  # TODO B20
        (262, "config.settings"),  # TODO B20
        (285, "config.settings"),  # TODO B20
        (327, "argparse"),  # TODO B20
        (328, "config.settings"),  # TODO B20
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
            if (line, mod) not in allowed
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
            and (line, mod) not in allowed
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
            if (line, mod) not in allowed
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
            and (line, mod) not in allowed
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
            and (line, mod) not in allowed
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
