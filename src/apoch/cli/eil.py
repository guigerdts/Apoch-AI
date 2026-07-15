"""``apoch eil`` — Engineering Intelligence Layer dashboard and status.

Commands for inspecting Pulse, Optimizer, Oracle, and Guardian state
from the CLI without depending on specific module implementations.

Design: Engineering Intelligence Subcommands (eil/)
Spec: cli-interface §EIL Dashboard, §EIL Status

Uses ``ModuleRegistry`` and ``Context`` to lazily-load EIL modules and
call read-only cross-module services.  Never imports module types
directly — everything flows through duck-typed service lookups.
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
from typing import Any

import typer

from apoch.core.module import Context
from apoch.core.registry import ModuleRegistry

logger = logging.getLogger(__name__)

cli_app = typer.Typer(
    help="Engineering Intelligence Layer — Pulse, Optimizer, Oracle, Guardian.",
    no_args_is_help=True,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EIL_MODULES = ("pulse", "optimizer", "oracle", "guardian", "chronicle")

_STATE_SYMBOLS: dict[str, str] = {
    "RUNNING": "●",
    "LOADED": "○",
    "STOPPED": "○",
    "SHUTDOWN": "○",
    "FAILED": "✕",
}

_PRIORITY_COLORS: dict[str, str] = {
    "critical": "CRIT",
    "high": "HIGH",
    "medium": "MED ",
    "low": "LOW ",
}

_HYPOTHESIS_TYPE_COLORS: dict[str, str] = {
    "anomaly": "ANOM",
    "pattern": "PATT",
    "opportunity": "OPPT",
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _symbol(state: str | None) -> str:
    if state is None:
        return "○"
    return _STATE_SYMBOLS.get(state.upper(), "○")


def _module_state(registry: ModuleRegistry, name: str) -> str | None:
    """Get the state string for a module, or ``None`` if not loaded."""
    mod = registry.loaded.get(name)
    if mod is None:
        return None
    return mod.state.value if mod.state else None


async def _load_and_start() -> tuple[Context, ModuleRegistry]:
    """Create a ``Context``, load EIL modules, start them.

    Returns:
        A (context, registry) tuple.  Modules that fail to load or start
        are skipped — never raises.
    """
    ctx = Context()
    registry = ModuleRegistry(config={})
    ctx.registry = registry

    for name in EIL_MODULES:
        try:
            registry.load(name)
        except Exception:  # noqa: BLE001
            pass  # Module not available — skip gracefully

    if registry.loaded:
        await registry.start_all(ctx)

    return ctx, registry


def _try_call(
    ctx: Context | ModuleRegistry | Any,
    service_key: str | None = None,
    fallback: Any = None,
    module_ref: Any = None,
    method_name: str | None = None,
) -> Any:
    """Safely call a service or module method, returning *fallback* on failure.

    Kwargs:
        service_key: Call ``ctx.services[service_key]()``.
        module_ref:  Call ``getattr(module_ref, method_name)()``
        method_name: Required when using *module_ref*.
    """
    if service_key and hasattr(ctx, "services"):
        try:
            fn = ctx.services.get(service_key)
            if fn is not None:
                return fn()
        except Exception:  # noqa: BLE001
            pass
        return fallback

    if module_ref is not None and method_name is not None:
        try:
            fn = getattr(module_ref, method_name, None)
            if fn is not None:
                return fn()
        except Exception:  # noqa: BLE001
            pass
        return fallback

    return fallback


def _fmt_module_line(
    name: str, symbol_char: str, state_label: str, detail: str = ""
) -> str:
    """Format a single module line for the dashboard.

    Example::

        ● Pulse       started   42 measurements
    """
    padding = " " * (12 - len(name))
    detail_str = f"  {detail}" if detail else ""
    return f"  {symbol_char} {name}{padding}{state_label}{detail_str}"


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


@cli_app.command()
def dashboard(
    json: bool = typer.Option(
        False, "--json", help="Output in JSON format."
    ),
) -> None:
    """Show a compact EIL overview (default command).

    Displays Pulse, Optimizer, Oracle, Guardian, and Chronicle state
    in a one-shot dashboard.  Degrades gracefully when modules are
    unavailable.
    """
    ctx, registry = asyncio.run(_load_and_start())

    pulse_mod = registry.loaded.get("pulse")
    opt_mod = registry.loaded.get("optimizer")
    oracle_mod = registry.loaded.get("oracle")
    guardian_mod = registry.loaded.get("guardian")
    chronicle_mod = registry.loaded.get("chronicle")

    # ---- JSON output ----
    if json:
        data: dict[str, Any] = {}

        for mod_name, mod_ref in (
            ("pulse", pulse_mod),
            ("optimizer", opt_mod),
            ("oracle", oracle_mod),
            ("guardian", guardian_mod),
            ("chronicle", chronicle_mod),
        ):
            entry: dict[str, Any] = {}
            state_val = _module_state(registry, mod_name) or "not_loaded"
            entry["state"] = state_val
            if mod_ref is not None and state_val == "RUNNING":
                # Module-specific enrichment
                if mod_name == "pulse":
                    units = _try_call(ctx, "pulse.measurements", [])
                    entry["measurement_count"] = len(units)
                elif mod_name == "optimizer":
                    s = _try_call(ctx, "optimizer.status", {})
                    entry.update(s)
                elif mod_name == "oracle":
                    s = _try_call(ctx, "oracle.status", {})
                    entry.update(s)
                elif mod_name == "guardian":
                    diags = _try_call(
                        ctx, module_ref=guardian_mod, method_name="all_diagnostics", fallback={}
                    )
                    entry["failed_module_count"] = len(diags)
            data[mod_name] = entry

        typer.echo(_json.dumps(data, indent=2, default=str))
        return

    # ---- Text output ----
    lines: list[str] = []
    lines.append("EIL Dashboard")
    lines.append("=" * 60)

    # Pulse
    if pulse_mod and _module_state(registry, "pulse") == "RUNNING":
        units = _try_call(ctx, "pulse.measurements", [])
        n = len(units)
        detail = f"{n} measurement{'s' if n != 1 else ''} tracked"
        lines.append(_fmt_module_line("Pulse", "●", "started", detail))
    else:
        st = _module_state(registry, "pulse") or "not loaded"
        lines.append(_fmt_module_line("Pulse", _symbol(st), st))

    # Optimizer
    if opt_mod and _module_state(registry, "optimizer") == "RUNNING":
        opt_data = _try_call(ctx, "optimizer.status", {})
        hyps = opt_data.get("hypothesis_count", "?")
        baselines = opt_data.get("baseline_count", "?")
        pulse_ok = opt_data.get("pulse_connected", False)
        detail = (
            f"{hyps} hypotheses, {baselines} baselines  "
            f"(Pulse {'✓' if pulse_ok else '✗'})"
        )
        lines.append(_fmt_module_line("Optimizer", "●", "started", detail))
    else:
        st = _module_state(registry, "optimizer") or "not loaded"
        lines.append(_fmt_module_line("Optimizer", _symbol(st), st))

    # Oracle
    if oracle_mod and _module_state(registry, "oracle") == "RUNNING":
        recs = _try_call(ctx, "oracle.recommendations", [])
        detail = f"{len(recs)} active recommendation{'s' if len(recs) != 1 else ''}"
        lines.append(_fmt_module_line("Oracle", "●", "started", detail))
    else:
        st = _module_state(registry, "oracle") or "not loaded"
        lines.append(_fmt_module_line("Oracle", _symbol(st), st))

    # Guardian
    if guardian_mod and _module_state(registry, "guardian") == "RUNNING":
        diags = _try_call(
            ctx, module_ref=guardian_mod, method_name="all_diagnostics", fallback={}
        )
        detail = f"{len(diags)} failed module{'s' if len(diags) != 1 else ''}"
        lines.append(_fmt_module_line("Guardian", "●", "started", detail))
    else:
        st = _module_state(registry, "guardian") or "not loaded"
        lines.append(_fmt_module_line("Guardian", _symbol(st), st))

    # Chronicle
    if chronicle_mod and _module_state(registry, "chronicle") == "RUNNING":
        lines.append(_fmt_module_line("Chronicle", "●", "started", ""))
    else:
        st = _module_state(registry, "chronicle") or "not loaded"
        lines.append(_fmt_module_line("Chronicle", _symbol(st), st))

    typer.echo("\n".join(lines))


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------


@cli_app.command()
def status(
    json: bool = typer.Option(
        False, "--json", help="Output in JSON format."
    ),
) -> None:
    """Show detailed EIL module status and service availability."""
    ctx, registry = asyncio.run(_load_and_start())

    rows: list[dict[str, Any]] = []
    for name in EIL_MODULES:
        mod = registry.loaded.get(name)
        state_val = _module_state(registry, name) or "—"
        services: list[str] = []

        if mod is not None and state_val == "RUNNING":
            svc = getattr(mod, "services", None)
            if isinstance(svc, dict):
                services = sorted(svc.keys())

        rows.append({"name": name, "state": state_val, "services": services})

    if json:
        data = {
            "modules": [
                {
                    "name": r["name"],
                    "state": r["state"],
                    "services": [
                        {"key": k, "description": _service_descriptor(k)}
                        for k in r["services"]
                    ],
                }
                for r in rows
            ]
        }
        typer.echo(_json.dumps(data, indent=2, default=str))
        return

    # Text table
    lines: list[str] = []
    lines.append("EIL Module Status")
    lines.append("-" * 60)
    for r in rows:
        sym = _symbol(r["state"] if r["state"] != "—" else None)
        service_str = ", ".join(
            f"{s} ✓" for s in r["services"]
        ) if r["services"] else "—"
        lines.append(f"  {sym} {r['name']:<12} {r['state']:<9}  {service_str}")
    typer.echo("\n".join(lines))


@cli_app.command()
def hypotheses(
    limit: int = typer.Option(10, "--limit", help="Max hypotheses to show."),
    min_confidence: float = typer.Option(
        0.0, "--min-confidence", min=0.0, max=1.0, help="Minimum confidence filter."
    ),
    json: bool = typer.Option(
        False, "--json", help="Output in JSON format."
    ),
) -> None:
    """List optimization hypotheses from the Optimizer module."""
    ctx, registry = asyncio.run(_load_and_start())

    opt_mod = registry.loaded.get("optimizer")
    if opt_mod is None or _module_state(registry, "optimizer") != "RUNNING":
        typer.echo("Optimizer not available or not started.")
        raise typer.Exit(code=1)

    hyps = _try_call(ctx, "optimizer.hypotheses", [])

    # Apply filters
    filtered = [h for h in hyps if h.confidence >= min_confidence]
    filtered = filtered[:limit]

    if json:
        typer.echo(
            _json.dumps(
                [
                    {
                        "type": h.type,
                        "domain": h.domain,
                        "confidence": h.confidence,
                        "affected_scope": h.affected_scope,
                        "generated_at": h.generated_at,
                        "evidence": dict(h.evidence),
                    }
                    for h in filtered
                ],
                indent=2,
                default=str,
            )
        )
        return

    if not filtered:
        typer.echo("No hypotheses match the current filters.")
        return

    lines: list[str] = []
    lines.append("Optimization Hypotheses")
    lines.append("=" * 60)
    for h in filtered:
        htype = _HYPOTHESIS_TYPE_COLORS.get(h.type, "????")
        pct = f"{h.confidence:.0%}" if h.confidence == int(h.confidence) else f"{h.confidence:.1%}"
        lines.append(
            f"  [{htype}] {h.affected_scope:<40} {pct:>5}  {h.generated_at[:19]}"
        )
    lines.append(f"\n  {len(filtered)} of {len(hyps)} hypotheses shown (--limit {limit})")
    typer.echo("\n".join(lines))


@cli_app.command()
def recs(
    min_priority: str = typer.Option(
        "low", "--min-priority",
        help="Minimum priority: critical, high, medium, low.",
    ),
    limit: int = typer.Option(10, "--limit", help="Max recommendations to show."),
    json: bool = typer.Option(
        False, "--json", help="Output in JSON format."
    ),
) -> None:
    """List improvement recommendations from the Oracle module."""
    ctx, registry = asyncio.run(_load_and_start())

    oracle_mod = registry.loaded.get("oracle")
    if oracle_mod is None or _module_state(registry, "oracle") != "RUNNING":
        typer.echo("Oracle not available or not started.")
        raise typer.Exit(code=1)

    recs_list = _try_call(ctx, "oracle.recommendations", [])

    # Priority ordering
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    try:
        min_order = priority_order.get(min_priority, 3)
    except Exception:  # noqa: BLE001
        min_order = 3

    filtered = sorted(
        [r for r in recs_list if priority_order.get(r.priority, 3) <= min_order],
        key=lambda r: (priority_order.get(r.priority, 3), r.created_at),
    )[:limit]

    if json:
        typer.echo(
            _json.dumps(
                [
                    {
                        "id": r.id,
                        "title": r.title,
                        "priority": r.priority,
                        "domain": r.domain,
                        "confidence": r.confidence,
                        "status": r.status,
                        "created_at": r.created_at,
                    }
                    for r in filtered
                ],
                indent=2,
                default=str,
            )
        )
        return

    if not filtered:
        typer.echo("No recommendations match the current filters.")
        return

    lines: list[str] = []
    lines.append("Improvement Recommendations")
    lines.append("=" * 60)
    for r in filtered:
        pri = _PRIORITY_COLORS.get(r.priority, "????")
        pct = f"{r.confidence:.0%}" if r.confidence == int(r.confidence) else f"{r.confidence:.1%}"
        status_tag = r.status.upper() if r.status != "active" else ""
        status_str = f" [{status_tag}]" if status_tag else ""
        lines.append(f"  [{pri}] {r.title:<50} {pct:>5}{status_str}")
    lines.append(f"\n  {len(filtered)} of {len(recs_list)} recommendations shown")
    typer.echo("\n".join(lines))


@cli_app.command()
def trends(
    days: int = typer.Option(7, "--days", "-d", help="Number of days to trend."),
    json: bool = typer.Option(
        False, "--json", help="Output in JSON format."
    ),
) -> None:
    """Show productivity trends from the Pulse module.

    Requires the Pulse module to be started.
    Delegates to ``PulseModule.trend()`` for per-period aggregation.
    """
    ctx, registry = asyncio.run(_load_and_start())

    pulse_mod = registry.loaded.get("pulse")
    if pulse_mod is None or _module_state(registry, "pulse") != "RUNNING":
        typer.echo("Pulse not available or not started.")
        raise typer.Exit(code=1)

    try:
        trend_fn = getattr(pulse_mod, "trend", None)
        if trend_fn is not None:
            trend_data = trend_fn(period_days=days)
        else:
            trend_data = []
    except Exception:  # noqa: BLE001
        trend_data = []

    if json:
        typer.echo(
            _json.dumps(
                [
                    {
                        "period_start": str(t.period_start),
                        "period_end": str(t.period_end),
                        "work_unit_count": t.work_unit_count,
                        "total_cost": str(t.total_cost),
                        "total_tokens": t.total_tokens,
                    }
                    for t in trend_data
                ],
                indent=2,
                default=str,
            )
        )
        return

    if not trend_data:
        typer.echo("No trend data available.")
        return

    lines: list[str] = []
    lines.append(f"Productivity Trend (last {days} days)")
    lines.append("=" * 60)
    for t in trend_data:
        start = str(t.period_start)[:10]
        end = str(t.period_end)[:10]
        lines.append(
            f"  {start} → {end}  "
            f"{t.work_unit_count} WUs  "
            f"${t.total_cost:.2f}  "
            f"{t.total_tokens:,} tokens"
        )
    typer.echo("\n".join(lines))


# ---------------------------------------------------------------------------
# Public helpers (for CLI service descriptor)
# ---------------------------------------------------------------------------


def _service_descriptor(key: str) -> str:
    """Return a human-readable description for a known service key."""
    descriptions: dict[str, str] = {
        "pulse.measurements": "measurement queries",
        "optimizer.hypotheses": "optimization hypotheses",
        "optimizer.baselines": "baseline metrics",
        "optimizer.status": "optimizer status",
        "oracle.recommendations": "improvement recommendations",
        "oracle.status": "oracle status",
        "chronicle.record": "event recording",
    }
    return descriptions.get(key, key)
