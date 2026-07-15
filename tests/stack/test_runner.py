"""Tests for CommandRunner, RealRunner, MockRunner, and RunResult.

Design: Core Stack Installation & Lifecycle — CommandRunner
Components never execute subprocesses directly — all subprocess/spawn
calls go through ``CommandRunner`` for testability.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from apoch.stack.runner import CommandRunner, MockRunner, RealRunner, RunResult


class TestRunResult:
    """RunResult is a frozen dataclass with a success helper."""

    def test_success_on_zero(self):
        assert RunResult(returncode=0).success is True

    def test_failure_on_nonzero(self):
        assert RunResult(returncode=1).success is False

    def test_frozen(self):
        r = RunResult(returncode=0, stdout="a")
        with pytest.raises(AttributeError):
            r.returncode = 1  # type: ignore[misc]

    def test_defaults(self):
        r = RunResult(returncode=0)
        assert r.stdout == ""
        assert r.stderr == ""
        assert r.duration == 0.0

    def test_can_use_replace_for_variants(self):
        base = RunResult(returncode=0, stdout="ok")
        altered = replace(base, returncode=1, stderr="fail")
        assert altered.returncode == 1
        assert altered.stderr == "fail"
        assert altered.stdout == "ok"


class TestCommandRunner:
    """CommandRunner is abstract and cannot be instantiated."""

    def test_command_runner_is_abstract(self):
        with pytest.raises(TypeError):
            CommandRunner()  # type: ignore[abstract]


class TestMockRunner:
    """MockRunner returns a configurable RunResult for tests."""

    async def test_default_result(self):
        runner = MockRunner()
        result = await runner.run(["echo", "hi"])
        assert result.returncode == 0
        assert result.stdout == ""

    async def test_custom_result(self):
        desired = RunResult(returncode=42, stdout="custom", stderr="err")
        runner = MockRunner(result=desired)
        result = await runner.run(["any", "cmd"])
        assert result == desired

    async def test_mutable_result(self):
        runner = MockRunner()
        runner.result = RunResult(returncode=1, stderr="simulated failure")
        result = await runner.run(["fail"])
        assert result.returncode == 1
        assert result.stderr == "simulated failure"

    async def test_ignores_command_args(self):
        """MockRunner returns the configured result regardless of cmd."""
        runner = MockRunner(result=RunResult(returncode=0, stdout="fixed"))
        r1 = await runner.run(["echo", "hello"])
        r2 = await runner.run(["git", "status"])
        assert r1 == r2

    async def test_async_interface(self):
        """MockRunner.run is awaitable."""
        runner = MockRunner()
        result = await runner.run(["ls"])
        assert isinstance(result, RunResult)


class TestRealRunner:
    """RealRunner executes actual subprocesses."""

    @pytest.mark.parametrize(
        ("cmd", "expected_out"),
        [
            (["echo", "hello"], "hello"),
            (["printf", "world\n"], "world\n"),
        ],
    )
    async def test_echo_commands(self, cmd: list[str], expected_out: str):
        runner = RealRunner()
        result = await runner.run(cmd)
        assert result.success
        assert expected_out in result.stdout

    async def test_nonzero_exit(self):
        """A failing command returns a non-zero result (not an exception)."""
        runner = RealRunner()
        result = await runner.run(["bash", "-c", "exit 42"])
        assert result.returncode == 42
        assert result.success is False

    async def test_stderr_captured(self):
        runner = RealRunner()
        result = await runner.run(["bash", "-c", "echo err >&2"])
        assert result.success
        assert "err" in result.stderr

    async def test_timeout_kills_command(self):
        """A command that exceeds the timeout returns returncode -1."""
        runner = RealRunner()
        result = await runner.run(["sleep", "10"], timeout=0.1)
        assert result.returncode == -1
        assert "timed out" in result.stderr

    async def test_file_not_found(self):
        runner = RealRunner()
        result = await runner.run(["nonexistent_command_xyz123"])
        assert result.returncode == -1
        assert "not found" in result.stderr

    async def test_duration_is_recorded(self):
        runner = RealRunner()
        result = await runner.run(["echo", "fast"])
        assert result.duration > 0.0

    async def test_env_override(self):
        runner = RealRunner()
        result = await runner.run(
            ["bash", "-c", "echo $MY_VAR"],
            env={"MY_VAR": "hello_test"},
        )
        assert result.success
        assert "hello_test" in result.stdout

    async def test_duration_times_out(self):
        """Even timed-out commands record a duration."""
        runner = RealRunner()
        result = await runner.run(["sleep", "10"], timeout=0.05)
        assert result.duration > 0.0
        assert result.returncode == -1
