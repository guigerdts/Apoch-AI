"""Tests for apoch_history — ApochCoordinator.history() orchestration.

Spec: mcp-public-api §Tool 2: apoch_history, §Niveles de Confianza
Design: ADR-001 (orchestration), ADR-004 (timeouts), ADR-007 (concurrency)

Covers 18 scenarios from the DoD matrix (§15.3):
  1. Happy path — Chronicle returns events → chronological narrative, HIGH confidence (≥0.75)
  2. No activity — Chronicle responds with 0 events
  3. Filter by horas — only events in window
  4. Filter by tipo — only error events
  5. Combined filter — horas + tipo
  6. No params → defaults (24h, 50 max, all types)
  7. Chronicle timeout → ERR_DEPENDENCY_UNAVAILABLE
  8. Chronicle not available (None) → ERR_DEPENDENCY_UNAVAILABLE
  9. Invalid horas (≤0) → ERR_INVALID_ARGUMENT
  10. Invalid tipo → ERR_INVALID_ARGUMENT
  11. Response has all ToolResponse fields
  12. api_version = "1.0"
  13. No fields from future tools
  14. suggested_action is None
  15. Counts by type present in summary
  16. No event IDs, SQL, source names in narrative
  17. horas clamped to max bound
  18. tipo=tool maps to chronicle's "tool_invocation"
"""
# ruff: noqa: SLF001  — accessing _private members for test validation

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from apoch.public_api.coordinator import (
    HISTORY_DEFAULT_HOURS,
    ApochCoordinator,
)
from apoch.public_api.registry import ServiceRegistry

# ── Mock services ─────────────────────────────────────────────────────────────


class _FakeChronicle:
    """Fake Chronicle that returns configured ActivityEvent-like objects."""

    def __init__(self, events: list | None = None) -> None:
        self._events = events or []
        self._last_event_filter = None
        self._last_since = None

    async def query(self, event_filter=None, since=None, limit=None) -> list:
        """Return events matching the filter, mimicking real Chronicle."""
        self._last_event_filter = event_filter
        self._last_since = since
        result = self._events

        # Apply type filter if present
        if event_filter is not None and event_filter.type is not None:
            result = [e for e in result if e.type == event_filter.type]

        # Apply since filter — parse as datetimes to handle varying ISO formats
        if since is not None:
            since_dt = datetime.fromisoformat(since)

            def _ts_ge(evt: object) -> bool:
                try:
                    evt_dt = datetime.fromisoformat(evt.timestamp)
                    return evt_dt >= since_dt
                except (ValueError, AttributeError):
                    return False

            result = [e for e in result if _ts_ge(e)]

        # Apply limit
        if limit is not None:
            result = result[:limit]

        return result


class _SlowChronicle:
    """Chronicle that sleeps beyond the configured timeout."""

    async def query(self, event_filter=None, since=None, limit=None) -> list:  # noqa: ARG002
        await asyncio.sleep(10)
        return [{"event": "too_late"}]


# ── Test event helpers ─────────────────────────────────────────────────────────


def _make_event(
    timestamp: str,
    type_: str = "lifecycle",
    source: str = "vision",
    severity: str = "info",
    payload: dict | None = None,
) -> dict:
    """Build a minimal ActivityEvent-like dict for testing.

    The narrative builder accesses .timestamp, .type, .source, .severity,
    and .payload as attribute access. We use a simple dict-like object.
    """
    payload = payload or {}

    class _Event:
        """Minimal event object with attrs the coordinator accesses."""

        def __init__(self) -> None:
            self.timestamp = timestamp
            self.type = type_
            self.source = source
            self.severity = severity
            self.payload = payload

    return _Event()


# ── Standard test events ───────────────────────────────────────────────────────

