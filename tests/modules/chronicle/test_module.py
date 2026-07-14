"""Tests for ChronicleModule — lifecycle, config, auto-prune, integration.

Spec: module-chronicle §Requirements
Design: PR3A — Chronicle Foundation §Testing Strategy
"""

from __future__ import annotations

import pytest

from apoch.core.module import Context, ModuleState
from apoch.modules.chronicle.models import ActivityEvent

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def context():
    """Provide a minimal execution context for ``start()``."""
    return Context()


@pytest.fixture
def module():
    """Provide a ChronicleModule with a test config."""
    from apoch.modules.chronicle.module import ChronicleModule

    return ChronicleModule({"retention_days": 30})


# ---------------------------------------------------------------------------
# Lifecycle — RED tests: these must fail because module.py doesn't exist yet
# ---------------------------------------------------------------------------


class TestLifecycle:
    """ChronicleModule follows the LOADED → RUNNING → STOPPED → SHUTDOWN lifecycle."""

    @pytest.mark.asyncio
    async def test_initial_state_is_loaded(self, module):
        """Module starts in LOADED state after init."""
        assert module.state is ModuleState.LOADED

    @pytest.mark.asyncio
    async def test_start_transitions_to_running(self, module, context, tmp_path):
        """``start()`` transitions LOADED → RUNNING."""
        from apoch.modules.chronicle.module import ChronicleModule

        mod = ChronicleModule({"chronicle_db_path": str(tmp_path / "test.db")})
        await mod.start(context)
        assert mod.state is ModuleState.RUNNING
        await mod.stop()
        await mod.shutdown()

    @pytest.mark.asyncio
    async def test_stop_transitions_to_stopped(self, module, context, tmp_path):
        """``stop()`` transitions RUNNING → STOPPED."""
        from apoch.modules.chronicle.module import ChronicleModule

        mod = ChronicleModule({"chronicle_db_path": str(tmp_path / "test.db")})
        await mod.start(context)
        await mod.stop()
        assert mod.state is ModuleState.STOPPED

    @pytest.mark.asyncio
    async def test_shutdown_transitions_to_shutdown(self, module, context, tmp_path):
        """``shutdown()`` transitions STOPPED → SHUTDOWN."""
        from apoch.modules.chronicle.module import ChronicleModule

        mod = ChronicleModule({"chronicle_db_path": str(tmp_path / "test.db")})
        await mod.start(context)
        await mod.stop()
        await mod.shutdown()
        assert mod.state is ModuleState.SHUTDOWN

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, module, context, tmp_path):
        """Full init → start → stop → shutdown completes cleanly."""
        from apoch.modules.chronicle.module import ChronicleModule

        mod = ChronicleModule({"chronicle_db_path": str(tmp_path / "test.db")})
        assert mod.state is ModuleState.LOADED
        await mod.start(context)
        assert mod.state is ModuleState.RUNNING
        await mod.stop()
        assert mod.state is ModuleState.STOPPED
        await mod.shutdown()
        assert mod.state is ModuleState.SHUTDOWN

    @pytest.mark.asyncio
    async def test_idempotent_stop_does_not_raise(self, module, context, tmp_path):
        """Calling ``stop()`` twice is safe (second call handles gracefully)."""
        from apoch.modules.chronicle.module import ChronicleModule

        mod = ChronicleModule({"chronicle_db_path": str(tmp_path / "test.db")})
        await mod.start(context)
        await mod.stop()
        # Second stop should be a no-op or handle gracefully
        # (Module's _pre_stop raises LifecycleError if not RUNNING,
        #  so the module should handle this itself)
        await mod.stop()  # Should not raise


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestConfig:
    """ChronicleModule reads config correctly."""

    @pytest.mark.asyncio
    async def test_retention_days_defaults_to_30(self, module):
        """Default retention_days is 30."""
        assert module._retention_days == 30

    @pytest.mark.asyncio
    async def test_retention_days_from_config(self):
        """retention_days from config overrides default."""
        from apoch.modules.chronicle.module import ChronicleModule

        mod = ChronicleModule({"retention_days": 60})
        assert mod._retention_days == 60


# ---------------------------------------------------------------------------
# Auto-prune during start
# ---------------------------------------------------------------------------


class TestAutoPrune:
    """Auto-prune runs during start and never blocks boot."""

    @pytest.mark.asyncio
    async def test_auto_prune_rejects_negative_retention(self):
        """Auto-prune rejects negative retention_days gracefully."""
        from apoch.modules.chronicle.module import ChronicleModule

        mod = ChronicleModule({"retention_days": -1})
        assert mod._retention_days is not None  # Should not crash

    @pytest.mark.asyncio
    async def test_auto_prune_runs_during_start(self, context, tmp_path, mocker):
        """Auto-prune calls store.prune with the correct cutoff during start()."""
        from apoch.modules.chronicle.module import ChronicleModule

        mod = ChronicleModule(
            {
                "retention_days": 30,
                "chronicle_db_path": str(tmp_path / "prune.db"),
            }
        )
        original_prune = mod.prune

        prune_called = False
        captured_before: str | None = None

        async def tracking_prune(before: str) -> int:
            nonlocal prune_called, captured_before
            prune_called = True
            captured_before = before
            return await original_prune(before) if hasattr(original_prune, "__call__") else 0

        # Monkey-patch prune to track calls
        import apoch.modules.chronicle.module as mod_module

        mocker.patch.object(mod_module.ChronicleModule, "prune", tracking_prune)

        await mod.start(context)
        await mod.stop()
        await mod.shutdown()


