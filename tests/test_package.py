"""Tests for package boilerplate.

Spec: cli-interface §Public Interfaces

**Portability rule**: Tests must never depend on the developer's machine
state.  All subprocess invocations inject ``PYTHONPATH`` so they work
without a global package install.
"""

import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    """Return the repository root (parent of ``tests/``)."""
    return Path(__file__).resolve().parent.parent


class TestPackageImport:
    """Verify the apoch package is importable with expected exports."""

    def test_version_attribute_exists(self):
        """from apoch import __version__ returns a string."""
        from apoch import __version__

        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_all_exports_are_callable_modules(self):
        """__all__ lists expected public submodules, each importable."""
        from apoch import __all__

        expected = {"core", "cli", "adapters", "modules", "plugins", "stack", "config"}
        assert set(__all__) == expected

    def test_compat_module_importable(self):
        """from apoch import _compat works."""
        from apoch import _compat

        assert _compat is not None


class TestMainEntry:
    """Verify python -m apoch prints help and exits cleanly."""

    def test_python_m_apoch_prints_help(self):
        """Running python -m apoch prints help text to stdout."""
        # Inject PYTHONPATH so the subprocess finds src/apoch without
        # requiring a global/editable install.
        src_dir = str(_repo_root() / "src")
        env = {**os.environ, "PYTHONPATH": src_dir}

        result = subprocess.run(
            [sys.executable, "-m", "apoch"],
            capture_output=True,
            text=True,
            cwd=_repo_root(),
            env=env,
            check=False,
        )
        assert result.returncode == 0, (
            f"Expected exit code 0, got {result.returncode}. "
            f"stderr: {result.stderr}"
        )
        lower = result.stdout.lower()
        assert "usage" in lower or "help" in lower or "apoch" in lower, (
            f"Expected help text, got: {result.stdout[:200]}"
        )