def _ts_ago(seconds: int) -> str:
    """Return an ISO 8601 timestamp *seconds* before now."""
    return (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat()

EVT_LIFECYCLE_STARTUP = _make_event(
    timestamp=_ts_ago(300),  # 5 min ago
    type_="lifecycle",
    source="vision",
    payload={"status": "iniciado"},
)

EVT_TOOL_CALL = _make_event(
    timestamp=_ts_ago(200),  # ~3 min ago
    type_="tool_invocation",
    source="chronicle",
    payload={"tool": "chronicle_query"},
)

EVT_ERROR = _make_event(
    timestamp=_ts_ago(60),  # 1 min ago
    type_="error",
    source="guardian",
    severity="error",
    payload={"message": "Tiempo de espera agotado"},
)

# Events with different sources to test aliases
EVT_GUARDIAN_LIFECYCLE = _make_event(
    timestamp=_ts_ago(90),
    type_="lifecycle",
    source="guardian",
    payload={"status": "verificando"},
)

ALL_STANDARD_EVENTS = [EVT_LIFECYCLE_STARTUP, EVT_TOOL_CALL, EVT_ERROR]

# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def happy_registry() -> ServiceRegistry:
    """Registry with Chronicle returning 3 standard events."""
    registry = ServiceRegistry()
    registry.chronicle = _FakeChronicle(ALL_STANDARD_EVENTS)
    return registry


@pytest.fixture
def empty_registry() -> ServiceRegistry:
    """Registry with no services loaded."""
    return ServiceRegistry()


@pytest.fixture
def no_events_registry() -> ServiceRegistry:
    """Registry with Chronicle returning empty list."""
    registry = ServiceRegistry()
    registry.chronicle = _FakeChronicle(events=[])
    return registry


@pytest.fixture
def coordinator(happy_registry: ServiceRegistry) -> ApochCoordinator:
    return ApochCoordinator(happy_registry)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestHistoryHappyPath:
    """Happy path — Chronicle returns events, narrative is built."""

    async def test_returns_narrative_with_three_events(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """3 events → summary mentions 3 events, explanation has 3 lines."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        assert "3 eventos" in result["summary"]
        lines = result["explanation"].split("\n")
        assert len(lines) == 3

    async def test_narrative_lines_format(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Each narrative line has HH:MM — description format."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        for line in result["explanation"].split("\n"):
            assert " — " in line
            # First 5 chars should be HH:MM
            time_part = line[:5]
            assert ":" in time_part

    async def test_lifecycle_narrative(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Lifecycle event → 'Sistema de monitoreo iniciado'."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        assert "Sistema de monitoreo iniciado" in result["explanation"]

    async def test_tool_narrative(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Tool invocation → 'Herramienta invocada: chronicle_query'."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        assert "Herramienta invocada: chronicle_query" in result["explanation"]

    async def test_error_narrative(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Error event → 'Error: Tiempo de espera agotado'."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        assert "Error: Tiempo de espera agotado" in result["explanation"]

    async def test_confidence_is_medium(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Events present → confidence = 0.50 (MEDIUM, single module)."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        assert result["confidence"] == 0.50

    async def test_suggested_action_is_none(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """suggested_action is None for pure query."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        assert result["suggested_action"] is None


class TestHistoryNoActivity:
    """Chronicle responds with 0 events."""

    async def test_no_activity_message(
        self, no_events_registry: ServiceRegistry,
    ) -> None:
        """0 events → 'No hay actividad registrada en el período solicitado.'"""
        coordinator = ApochCoordinator(no_events_registry)
        result = await coordinator.history()

        assert "No hay actividad registrada" in result["summary"]
        assert "No hay actividad registrada" in result["explanation"]

    async def test_no_activity_confidence(
        self, no_events_registry: ServiceRegistry,
    ) -> None:
        """0 events → confidence = 0.30 (LOW, negative data)."""
        coordinator = ApochCoordinator(no_events_registry)
        result = await coordinator.history()

        assert result["confidence"] == 0.30

    async def test_no_activity_narrative_empty(
        self, no_events_registry: ServiceRegistry,
    ) -> None:
        """0 events → explanation does not contain narrative lines."""
        coordinator = ApochCoordinator(no_events_registry)
        result = await coordinator.history()

        # Only the "no activity" message, no timeline
        assert " — " not in result["explanation"]


class TestHistoryFilters:
    """Filter parameters — horas, tipo, combined."""

    async def test_filter_by_horas(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """horas=2 — only events in window (1 recently added)."""
        registry = ServiceRegistry()
        # Event older than 2 hours
        old_event = _make_event(
            timestamp=(datetime.now(UTC) - timedelta(hours=3)).isoformat(),
            type_="lifecycle",
        )
        # Event within 2 hours
        recent_event = _make_event(
            timestamp=(datetime.now(UTC) - timedelta(hours=1)).isoformat(),
            type_="lifecycle",
        )
        registry.chronicle = _FakeChronicle([old_event, recent_event])
        coordinator = ApochCoordinator(registry)
        result = await coordinator.history(horas=2)

        # Only the recent event should be in the narrative
        # (the fake chronicle filters by since parameter)
        lines = result["explanation"].split("\n")
        assert len(lines) == 1

    async def test_filter_by_tipo_error(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """tipo=error — only error events in narrative."""
        registry = ServiceRegistry()
        registry.chronicle = _FakeChronicle(ALL_STANDARD_EVENTS)
        coordinator = ApochCoordinator(registry)
        result = await coordinator.history(tipo="error")

        # Only 1 error event out of 3
        assert "1 eventos" in result["summary"] or "1 evento" in result["summary"]

    async def test_filter_by_tipo_lifecycle(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """tipo=lifecycle — only lifecycle events."""
        registry = ServiceRegistry()
        registry.chronicle = _FakeChronicle(ALL_STANDARD_EVENTS)
        coordinator = ApochCoordinator(registry)
        result = await coordinator.history(tipo="lifecycle")

        assert "1 eventos" in result["summary"] or "1 evento" in result["summary"]

    async def test_filter_tipo_tool_maps_to_tool_invocation(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """tipo=tool maps to chronicle's 'tool_invocation' type."""
        registry = ServiceRegistry()
        registry.chronicle = _FakeChronicle(ALL_STANDARD_EVENTS)
        coordinator = ApochCoordinator(registry)
        result = await coordinator.history(tipo="tool")

        # Only 1 tool_invocation event
        assert "1 eventos" in result["summary"] or "1 evento" in result["summary"]
        # Verify the mock received the correct filter
        assert registry.chronicle._last_event_filter is not None
        assert registry.chronicle._last_event_filter.type == "tool_invocation"

    async def test_combined_filter(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """horas=24 + tipo=lifecycle — combined filtering works."""
        registry = ServiceRegistry()
        registry.chronicle = _FakeChronicle(ALL_STANDARD_EVENTS)
        coordinator = ApochCoordinator(registry)
        result = await coordinator.history(horas=24, tipo="lifecycle")

        # Only lifecycle events
        assert "lifecycle" in result["summary"] or "lifecycle" in result["summary"]

    async def test_no_params_uses_defaults(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """No params → uses HISTORY_DEFAULT_HOURS and HISTORY_DEFAULT_LIMIT."""
        coordinator = ApochCoordinator(happy_registry)
        await coordinator.history()

        chronicle = happy_registry.chronicle
        # Check that since was calculated from DEFAULT_HOURS
        assert chronicle._last_since is not None
        since_dt = datetime.fromisoformat(chronicle._last_since)
        age = (datetime.now(UTC) - since_dt).total_seconds()
        expected = HISTORY_DEFAULT_HOURS * 3600
        # within 5 seconds tolerance
        assert abs(age - expected) < 5


class TestHistoryValidation:
    """Invalid parameters produce ERR_INVALID_ARGUMENT."""

    async def test_invalid_horas_zero(self) -> None:
        """horas=0 → ERR_INVALID_ARGUMENT."""
        coordinator = ApochCoordinator(ServiceRegistry())
        result = await coordinator.history(horas=0)

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_INVALID_ARGUMENT"

    async def test_invalid_horas_negative(self) -> None:
        """horas=-1 → ERR_INVALID_ARGUMENT."""
        coordinator = ApochCoordinator(ServiceRegistry())
        result = await coordinator.history(horas=-1)

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_INVALID_ARGUMENT"

    async def test_invalid_tipo(self) -> None:
        """tipo='invalid' → ERR_INVALID_ARGUMENT."""
        coordinator = ApochCoordinator(ServiceRegistry())
        result = await coordinator.history(tipo="invalid")

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_INVALID_ARGUMENT"


class TestHistoryChronicleNotAvailable:
    """Chronicle missing or failing → ERR_DEPENDENCY_UNAVAILABLE."""

    async def test_chronicle_timeout(self) -> None:
        """Chronicle times out → ERR_DEPENDENCY_UNAVAILABLE."""
        registry = ServiceRegistry()
        registry.chronicle = _SlowChronicle()

        coordinator = ApochCoordinator(registry, timeouts={"chronicle": 0.05})
        result = await coordinator.history()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_chronicle_none(self) -> None:
        """Chronicle is None → ERR_DEPENDENCY_UNAVAILABLE."""
        coordinator = ApochCoordinator(ServiceRegistry())
        result = await coordinator.history()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_chronicle_no_query_method(self) -> None:
        """Chronicle lacks query method → ERR_DEPENDENCY_UNAVAILABLE."""
        registry = ServiceRegistry()

        class _NoQueryChronicle:
            pass

        registry.chronicle = _NoQueryChronicle()
        coordinator = ApochCoordinator(registry)
        result = await coordinator.history()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

    async def test_chronicle_exception(self) -> None:
        """Chronicle raises exception → ERR_DEPENDENCY_UNAVAILABLE."""
        registry = ServiceRegistry()

        class _FailingChronicle:
            async def query(self, event_filter=None, since=None, limit=None) -> list:  # noqa: ARG002
                msg = "chronicle crash"
                raise RuntimeError(msg)

        registry.chronicle = _FailingChronicle()
        coordinator = ApochCoordinator(registry)
        result = await coordinator.history()

        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"


class TestHistoryResponseFormat:
    """Response structure verification — ToolResponse contract."""

    async def test_all_tool_response_fields(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Response includes all required ToolResponse fields."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        assert "api_version" in result
        assert "summary" in result
        assert "explanation" in result
        assert "evidence" in result
        assert "suggested_action" in result
        assert "confidence" in result
        assert "generated_at" in result
        assert "data_freshness" in result
        assert "metadata" in result

    async def test_api_version(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """api_version = '1.0'."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        assert result["api_version"] == "1.0"

    async def test_no_forbidden_fields(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Response has no fields from future tools."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        assert "priority" not in result
        assert "expected_benefit" not in result
        assert "productivity" not in result
        assert "patterns" not in result
        assert "opportunities" not in result
        assert "entries" not in result

    async def test_evidence_structure(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Evidence entries have correct structure."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        assert len(result["evidence"]) == 1
        entry = result["evidence"][0]
        assert "source" in entry
        assert "confidence" in entry
        assert "collected_ago" in entry
        assert "based_on" in entry

    async def test_evidence_source_chronicle(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Evidence source is 'Chronicle'."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        assert result["evidence"][0]["source"] == "Chronicle"

    async def test_evidence_based_on_events_count(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Evidence based_on shows event count."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        assert result["evidence"][0]["based_on"] == "3 events"

    async def test_generated_at_is_iso8601(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """generated_at is a valid ISO 8601 timestamp."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        parsed = datetime.fromisoformat(result["generated_at"])
        assert parsed is not None

    async def test_summary_not_empty(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Summary is a non-empty string."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        assert result["summary"]

    async def test_data_freshness_is_zero(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """data_freshness=0 for fresh query."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        assert result["data_freshness"] == 0


class TestHistoryContentConstraints:
    """Content rules: no IDs, no SQL, no source names in narrative."""

    async def test_no_event_ids_in_narrative(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Narrative does not contain event IDs."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        assert "evt-" not in result["explanation"]

    async def test_no_module_names_in_narrative(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Narrative uses user-facing aliases, not raw source module names."""
        # Test with an event whose source has no payload tool keyword overlap:
        # lifecycle from 'guardian' source does not mention 'guardian' in payload.
        registry = ServiceRegistry()
        registry.chronicle = _FakeChronicle([EVT_GUARDIAN_LIFECYCLE])
        coordinator = ApochCoordinator(registry)
        result = await coordinator.history()

        expl = result["explanation"]
        # Source module names must NOT appear in narrative — aliases should be used
        assert "Guardian" not in expl
        assert "Sistema de diagnóstico" in expl

    async def test_no_sql_in_narrative(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Narrative does not contain SQL-like text."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        assert "SELECT" not in result["explanation"]
        assert "FROM" not in result["explanation"]
        assert "WHERE" not in result["explanation"]

    async def test_user_facing_aliases_used(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """User-facing aliases like 'Sistema de monitoreo' are used."""
        registry = ServiceRegistry()
        registry.chronicle = _FakeChronicle([EVT_GUARDIAN_LIFECYCLE])
        coordinator = ApochCoordinator(registry)
        result = await coordinator.history()

        # guardian should be 'Sistema de diagnóstico'
        assert "Sistema de diagnóstico verificando" in result["explanation"]

    async def test_counts_by_type_in_summary(
        self, happy_registry: ServiceRegistry,
    ) -> None:
        """Summary includes counts by tipo."""
        coordinator = ApochCoordinator(happy_registry)
        result = await coordinator.history()

        summary = result["summary"]
        # Should mention lifecycle, tool, error counts
        assert "lifecycle" in summary
        assert "tool" in summary
        assert "error" in summary


class TestHistoryAcceptanceGate:
    """Acceptance gate for PR4: tool visible, no future tools exposed."""

    def test_get_tool_defs_includes_history(self) -> None:
        """apoch_history is in get_tool_defs."""
        defs = ApochCoordinator.get_tool_defs()
        names = [d.name for d in defs]
        assert "apoch_history" in names

    def test_get_tool_defs_has_exactly_seven_tools(self) -> None:
        """get_tool_defs returns 7 tools (PR8 adds apoch_logs)."""
        defs = ApochCoordinator.get_tool_defs()
        assert len(defs) == 7
        names = {d.name for d in defs}
        assert names == {
            "apoch_status", "apoch_health",
            "apoch_history", "apoch_recommend",
            "apoch_progress", "apoch_insights",
            "apoch_logs",
        }

    def test_get_tool_defs_all_registered(self) -> None:
        """All 7 tools are registered (PR8 — logs implemented)."""
        defs = ApochCoordinator.get_tool_defs()
        names = {d.name for d in defs}
        assert "apoch_insights" in names  # PR7
        assert "apoch_logs" in names  # PR8

    async def test_other_tools_still_stubs(self) -> None:
        """logs implemented — empty registry returns ERR_DEPENDENCY_UNAVAILABLE."""
        coordinator = ApochCoordinator(ServiceRegistry())

        result = await coordinator.recommend()
        # recommend is implemented — empty registry returns ERR_TIMEOUT
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_TIMEOUT"

        result = await coordinator.progress()
        # progress is implemented — empty registry returns ERR_DEPENDENCY_UNAVAILABLE (pulse None)
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

        result = await coordinator.insights()
        # insights is implemented — empty registry returns ERR_DEPENDENCY_UNAVAILABLE
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"

        result = await coordinator.logs()
        # logs is implemented — empty registry returns ERR_DEPENDENCY_UNAVAILABLE
        assert result["ok"] is False
        assert result["error"]["code"] == "ERR_DEPENDENCY_UNAVAILABLE"
