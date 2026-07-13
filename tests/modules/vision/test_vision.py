"""RED tests for degraded Vision Module operation (Task 5.2).

Spec: module-vision §Degraded Behaviour
Design: PR3C — Vision Module §Degraded modes
"""

from __future__ import annotations

from unittest.mock import patch

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


__all__ = ["TestVisionDegradedFoundation"]
