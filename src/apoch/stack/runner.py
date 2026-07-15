"""Subprocess abstraction for stack operations.

Design: Core Stack Installation & Lifecycle — CommandRunner
Components never execute subprocesses directly — all subprocess/spawn
calls go through ``CommandRunner`` for testability.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunResult:
    """Immutable result of a command execution.

    Attributes:
        returncode: Exit code of the process.
        stdout:     Captured standard output.
        stderr:     Captured standard error.
        duration:   Wall-clock duration in seconds.
    """

    returncode: int
    stdout: str = ""
    stderr: str = ""
    duration: float = 0.0

    @property
    def success(self) -> bool:
        """Return ``True`` if the command exited with code 0."""
        return self.returncode == 0


class CommandRunner(ABC):
    """Injectable subprocess runner — mockable in tests.

    Usage::

        class MyComponent:
            def __init__(self, runner: CommandRunner | None = None) -> None:
                self._runner = runner or RealRunner()
    """

    @abstractmethod
    async def run(
        self,
        cmd: list[str],
        *,
        timeout: float | None = None,
        env: dict[str, str] | None = None,
    ) -> RunResult:
        """Execute *cmd* and return the result.

        Args:
            cmd:     Command and arguments as a list of strings.
            timeout: Optional timeout in seconds.  If the command does
                     not complete within this time it is killed.
            env:     Optional environment variable overrides.

        Returns:
            A :class:`RunResult` with captured output.
        """
        ...


class RealRunner(CommandRunner):
    """Production subprocess runner using ``asyncio.create_subprocess_exec``."""

    async def run(
        self,
        cmd: list[str],
        *,
        timeout: float | None = None,
        env: dict[str, str] | None = None,
    ) -> RunResult:
        """Execute *cmd* via async subprocess.

        Captures stdout and stderr.  Uses *timeout* via ``asyncio.wait_for``
        if provided.
        """
        log.debug("Running command", extra={"cmd": cmd, "timeout": timeout})

        import time

        start = time.monotonic()

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            if timeout is not None:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            else:
                stdout_bytes, stderr_bytes = await proc.communicate()

            elapsed = time.monotonic() - start
            result = RunResult(
                returncode=proc.returncode or 0,
                stdout=stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else "",
                stderr=stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else "",
                duration=elapsed,
            )
        except TimeoutError:
            elapsed = time.monotonic() - start
            result = RunResult(
                returncode=-1,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                duration=elapsed,
            )
        except FileNotFoundError:
            elapsed = time.monotonic() - start
            result = RunResult(
                returncode=-1,
                stdout="",
                stderr=f"Command not found: {cmd[0] if cmd else '(empty)'}",
                duration=elapsed,
            )

        if not result.success:
            log.warning(
                "Command failed",
                extra={
                    "cmd": cmd,
                    "returncode": result.returncode,
                    "stderr": result.stderr[:200],
                    "duration": result.duration,
                },
            )

        return result


class MockRunner(CommandRunner):
    """Mock runner for tests — returns a configurable :class:`RunResult`.

    Usage::

        runner = MockRunner()
        runner.result = RunResult(returncode=0, stdout="hello")

        # Or pass a result at construction time:
        runner = MockRunner(result=RunResult(returncode=1, stderr="fail"))
    """

    def __init__(self, result: RunResult | None = None) -> None:
        """Initialise with an optional default result.

        Args:
            result: The :class:`RunResult` to return.  Defaults to
                    ``RunResult(returncode=0)``.
        """
        self.result = result or RunResult(returncode=0)

    async def run(
        self,
        cmd: list[str],
        *,
        timeout: float | None = None,
        env: dict[str, str] | None = None,
    ) -> RunResult:
        """Return the configured result immediately, ignoring *cmd*."""
        return self.result


__all__ = [
    "CommandRunner",
    "MockRunner",
    "RealRunner",
    "RunResult",
]
