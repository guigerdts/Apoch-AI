"""Integration tests for ApochCoordinator.history() with REAL ChronicleModule.

Uses the real ChronicleModule with a real SQLite database (tmp_path).
Events are recorded directly via ChronicleModule.record(), then queried
via ApochCoordinator.history().  Proves that history() correctly
interprets REAL Chronicle data — not just fake event objects.

Design:
    - Real ChronicleModule (from apoch.modules.chronicle.module)
    - Real SqliteEventStore (backed by a temp file)
    - Real ApochCoordinator + ServiceRegistry
    - No mocks: the Chronicle is fully functional
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apoch.modules.chronicle.models import ActivityEvent
from apoch.public_api.coordinator import ApochCoordinator
from apoch.public_api.registry import ServiceRegistry

# ---------------------------------------------------------------------------
# Test event helpers
# ---------------------------------------------------------------------------


def _fixed_ts(days_ago: int = 0, hours_ago: int = 0, minutes_ago: int = 0) -> str:
    """Return ISO 8601 timestamp offset from now (fixed for determinism)."""
    dt = datetime.now(UTC) - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
    return dt.isoformat()


EVT_LIFECYCLE = ActivityEvent(
    id="integ-lifecycle-1",
    timestamp=_fixed_ts(minutes_ago=30),
    type="lifecycle",
    source="vision",
    severity="info",
    payload={"status": "iniciado"},
)

EVT_TOOL = ActivityEvent(
    id="integ-tool-1",
    timestamp=_fixed_ts(minutes_ago=20),
    type="tool_invocation",
    source="chronicle",
    severity="info",
    payload={"tool": "chronicle_query"},
)

EVT_ERROR = ActivityEvent(
    id="integ-error-1",
    timestamp=_fixed_ts(minutes_ago=10),
    type="error",
    source="guardian",
    severity="error",
    payload={"message": "Tiempo de espera agotado"},
)

ALL_STANDARD_EVENTS = [EVT_LIFECYCLE, EVT_TOOL, EVT_ERROR]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def chronicle_and_coordinator(tmp_path):
    """Return (ChronicleModule, ApochCoordinator) with a started real Chronicle.

    Cleans up lifecycle (stop + shutdown) after the test.
    """
    from apoch.core.module import Context
    from apoch.modules.chronicle.module import ChronicleModule

    mod = ChronicleModule({"chronicle_db_path": str(tmp_path / "history_int.db")})
    await mod.start(Context())

    registry = ServiceRegistry()
    registry.chronicle = mod

    coordinator = ApochCoordinator(registry)

    yield mod, coordinator

    await mod.stop()
    await mod.shutdown()


# ---------------------------------------------------------------------------
# Tests — REAL ChronicleModule integration
# ---------------------------------------------------------------------------


class TestHistoryWithRealChronicle:
    """Verifies ApochCoordinator.history() against the real ChronicleModule."""

    async def test_happy_path_returns_event_count(self, chronicle_and_coordinator, tmp_path):
        """Record 3 events via real Chronicle → history() returns count=3."""
        mod, coordinator = chronicle_and_coordinator
        for evt in ALL_STANDARD_EVENTS:
            await mod.record(evt)

        result = await coordinator.history()

        assert "3 eventos" in result["summary"]

    async def test_narrative_line_format(self, chronicle_and_coordinator, tmp_path):
        """Each narrative line has HH:MM — description format."""
        mod, coordinator = chronicle_and_coordinator
        for evt in ALL_STANDARD_EVENTS:
            await mod.record(evt)

        result = await coordinator.history()

        for line in result["explanation"].split("\n"):
            assert " — " in line
            time_part = line[:5]
            assert ":" in time_part

    async def test_lifecycle_narrative(self, chronicle_and_coordinator, tmp_path):
        """Lifecycle event → 'Sistema de monitoreo iniciado' (source alias + status)."""
        mod, coordinator = chronicle_and_coordinator
        await mod.record(EVT_LIFECYCLE)

        result = await coordinator.history()

        assert "Sistema de monitoreo iniciado" in result["explanation"]

    async def test_tool_invocation_narrative(self, chronicle_and_coordinator, tmp_path):
        """Tool invocation → 'Herramienta invocada: chronicle_query'."""
        mod, coordinator = chronicle_and_coordinator
        await mod.record(EVT_TOOL)

        result = await coordinator.history()

        assert "Herramienta invocada: chronicle_query" in result["explanation"]

    async def test_error_narrative(self, chronicle_and_coordinator, tmp_path):
        """Error event → 'Error: Tiempo de espera agotado'."""
        mod, coordinator = chronicle_and_coordinator
        await mod.record(EVT_ERROR)

        result = await coordinator.history()

        assert "Error: Tiempo de espera agotado" in result["explanation"]

    async def test_no_events_returns_empty_message(self, chronicle_and_coordinator, tmp_path):
        """Empty DB → 'No hay actividad registrada' + confidence 0.30."""
        mod, coordinator = chronicle_and_coordinator

        result = await coordinator.history()

        assert "No hay actividad registrada" in result["summary"]
        assert "No hay actividad registrada" in result["explanation"]
        assert result["confidence"] == 0.30

    async def test_confidence_with_events(self, chronicle_and_coordinator, tmp_path):
        """Events present → confidence = 0.50 (MEDIUM, single module)."""
        mod, coordinator = chronicle_and_coordinator
        await mod.record(EVT_LIFECYCLE)

        result = await coordinator.history()

        assert result["confidence"] == 0.50

    async def test_suggested_action_is_none(self, chronicle_and_coordinator, tmp_path):
        """suggested_action is None for pure query."""
        mod, coordinator = chronicle_and_coordinator
        await mod.record(EVT_LIFECYCLE)

        result = await coordinator.history()

        assert result["suggested_action"] is None

    async def test_filter_by_tipo_tool(self, chronicle_and_coordinator, tmp_path):
        """tipo=tool → only tool_invocation events in narrative."""
        mod, coordinator = chronicle_and_coordinator
        for evt in ALL_STANDARD_EVENTS:
            await mod.record(evt)

        result = await coordinator.history(tipo="tool")

        assert "1 eventos" in result["summary"] or "1 evento" in result["summary"]
        assert "Herramienta invocada" in result["explanation"]
        # No lifecycle or error narrative
        assert "iniciado" not in result["explanation"]
        assert "Error" not in result["explanation"]

    async def test_filter_by_tipo_error(self, chronicle_and_coordinator, tmp_path):
        """tipo=error → only error events in narrative."""
        mod, coordinator = chronicle_and_coordinator
        for evt in ALL_STANDARD_EVENTS:
            await mod.record(evt)

        result = await coordinator.history(tipo="error")

        assert "1 eventos" in result["summary"] or "1 evento" in result["summary"]
        assert "Error" in result["explanation"]
        # No lifecycle or tool narrative
        assert "iniciado" not in result["explanation"]
        assert "Herramienta" not in result["explanation"]

    async def test_response_has_all_tool_response_fields(
        self,
        chronicle_and_coordinator,
        tmp_path,
    ):
        """Response includes all required ToolResponse fields and api_version 1.0."""
        mod, coordinator = chronicle_and_coordinator
        await mod.record(EVT_LIFECYCLE)

        result = await coordinator.history()

        assert result["api_version"] == "1.0"
        assert "summary" in result
        assert "explanation" in result
        assert "evidence" in result
        assert "suggested_action" in result
        assert "confidence" in result
        assert "generated_at" in result
        assert "data_freshness" in result
        assert "metadata" in result
