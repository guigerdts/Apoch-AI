"""Shared fixtures for E2E tests.

Every fixture here is ``tmp_path``-isolated — no test writes to global
user directories.  Zero imports from ``apoch.stack.components.*``;
no real tool calls happen in fixtures.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def apoch_root() -> Path:
    """Return the absolute path to the repository root.

    Calculated from the test file location: ``tests/e2e/`` → repo root.
    """
    return Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def sandbox_path(tmp_path: Path) -> Path:
    """Return a temporary ``bin/`` directory for command resolution tests.

    The directory is created automatically and cleaned up by pytest.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    return bin_dir


@pytest.fixture
def isolated_env(sandbox_path: Path) -> Iterator[dict[str, str]]:
    """Provide a ``$PATH`` that points only to *sandbox_path/bin*.

    Useful for tests that need to verify behaviour when a tool is
    absent (the sandbox bin/ is empty).

    Yields the modified environment dictionary.
    """
    old_path = os.environ.get("PATH", "")
    new_path = str(sandbox_path)
    os.environ["PATH"] = new_path
    try:
        yield {"PATH": new_path}
    finally:
        os.environ["PATH"] = old_path


@pytest.fixture
def ci_override() -> Iterator[None]:
    """Temporarily set ``CI=true`` for tests that need CI-like detection.

    Restores the original value on exit.
    """
    old_ci = os.environ.get("CI")
    os.environ["CI"] = "true"
    try:
        yield
    finally:
        if old_ci is None:
            os.environ.pop("CI", None)
        else:
            os.environ["CI"] = old_ci


@pytest.fixture
def e2e_config() -> dict[str, Any]:
    """Return a configuration dict safe for any E2E test.

    No real tool paths — just defaults that point to sandbox locations.
    """
    return {
        "e2e": {
            "sandbox": True,
            "skip_on_missing": True,
        },
    }


@pytest.fixture
def skip_if_no_openspec() -> bool:
    """Return ``True`` if OpenSpec is available, skip otherwise."""
    openspec = _find_tool("openspec")
    if openspec is None:
        pytest.skip("openspec not found on PATH — skipping E2E")
    return True


@pytest.fixture
def skip_if_no_codegraph() -> bool:
    """Return ``True`` if CodeGraph is available, skip otherwise."""
    cg = _find_tool("codegraph")
    if cg is None:
        pytest.skip("codegraph not found on PATH — skipping E2E")
    return True


@pytest.fixture
def skip_if_no_engram() -> bool:
    """Return ``True`` if Engram is available, skip otherwise."""
    engram = _find_tool("engram")
    if engram is None:
        pytest.skip("engram not found on PATH — skipping E2E")
    return True


@pytest.fixture
def skip_if_no_context7() -> bool:
    """Return ``True`` if Context7 is available, skip otherwise."""
    ctx7 = _find_tool("ctx7")
    if ctx7 is None:
        pytest.skip("context7 not found on PATH — skipping E2E")
    return True


def _find_tool(name: str) -> str | None:
    """Thin wrapper around ``shutil.which`` for fixture use."""
    import shutil
    return shutil.which(name)
