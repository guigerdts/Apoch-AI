"""ChronicleModule — activity recording module with SQLite storage.

Spec: module-chronicle §Public Interfaces, §Requirements
Design: PR3A — Chronicle Foundation §Interfaces / Contracts
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apoch._compat import user_data_dir
from apoch.core.module import Context, Module, ModuleState
from apoch.modules.chronicle.models import ActivityEvent, EventFilter, EventStats
from apoch.modules.chronicle.storage import SqliteEventStore

log = logging.getLogger(__name__)


class ChronicleModule(Module):
    """Chronicle — persistent activity recording for Apoch-AI.

    Records lifecycle events, tool invocations, errors, and user actions
    with a configurable retention period and SQLite-backed storage.

    Configuration (via ``config`` dict):
        ``retention_days`` (int, default 30):
            Events older than this are pruned on startup.
        ``chronicle_db_path`` (str, optional):
            Override the default database path.
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._retention_days: int = config.get("retention_days", 30)
        self._conn: sqlite3.Connection | None = None
        self._store: SqliteEventStore | None = None

    # ------------------------------------------------------------------
    # Lifecycle validation overrides
    # ------------------------------------------------------------------

    def _pre_stop(self) -> None:
        """Allow idempotent ``stop()`` — no-op if already STOPPED.

        The Module ABC lifecycle decorator calls ``_pre_stop()`` before
        the method body.  Without this override, a second ``stop()``
        would raise ``LifecycleError`` because the state is no longer
        RUNNING.
        """
        if self._state == ModuleState.STOPPED:
            return  # Already stopped — idempotent
        # Delegate to the standard lifecycle validation (RUNNING → STOPPED)
        super()._pre_stop()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, context: Context) -> None:  # noqa: ARG002
        """Open the SQLite database, initialise the schema, and run auto-prune.

        The database is created at ``user_data_dir() / "chronicle.db"``
        unless overridden via ``config["chronicle_db_path"]``.
        """
        db_path = (
            Path(self._config["chronicle_db_path"])
            if "chronicle_db_path" in self._config
            else user_data_dir() / "chronicle.db"
        )
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(db_path))
        self._store = SqliteEventStore(self._conn)
        self._store.init_schema()

        # Auto-prune: silent, non-blocking
        self._run_auto_prune()

        log.info("Chronicle started — db=%s, retention_days=%s", db_path, self._retention_days)

    async def stop(self) -> None:
        """Close the database connection.

        Safe to call multiple times — subsequent calls are no-ops.
        """
        # The lifecycle decorator (_pre_stop) already transitioned
        # RUNNING → STOPPED.  If we're already not RUNNING, the state
        # machine raises, so we handle the idempotent case by catching.
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            self._store = None

    async def shutdown(self) -> None:
        """Final cleanup.  No-op after ``stop()``."""
        # Module ABC handles the state transition STOPPED → SHUTDOWN
        # via the injected _validate_lifecycle decorator.

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def record(self, event: ActivityEvent) -> None:
        """Persist an activity event."""
        self._store.record(event)

    async def query(self, event_filter: EventFilter | None = None) -> list[ActivityEvent]:
        """Retrieve events matching *event_filter* (default: no filter)."""
        return self._store.query(event_filter or EventFilter())

    # ------------------------------------------------------------------
    # MCP tool handlers (thin wrappers — adapt individual kwargs to
    # domain-object signatures for dispatch via _dispatch(**kwargs))
    # ------------------------------------------------------------------

    async def record_tool(
        self,
        source: str,
        event_type: str,
        details: dict | None = None,
    ) -> dict:
        """Tool handler for chronicle_record — wraps record()."""
        import uuid
        from datetime import UTC, datetime

        event = ActivityEvent(
            id=uuid.uuid4().hex,
            timestamp=datetime.now(UTC).isoformat(),
            type=event_type,
            source=source,
            severity="info",
            payload=details or {},
        )
        await self.record(event)
        return {"ok": True, "id": event.id}

    async def query_tool(
        self,
        source: str | None = None,
        event_type: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 100,
    ) -> dict:
        """Tool handler for chronicle_query — wraps query()."""
        event_filter = EventFilter(
            type=event_type,  # ToolDef uses "event_type"; EventFilter uses "type"
            source=source,
            since=since,
            until=until,
            limit=limit,
        )
        results = await self.query(event_filter)
        return {"ok": True, "count": len(results), "events": results}

    async def prune(self, before: str) -> int:
        """Delete events older than *before* (ISO 8601).

        Returns the number of deleted rows.
        """
        return self._store.prune(before)

    async def stats(self) -> EventStats:
        """Return aggregate statistics over all recorded events."""
        return self._store.stats()

    # ------------------------------------------------------------------
    # Cross-module services
    # ------------------------------------------------------------------

    @property
    def services(self) -> dict[str, Callable]:
        """Publish the event-recording API as a cross-module service.

        Published contract:
            key:       ``"chronicle.record"``
            signature: ``async (event: ActivityEvent) -> None``
            optional:  Yes — consumer modules degrade gracefully.
        """
        return {"chronicle.record": self.record}

    # ------------------------------------------------------------------
    # MCP tool definitions
    # ------------------------------------------------------------------

    def get_tool_defs(self) -> list:
        """Return MCP tool definitions for this module.

        Returns:
            List of 3 ``ToolDef`` entries (record, query, stats).
        """
        from apoch.adapters.base import ToolDef  # noqa: PLC0415

        return [
            ToolDef(
                name="chronicle_record",
                description="Record an activity event in the chronicle log.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "Event source identifier.",
                        },
                        "event_type": {
                            "type": "string",
                            "description": "Event type (tool_call, error, state_change).",
                        },
                        "details": {
                            "type": "object",
                            "description": "Optional structured payload.",
                        },
                    },
                    "required": ["source", "event_type"],
                },
                handler_name="record_tool",
            ),
            ToolDef(
                name="chronicle_query",
                description="Query recorded activity events.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "Optional source filter.",
                        },
                        "event_type": {
                            "type": "string",
                            "description": "Optional event type filter.",
                        },
                        "since": {
                            "type": "string",
                            "format": "date-time",
                            "description": "ISO 8601 start timestamp.",
                        },
                        "until": {
                            "type": "string",
                            "format": "date-time",
                            "description": "ISO 8601 end timestamp.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results.",
                            "default": 100,
                        },
                    },
                },
                handler_name="query_tool",
            ),
            ToolDef(
                name="chronicle_stats",
                description="Return aggregate statistics over all recorded events.",
                input_schema={"type": "object", "properties": {}},
                handler_name="stats",
            ),
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_auto_prune(self) -> None:
        """Prune events older than the configured retention period.

        Failures are logged and silently swallowed — auto-prune never
        blocks module startup.
        """
        try:
            deleted = self._store.prune(self._auto_prune_cutoff())
            if deleted:
                log.info("Auto-prune removed %d event(s)", deleted)
        except Exception:  # noqa: BLE001
            log.exception("Auto-prune failed — continuing startup")

    def _auto_prune_cutoff(self) -> str:
        """Calculate the ISO 8601 cutoff for auto-prune.

        Returns a timestamp *retention_days* in the past.
        """
        cutoff = datetime.now(UTC) - timedelta(days=self._retention_days)
        return cutoff.isoformat()
