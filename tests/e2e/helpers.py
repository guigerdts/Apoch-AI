"""Helper utilities for E2E tests.

Environment detection, path resolution, and safe-skip helpers.
No imports from apoch.stack.* — helper layer is Stack-agnostic.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def find_binary(name: str) -> Path | None:
    """Locate *name* on ``$PATH``.

    Returns the absolute path to the binary, or ``None`` if not found.
    """
    found = shutil.which(name)
    return Path(found) if found else None


def is_ci() -> bool:
    """Return ``True`` when running inside a CI runner.

    Checks the ``CI`` environment variable (GitHub Actions, GitLab CI,
    Travis, Circle, Jenkins all set this).
    """
    return os.environ.get("CI", "").lower() in ("true", "1")


def requires_tool(name: str) -> str | None:
    """Return *name* if the tool is on ``$PATH``, or ``None`` to skip.

    Intended for use with ``pytest.param`` or conditional skip::

        openspec = pytest.param(
            "openspec",
            marks=pytest.mark.skipif(
                helpers.find_binary("openspec") is None,
                reason="openspec not found on PATH",
            ),
        )
    """
    return name if find_binary(name) is not None else None


@contextmanager
def sandbox_env(**env_vars: str) -> Iterator[None]:
    """Temporarily set environment variables for the duration of a test.

    Restores the original values (or removes them) on exit.
    Safe to nest.
    """
    old = {}
    for key, value in env_vars.items():
        old[key] = os.environ.get(key)
        os.environ[key] = value
    try:
        yield
    finally:
        for key in env_vars:
            if old[key] is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old[key]
