"""Download abstraction for external sources (HTTP, Git, PyPI).

Design: Core Stack Installation & Lifecycle — Downloader
No download logic embedded in components — all external source access
goes through ``Downloader`` for testability.
"""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class Downloader(ABC):
    """Injectable downloader — mockable in tests.

    Usage::

        class MyComponent:
            def __init__(self, downloader: Downloader | None = None) -> None:
                self._downloader = downloader or RealDownloader()
    """

    @abstractmethod
    async def download(self, source: str, dest: Path) -> bool:
        """Download *source* to *dest*.

        Args:
            source: URI of the resource to download
                    (e.g. ``https://example.com/file.zip``).
            dest:   Local filesystem path where the resource is saved.

        Returns:
            ``True`` if the download succeeded, ``False`` otherwise.
        """
        ...


class RealDownloader(Downloader):
    """Production downloader that handles various source types.

    Supported schemes:

    - ``https://`` / ``http://``:  HTTP download via :mod:`urllib.request`.
    - ``git+https://`` / ``git+ssh://``:  Delegated to ``git clone`` via
      a :class:`~apoch.stack.runner.CommandRunner` (injected or default).

    Unsupported schemes return ``False`` without raising.
    """

    def __init__(self, runner: Any | None = None) -> None:
        """Initialise with an optional :class:`~apoch.stack.runner.CommandRunner`.

        Args:
            runner: A ``CommandRunner`` instance for subprocess operations.
                    Defaults to ``None`` (subprocess operations disabled).
        """
        self._runner = runner

    async def download(self, source: str, dest: Path) -> bool:
        """Download *source* to *dest*.

        Returns ``False`` (rather than raising) for unsupported schemes
        or transient errors so that callers can degrade gracefully.
        """
        if not source or not dest:
            log.warning("Download called with empty source or dest")
            return False

        scheme = _parse_scheme(source)

        if scheme in ("http", "https"):
            return await self._download_http(source, dest)

        if scheme in ("git+https", "git+ssh", "git"):
            return await self._download_git(source, dest)

        log.warning("Unsupported download scheme", extra={"scheme": scheme, "source": source})
        return False

    async def _download_http(self, url: str, dest: Path) -> bool:
        """Download a file over HTTP/HTTPS using :mod:`urllib.request`."""
        import asyncio

        dest.parent.mkdir(parents=True, exist_ok=True)

        def _blocking_get() -> bool:
            try:
                urllib.request.urlretrieve(url, str(dest))
                return True
            except urllib.error.URLError as exc:
                log.error("HTTP download failed", extra={"url": url, "error": str(exc)})
                return False
            except OSError as exc:
                log.error("Download write error", extra={"dest": str(dest), "error": str(exc)})
                return False

        return await asyncio.get_running_loop().run_in_executor(None, _blocking_get)

    async def _download_git(self, source: str, dest: Path) -> bool:
        """Clone a git repository to *dest*."""
        if self._runner is None:
            log.warning("Git download requires a CommandRunner — none configured")
            return False

        # Normalise git+https → https for git clone
        clone_url = source
        if source.startswith("git+https://"):
            clone_url = source[4:]  # strip "git+"
        elif source.startswith("git+ssh://"):
            clone_url = source[4:]  # strip "git+"

        dest.parent.mkdir(parents=True, exist_ok=True)
        result = await self._runner.run(["git", "clone", clone_url, str(dest)])
        return result.success


class MockDownloader(Downloader):
    """Mock downloader for tests — returns a configurable result.

    Records every call for later assertion.

    Usage::

        downloader = MockDownloader()
        downloader.result = True  # downloads will "succeed"
        ok = await downloader.download("https://example.com/file", Path("/tmp/f"))
        assert downloader.calls[0] == ("https://example.com/file", Path("/tmp/f"))
    """

    def __init__(self, result: bool = True) -> None:
        """Initialise with an optional default result.

        Args:
            result: The value ``download()`` returns.  Defaults to ``True``.
        """
        self.result: bool = result
        self.calls: list[tuple[str, Path]] = []

    async def download(self, source: str, dest: Path) -> bool:
        """Record the call and return the configured result."""
        self.calls.append((source, dest))
        return self.result


def _parse_scheme(source: str) -> str:
    """Extract the scheme from a source URI.

    Handles ``scheme://`` and ``scheme+subscheme://`` formats.
    """
    if "://" not in source:
        return ""
    scheme_part = source.split("://", 1)[0]
    return scheme_part.lower()


__all__ = [
    "Downloader",
    "MockDownloader",
    "RealDownloader",
]
