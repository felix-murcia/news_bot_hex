"""Tests for fail-safe configuration loading.

Contract under test (T1): ``config.settings`` must be importable with NO
environment variables and NO ``.env`` file present. Every setting falls back to
a sensible default instead of raising ``KeyError`` from ``os.environ[...]``.

The test runs in a subprocess because ``config.settings`` executes
``Settings.ensure_directories()`` at import time and binds class attributes
once, so it cannot be re-imported cleanly inside the pytest process.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Settings that must resolve to a usable default when nothing is configured.
CRITICAL_DEFAULTS = [
    "BASE_DIR",
    "DATA_DIR",
    "CACHE_DIR",
    "MODELS_DIR",
    "IMAGES_DIR",
    "MONGO_DB_NAME",
    "AI_PROVIDER",
    "FFMPEG_API_URL",
]


def _run_import_without_env(cwd: str) -> subprocess.CompletedProcess:
    """Import config.settings in a clean interpreter with dotenv neutralized.

    ``dotenv.load_dotenv`` is patched to a no-op *before* importing
    ``config.settings`` because settings.py does ``from dotenv import
    load_dotenv`` and would otherwise pull the repository ``.env`` into the
    environment, masking the missing-configuration behaviour under test.
    """
    script = textwrap.dedent(
        f"""
        import os, sys
        sys.path.insert(0, {str(PROJECT_ROOT)!r})

        # Neutralize dotenv before config.settings imports it.
        import dotenv
        dotenv.load_dotenv = lambda *a, **k: False

        # Simulate a bare host: strip every variable, not just BASE_DIR.
        os.environ.clear()

        import config.settings as s

        out = {{}}
        for name in {CRITICAL_DEFAULTS!r}:
            out[name] = str(getattr(s.Settings, name))
        for k, v in sorted(out.items()):
            print(k, "=", v)
        print("IMPORT_OK")
        """
    )
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
    )


class TestSettingsFailSafe:
    def test_import_without_env_does_not_raise(self):
        """RED if any os.environ[...] remains: it raises KeyError."""
        result = _run_import_without_env(cwd="/tmp")
        assert "IMPORT_OK" in result.stdout, (
            "config.settings is not importable with an empty environment.\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )

    def test_critical_settings_have_non_empty_defaults(self):
        """Fail-safe means a *usable* default, not an empty string."""
        result = _run_import_without_env(cwd="/tmp")
        assert "IMPORT_OK" in result.stdout, result.stderr

        parsed = {}
        for line in result.stdout.splitlines():
            if " = " in line:
                key, _, value = line.partition(" = ")
                parsed[key] = value

        empty = [k for k in CRITICAL_DEFAULTS if not parsed.get(k, "").strip()]
        assert not empty, f"Settings resolved to empty values: {empty}"

    def test_base_dir_is_absolute_path(self):
        """BASE_DIR must stay usable for mkdir without configuration."""
        result = _run_import_without_env(cwd="/tmp")
        assert "IMPORT_OK" in result.stdout, result.stderr
        for line in result.stdout.splitlines():
            if line.startswith("BASE_DIR = "):
                assert line.split(" = ", 1)[1].startswith("/"), (
                    f"BASE_DIR must default to an absolute path, got: {line}"
                )
                break
        else:
            pytest.fail("BASE_DIR not reported")

    def test_repo_env_is_not_required_for_import(self):
        """Regression guard: the repo .env must not be a hard requirement."""
        # cwd is the repo, so find_dotenv() *can* locate .env — we still
        # neutralize it, proving the module does not depend on it.
        result = _run_import_without_env(cwd=str(PROJECT_ROOT))
        assert "IMPORT_OK" in result.stdout, result.stderr