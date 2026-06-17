"""Architecture tests — verify hexagonal layer boundaries.

These tests enforce that:
1. Domain layer never imports from infrastructure or adapters
2. Application layer never imports Settings at module level
3. All key adapters implement their port ABCs
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