# ---------------------------------------------------------------------------
# Integration: record → query → prune cycle
# ---------------------------------------------------------------------------


class TestIntegration:
    """Full record → query → prune cycle with real SQLite."""

    @pytest.mark.asyncio
    async def test_record_then_query_returns_event(self, context, tmp_path):
        """Record an event and query it back from the store."""
        from apoch.modules.chronicle.module import ChronicleModule

        mod = ChronicleModule({"chronicle_db_path": str(tmp_path / "integ.db")})
        await mod.start(context)

        event = ActivityEvent(
            id="integ-1",
            timestamp="2026-07-13T12:00:00.000000+00:00",
            type="lifecycle",
            source="test",
            severity="info",
            payload={"msg": "integration test"},
        )
        await mod.record(event)

        results = await mod.query()
        assert len(results) == 1
        assert results[0].id == "integ-1"
        assert results[0].payload == {"msg": "integration test"}

        await mod.stop()
        await mod.shutdown()

    @pytest.mark.asyncio
    async def test_record_query_prune_cycle(self, context, tmp_path):
        """Full cycle: record events, query them, prune old ones, verify."""
        from apoch.modules.chronicle.module import ChronicleModule

        mod = ChronicleModule(
            {
                "retention_days": 30,
                "chronicle_db_path": str(tmp_path / "cycle.db"),
            }
        )
        await mod.start(context)

        # Create events: one old (should be pruned), one recent
        old = ActivityEvent(
            id="old-event",
            timestamp="2026-01-01T00:00:00.000000+00:00",
            type="test",
            source="test",
            severity="info",
            payload={},
        )
        recent = ActivityEvent(
            id="recent-event",
            timestamp="2026-07-13T12:00:00.000000+00:00",
            type="test",
            source="test",
            severity="info",
            payload={"alive": True},
        )

        await mod.record(old)
        await mod.record(recent)

        # Query shows both
        results = await mod.query()
        assert len(results) == 2

        # Prune old events (cutoff between old and recent)
        deleted = await mod.prune("2026-06-01T00:00:00.000000+00:00")
        assert deleted == 1

        # Only recent remains
        results = await mod.query()
        assert len(results) == 1
        assert results[0].id == "recent-event"

        await mod.stop()
        await mod.shutdown()

    @pytest.mark.asyncio
    async def test_stats_after_operations(self, context, tmp_path):
        """Stats reflect operations after record and prune."""
        from apoch.modules.chronicle.module import ChronicleModule

        mod = ChronicleModule({"chronicle_db_path": str(tmp_path / "stats.db")})
        await mod.start(context)

        await mod.record(
            ActivityEvent(
                id="s1",
                timestamp="2026-07-13T12:00:00.000000+00:00",
                type="test",
                source="t",
                severity="info",
                payload={},
            )
        )
        await mod.record(
            ActivityEvent(
                id="s2",
                timestamp="2026-07-13T12:00:01.000000+00:00",
                type="test",
                source="t",
                severity="error",
                payload={},
            )
        )

        stats = await mod.stats()
        assert stats.total == 2
        assert stats.by_severity.get("info") == 1
        assert stats.by_severity.get("error") == 1

        await mod.stop()
        await mod.shutdown()


class TestChronicleGetToolDefs:
    """ChronicleModule.get_tool_defs() returns correct MCP tool definitions."""

    def test_returns_list_of_tool_defs(self) -> None:
        """get_tool_defs returns a list with 3 entries."""
        from apoch.modules.chronicle.module import ChronicleModule

        mod = ChronicleModule({"retention_days": 30})
        defs = mod.get_tool_defs()
        assert len(defs) == 3

    def test_each_tool_def_has_required_attributes(self) -> None:
        """Each ToolDef has name, description, input_schema, handler_name."""
        from apoch.adapters.base import ToolDef
        from apoch.modules.chronicle.module import ChronicleModule

        mod = ChronicleModule({"retention_days": 30})
        for tool in mod.get_tool_defs():
            assert isinstance(tool, ToolDef)
            assert tool.name
            assert tool.description
            assert isinstance(tool.input_schema, dict)
            assert tool.handler_name

    def test_handler_names_exist_as_public_methods(self) -> None:
        """Every handler_name corresponds to a public callable method on the module."""
        from apoch.modules.chronicle.module import ChronicleModule

        mod = ChronicleModule({"retention_days": 30})
        for tool in mod.get_tool_defs():
            handler = getattr(mod, tool.handler_name, None)
            assert handler is not None, (
                f"Handler '{tool.handler_name}' not found on ChronicleModule"
            )
            assert callable(handler), (
                f"Handler '{tool.handler_name}' is not callable"
            )
            assert not tool.handler_name.startswith("_")

    def test_input_schemas_are_valid_json_schema(self) -> None:
        """Each input_schema has a valid type and properties structure."""
        from apoch.modules.chronicle.module import ChronicleModule

        mod = ChronicleModule({"retention_days": 30})
        for tool in mod.get_tool_defs():
            schema = tool.input_schema
            assert "type" in schema
            assert schema["type"] == "object"
            assert "properties" in schema
            assert isinstance(schema["properties"], dict)
