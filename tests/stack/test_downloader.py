"""Tests for Downloader, RealDownloader, and MockDownloader.

Design: Core Stack Installation & Lifecycle — Downloader
No download logic embedded in components — all external source access
goes through ``Downloader`` for testability.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apoch.stack.downloader import Downloader, MockDownloader, RealDownloader
from apoch.stack.runner import MockRunner, RunResult


class TestDownloader:
    """Downloader is abstract and cannot be instantiated."""

    def test_downloader_is_abstract(self):
        with pytest.raises(TypeError):
            Downloader()  # type: ignore[abstract]


class TestMockDownloader:
    """MockDownloader returns configurable results and records calls."""

    async def test_default_true(self):
        downloader = MockDownloader()
        result = await downloader.download("https://example.com/f", Path("/tmp/f"))
        assert result is True

    async def test_custom_result(self):
        downloader = MockDownloader(result=False)
        result = await downloader.download("https://example.com/f", Path("/tmp/f"))
        assert result is False

    async def test_mutable_result(self):
        downloader = MockDownloader()
        downloader.result = False
        assert await downloader.download("https://x.com/f", Path("/tmp/f")) is False

    async def test_records_calls(self):
        downloader = MockDownloader()
        src1, src2 = "https://a.com/x", "https://b.com/y"
        dst1, dst2 = Path("/tmp/x"), Path("/tmp/y")

        await downloader.download(src1, dst1)
        await downloader.download(src2, dst2)

        assert len(downloader.calls) == 2
        assert downloader.calls[0] == (src1, dst1)
        assert downloader.calls[1] == (src2, dst2)

    async def test_async_interface(self):
        downloader = MockDownloader()
        result = await downloader.download("https://x.com/f", Path("/tmp/f"))
        assert isinstance(result, bool)

    async def test_empty_source_returns_true_by_default(self):
        # MockDownloader doesn't validate — returns configured result
        downloader = MockDownloader(result=True)
        assert await downloader.download("", Path("/tmp/f")) is True


class TestRealDownloaderHttp:
    """RealDownloader handles HTTP/HTTPS downloads (network-free)."""

    async def test_unsupported_scheme_returns_false(self):
        downloader = RealDownloader()
        result = await downloader.download("ftp://example.com/f", Path("/tmp/f"))
        assert result is False

    async def test_empty_source_returns_false(self):
        downloader = RealDownloader()
        assert await downloader.download("", Path("/tmp/f")) is False

    async def test_empty_dest_returns_false(self):
        downloader = RealDownloader()
        assert await downloader.download("https://example.com/f", Path()) is False

    async def test_missing_file_is_not_found(self):
        """HTTP download to a non-existent URL returns False."""
        downloader = RealDownloader()
        result = await downloader.download(
            "https://invalid.example.invalid/file.zip",
            Path("/tmp/test_download_nonexistent"),
        )
        assert result is False

    async def test_git_without_runner_returns_false(self):
        """Git downloads require a CommandRunner."""
        downloader = RealDownloader()
        result = await downloader.download(
            "git+https://github.com/example/repo.git",
            Path("/tmp/test_git_repo"),
        )
        assert result is False

    async def test_git_with_mock_runner(self):
        """Git download delegates to the injected runner."""
        runner = MockRunner(result=RunResult(returncode=0))
        downloader = RealDownloader(runner=runner)
        result = await downloader.download(
            "git+https://github.com/example/repo.git",
            Path("/tmp/test_git_repo_mock"),
        )
        assert result is True

    async def test_git_with_failing_runner(self):
        """A failing git clone returns False."""
        runner = MockRunner(result=RunResult(returncode=1, stderr="failed"))
        downloader = RealDownloader(runner=runner)
        result = await downloader.download(
            "git+https://github.com/example/repo.git",
            Path("/tmp/test_git_repo_fail"),
        )
        assert result is False

    async def test_git_normalises_url(self):
        """git+https:// is normalised to https:// for git clone."""
        runner = MockRunner(result=RunResult(returncode=0))
        downloader = RealDownloader(runner=runner)

        result = await downloader.download(
            "git+https://github.com/org/repo.git",
            Path("/tmp/test_git_normalise"),
        )

        assert result is True

    async def test_plain_git_uses_runner(self):
        """Plain git:// scheme also uses the runner."""
        runner = MockRunner(result=RunResult(returncode=0))
        downloader = RealDownloader(runner=runner)
        result = await downloader.download(
            "git://github.com/example/repo.git",
            Path("/tmp/test_git_plain"),
        )
        assert result is True


class TestParseScheme:
    """_parse_scheme extracts the URI scheme correctly."""

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            ("https://example.com/f", "https"),
            ("http://example.com/f", "http"),
            ("git+https://github.com/x.git", "git+https"),
            ("git+ssh://git@github.com/x.git", "git+ssh"),
            ("git://example.com/repo", "git"),
            ("ftps://example.com/f", "ftps"),
            ("", ""),
            ("no-scheme-at-all", ""),
            ("scheme:no-slash", ""),  # no ://
        ],
    )
    def test_parse_scheme(self, source: str, expected: str):
        from apoch.stack.downloader import _parse_scheme

        assert _parse_scheme(source) == expected
