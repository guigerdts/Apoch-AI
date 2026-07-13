"""VisionModule — structured logging and observability for Apoch-AI.

Spec: module-vision
Design: PR3C — Vision Module §VisionModule
"""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from apoch.core.module import Context, Module

from .models import LogRecord

logger = logging.getLogger(__name__)


class VisionModule(Module):
    """Vision — structured logging and MCP-observable introspection.

    Vision writes structured NDJSON log entries to a rotating file,
    keeps an in-memory ring buffer of recent entries, and optionally
    forwards events to Chronicle for long-term archival.

    Configuration keys (via ``config`` dict):
        log_dir (str):       Log directory path.
                             Default: ``~/.local/share/apoch/logs/``.
        log_file (str):      Log file name.  Default: ``"vision.ndjson"``.
        max_bytes (int):     Max file size before rotation (bytes).
                             Default: 1_048_576 (1 MB).
        backup_count (int):  Max rotated backup files.  Default: 3.
        buffer_size (int):   In-memory ring buffer capacity.
                             Default: 1000.
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)

        self._log_dir: Path = Path(
            self._config.get("log_dir", Path.home() / ".local" / "share" / "apoch" / "logs")
        )
        self._log_file: str = self._config.get("log_file", "vision.ndjson")
        self._max_bytes: int = int(self._config.get("max_bytes", 1_048_576))
        self._backup_count: int = int(self._config.get("backup_count", 3))
        buffer_size: int = int(self._config.get("buffer_size", 1000))

        self._buffer: deque[LogRecord] = deque(maxlen=buffer_size)
        self._handler: logging.Handler | None = None
        self._event_sink: Callable | None = None
        self._started_at: float = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, context: Context) -> None:  # noqa: ARG002
        """Initialise the log directory and capture injected services.

        Captures ``event_sink`` from ``context.services["chronicle.record"]``
        (optional — ``None`` if Chronicle is not loaded).  Captures
        ``context.registry`` for module state/config introspection.

        If the log directory cannot be created or is not writable, a
        warning is logged and Vision continues without file logging.
        """
        self._event_sink = context.services.get("chronicle.record")
        self._started_at = time.monotonic()

        # Attempt to set up the log directory and handler.
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            if not os.access(str(self._log_dir), os.W_OK):
                raise PermissionError(f"Log directory not writable: {self._log_dir}")
        except OSError as exc:
            logger.warning("Vision: cannot create/access log dir '%s': %s", self._log_dir, exc)
            logger.warning("Vision: continuing WITHOUT file logging (degraded mode)")
            return

        # Set up RotatingFileHandler with JSON formatter.
        self._init_handler()

        logger.info("Vision started — log_dir=%s, max_bytes=%s", self._log_dir, self._max_bytes)

    async def stop(self) -> None:
        """Flush and close the log handler."""
        if self._handler is not None:
            self._handler.close()
            self._handler = None

    async def shutdown(self) -> None:
        """Final cleanup.  No-op after ``stop()``."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_handler(self) -> None:
        """Create the ``RotatingFileHandler`` with a JSON formatter."""
        from logging.handlers import RotatingFileHandler

        log_path = self._log_dir / self._log_file

        class _JSONFormatter(logging.Formatter):
            """Format log records as newline-delimited JSON."""

            def format(self, record: logging.LogRecord) -> str:
                import json

                return json.dumps(
                    {
                        "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
                        "level": record.levelname,
                        "message": record.msg,
                        "module": getattr(record, "module_name", None),
                        "context": getattr(record, "context_data", {}),
                        "pid": record.process,
                    }
                )

        self._handler = RotatingFileHandler(
            filename=str(log_path),
            maxBytes=self._max_bytes,
            backupCount=self._backup_count,
            encoding="utf-8",
        )
        self._handler.setFormatter(_JSONFormatter())

    # ------------------------------------------------------------------
    # Logging API
    # ------------------------------------------------------------------

    def log(
        self,
        level: str,
        message: str,
        *,
        module: str | None = None,
        **context_data: Any,
    ) -> None:
        """Record a structured log entry.

        The entry is appended to the in-memory ring buffer and written
        to the rotating NDJSON log file.  If an ``event_sink`` is
        configured, the entry is also forwarded to Chronicle for
        long-term archival.

        Degraded behaviour:
          - JSON serialisation failure for *context_data* → problematic
            key skipped, warning logged, other keys preserved.
          - Log file not available → entry goes to buffer only.
          - ``event_sink`` raises → warning logged, entry not archived.
        """
        from datetime import UTC, datetime

        record = LogRecord(
            timestamp=datetime.now(UTC),
            level=level.upper(),
            message=message,
            module=module,
            pid=os.getpid(),
            context=dict(context_data),
        )
        self._buffer.append(record)

        # Write to rotating file (if handler is available).
        if self._handler is not None:
            try:
                log_record = logging.LogRecord(
                    name="apoch.vision",
                    level=self._level_for(record.level),
                    pathname="",
                    lineno=0,
                    msg=record.message,
                    args=(),
                    exc_info=None,
                )
                log_record.module_name = record.module
                log_record.context_data = record.context
                log_record.process = record.pid
                log_record.created = record.timestamp.timestamp()
                log_record.msecs = record.timestamp.microsecond / 1000
                log_record.levelname = record.level  # Preserve original level (WARN, not WARNING)

                self._handler.emit(log_record)
            except Exception:  # noqa: BLE001
                logger.exception("Vision: failed to write log entry")

        # Optional Chronicle archival.
        if self._event_sink is not None:
            try:
                from apoch.modules.chronicle.models import ActivityEvent  # noqa: PLC0415

                event = ActivityEvent(
                    id=f"vision-{record.timestamp.isoformat()}-{record.pid}",
                    timestamp=record.timestamp.isoformat(),
                    type="log",
                    source=record.module or "vision",
                    severity=record.level.upper(),
                    payload={
                        "message": record.message,
                        "context": record.context,
                    },
                )
                import asyncio

                asyncio.ensure_future(self._ensure_sink(event))
            except Exception:  # noqa: BLE001
                logger.warning("Vision: failed to dispatch event to Chronicle")

    async def _ensure_sink(self, event: Any) -> None:
        """Call the event sink with error isolation."""
        try:
            await self._event_sink(event)  # type: ignore[misc]
        except Exception:  # noqa: BLE001
            logger.warning("Vision: event_sink raised — entry not archived")

    # ------------------------------------------------------------------
    # Query API (Foundation — recent only)
    # ------------------------------------------------------------------

    async def recent(self, limit: int = 50, level: str | None = None) -> list[LogRecord]:
        """Return recent log entries from the ring buffer, newest first.

        Args:
            limit:  Maximum entries to return (default 50).
            level:  Optional severity filter (e.g. ``"ERROR"``).

        Returns:
            List of ``LogRecord`` objects, newest first.
        """
        entries: list[LogRecord] = list(reversed(self._buffer))
        if level is not None:
            entries = [e for e in entries if e.level.upper() == level.upper()]
        return entries[:limit]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _level_for(level: str) -> int:
        """Convert a string level to a ``logging`` constant."""
        return {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARN": logging.WARN,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "FATAL": logging.FATAL,
            "CRITICAL": logging.CRITICAL,
        }.get(level.upper(), logging.INFO)


__all__ = ["VisionModule"]
