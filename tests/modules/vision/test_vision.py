"""Tests for Vision Module — degraded modes and query APIs.

Spec: module-vision §Degraded Behaviour, §MCP Tools
Design: PR3C — Vision Module §Degraded modes, §Testing Strategy
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apoch.core.module import Context, ModuleState


class TestVisionDegradedFoundation:
    """Vision operates in degraded mode when dependencies are missing."""

    @pytest.fixture
    def vision(self):
        from apoch.modules.vision.module import VisionModule

        return VisionModule({})

    @pytest.fixture
    def context(self):
        return Context()

    @pytest.mark.asyncio
    async def test_start_with_empty_context(self, vision, context):
        """start() works with empty context — event_sink is None."""
        await vision.start(context)
        assert vision._event_sink is None
        assert vision._state is ModuleState.RUNNING

    @pytest.mark.asyncio
    @patch("os.access", return_value=False)
    async def test_start_with_no_log_dir(self, mock_access, vision, context, tmp_path):
        """start() works when log dir is not writable — no file handler."""
        vision._log_dir = tmp_path / "vision_logs"
        await vision.start(context)
        assert vision._handler is None
        assert vision._state is ModuleState.RUNNING

    @pytest.mark.asyncio
    async def test_log_with_no_event_sink(self, vision, context):
        """log() works without event_sink — no Chronicle archive."""
        await vision.start(context)
        assert vision._event_sink is None

        vision.log("INFO", "test message", module="vision")
        assert len(vision._buffer) == 1
        assert vision._buffer[0].message == "test message"

    @pytest.mark.asyncio
    async def test_event_sink_raises(self, vision, context):
        """event_sink that raises does not crash Vision."""
        async def _failing_sink(event):  # noqa: ARG001
            msg = "chronicle unavailable"
            raise RuntimeError(msg)

        context.services["chronicle.record"] = _failing_sink
        await vision.start(context)
        assert vision._event_sink is not None

        vision.log("WARN", "keep going")
        assert len(vision._buffer) == 1
        assert vision._buffer[0].message == "keep going"


class TestVisionDegradedQueryAPIs:
    """Query APIs work in degraded mode — Task 5.2b."""

    @pytest.fixture
    def vision(self):
        from apoch.modules.vision.module import VisionModule

        return VisionModule({})

    @pytest.fixture
    def context(self):
        return Context()

    @pytest.mark.asyncio
    async def test_module_state_no_registry(self, vision, context):
        """module_state() returns {} when no registry."""
        await vision.start(context)
        assert vision._registry is None
        result = await vision.module_state()
        assert result == {}

    @pytest.mark.asyncio
    async def test_module_config_no_registry(self, vision, context):
        """module_config() returns {} when no registry."""
        await vision.start(context)
        result = await vision.module_config()
        assert result == {}

    @pytest.mark.asyncio
    async def test_module_state_unknown_module(self, vision, context):
        """module_state('unknown') returns not_found."""
        mock_registry = MagicMock()
        mock_registry.loaded = {}
        context.registry = mock_registry
        await vision.start(context)
        result = await vision.module_state("nonexistent")
        assert result == {"nonexistent": {"not_found": True}}

    @pytest.mark.asyncio
    async def test_module_config_unknown_module(self, vision, context):
        """module_config('unknown') returns not_found."""
        mock_registry = MagicMock()
        mock_registry.loaded = {}
        context.registry = mock_registry
        await vision.start(context)
        result = await vision.module_config("nonexistent")
        assert result == {"nonexistent": {"not_found": True}}

    @pytest.mark.asyncio
    async def test_recent_empty_buffer(self, vision, context):
        """recent() returns [] when buffer is empty."""
        await vision.start(context)
        result = await vision.recent()
        assert result == []


class TestChronicleIntegration:
    """Full integration with Chronicle — Task 5.3."""

    @pytest.fixture
    def vision(self):
        from apoch.modules.vision.module import VisionModule

        return VisionModule({})

    @pytest.fixture
    def context(self):
        ctx = Context()
        # Simulate Registry having gathered chronicle.record service
        ctx.services["chronicle.record"] = AsyncMock()
        return ctx

    @pytest.mark.asyncio
    async def test_log_calls_event_sink(self, vision, context):
        """log() calls Chronicle.record() when event_sink is set."""
        await vision.start(context)
        assert vision._event_sink is not None

        vision.log("INFO", "test integration", module="vision")
        # Give the fire-and-forget task time to dispatch
        import asyncio

        await asyncio.sleep(0.05)
        # Verify event_sink was called at least once
        vision._event_sink.assert_called()


__all__ = [
    "TestVisionDegradedFoundation",
    "TestVisionDegradedQueryAPIs",
    "TestChronicleIntegration",
]
