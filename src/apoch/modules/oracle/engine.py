"""Pure RecommendationEngine — maps hypotheses to recommendations.

Constraint A (zero side effects):
  The engine MUST NOT know about context, Chronicle, or any service.
  Its interface is pure: ``generate(hypotheses, health=None) -> list[Recommendation]``
  No I/O, no service discovery, no state mutation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from apoch.modules.optimizer.models import OptimizationHypothesis
from apoch.modules.oracle.models import Recommendation, RecommendationPriority

# ---------------------------------------------------------------------------
# Priority ordinal for sorting (critical=0 … low=3)
# ---------------------------------------------------------------------------

PRIORITY_ORDER: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}

# ---------------------------------------------------------------------------
# Priority mapping table
# (domain, hyp_type) -> (base_priority, base_confidence)
# ---------------------------------------------------------------------------

_PRIORITY_MAP: dict[tuple[str, str], tuple[str, float]] = {
    ("cost", "anomaly"): ("critical", 0.9),
    ("rework", "anomaly"): ("high", 0.85),
    ("cost", "pattern"): ("high", 0.8),
    ("rework", "pattern"): ("medium", 0.7),
    ("model_efficiency", "pattern"): ("medium", 0.75),
    ("model_efficiency", "opportunity"): ("medium", 0.7),
    ("session_behavior", "pattern"): ("low", 0.6),
    ("session_behavior", "anomaly"): ("low", 0.55),
    # time domain from design table
    ("time", "anomaly"): ("high", 0.85),
    ("time", "pattern"): ("medium", 0.7),
    ("time", "opportunity"): ("medium", 0.7),
}

_DEFAULT_MAPPING = ("low", 0.5)

# Domains eligible for the priority bonus (one tier up when hyp.confidence >= 0.9)
_BONUS_DOMAINS = {"cost", "time", "rework"}

_PRIORITY_TIERS: list[str] = ["critical", "high", "medium", "low"]

# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

_DOMAIN_LABELS: dict[str, str] = {
    "cost": "Cost",
    "time": "Time",
    "rework": "Rework",
    "model_efficiency": "Model Efficiency",
    "session_behavior": "Session Behavior",
    "general": "General",
}

_TYPE_LABELS: dict[str, str] = {
    "anomaly": "Anomaly",
    "pattern": "Pattern",
    "opportunity": "Opportunity",
    "degradation": "Degradation",
}

# Default TTLs per priority level (in minutes)
_DEFAULT_TTLS: dict[str, int] = {
    "critical": 60,
    "high": 240,
    "medium": 480,
    "low": 1440,
}


# ---------------------------------------------------------------------------
# Mockable clock (for testability — datetime.datetime is immutable in C)
# ---------------------------------------------------------------------------


def _utc_now() -> datetime:
    """Return the current UTC wall-clock time as a timezone-aware datetime."""
    return datetime.now(UTC)


def _domain_label(domain: str) -> str:
    return _DOMAIN_LABELS.get(domain, domain.capitalize())


def _type_label(type_val: str) -> str:
    return _TYPE_LABELS.get(type_val, type_val.capitalize())


def _bump_priority(priority: str) -> str:
    """Bump priority one tier up (e.g. low -> medium). Critical stays critical."""
    idx = PRIORITY_ORDER.get(priority, 3)
    if idx == 0:
        return priority
    return _PRIORITY_TIERS[idx - 1]


def _make_rec_id(hyp: OptimizationHypothesis) -> str:
    """Deterministic recommendation ID from hypothesis content."""
    key = f"apoch/oracle/{hyp.type}/{hyp.domain}/{hyp.generated_at}/{hyp.confidence}"
    return uuid.uuid5(uuid.NAMESPACE_DNS, key).hex


def _make_title(hyp: OptimizationHypothesis) -> str:
    label = _domain_label(hyp.domain)
    if hyp.type == "anomaly":
        return f"{label} anomaly detected"
    if hyp.type == "pattern":
        return f"{label} pattern identified"
    if hyp.type == "opportunity":
        return f"{label} optimization opportunity"
    return f"{label} {_type_label(hyp.type)}"


def _make_description(hyp: OptimizationHypothesis) -> str:
    label = _domain_label(hyp.domain)
    conf_pct = f"{hyp.confidence:.0%}"
    if hyp.type == "anomaly":
        return f"Detected anomaly in {label} with {conf_pct} confidence."
    if hyp.type == "pattern":
        return f"Identified pattern in {label} with {conf_pct} confidence."
    if hyp.type == "opportunity":
        return f"Found optimization opportunity in {label} with {conf_pct} confidence."
    return f"{label} finding with {conf_pct} confidence."


def _make_justification(hyp: OptimizationHypothesis) -> str:
    return (
        f"Based on {_type_label(hyp.type)} analysis in {_domain_label(hyp.domain)} "
        f"domain with {hyp.confidence:.0%} confidence. "
        f"Scope: {hyp.affected_scope}."
    )


# ---------------------------------------------------------------------------
# RecommendationEngine
# ---------------------------------------------------------------------------


class RecommendationEngine:
    """Pure engine that maps hypotheses to sorted, validated recommendations.

    Zero side effects (Constraint A):
    - No I/O
    - No service discovery
    - No state mutation
    - No knowledge of context, Chronicle, Guardian, or Vision
    """

    def __init__(self, domain_ttls: dict[str, int] | None = None) -> None:
        """Initialise the engine with optional custom TTLs (per priority level).

        Args:
            domain_ttls: TTL in minutes per priority level. Keys are priority
                names (critical/high/medium/low). Falls back to defaults when
                a level is missing.
        """
        self._ttls: dict[str, int] = _DEFAULT_TTLS.copy()
        if domain_ttls:
            self._ttls.update(domain_ttls)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        hypotheses: list[OptimizationHypothesis] | None,
        health: dict[str, Any] | None = None,
    ) -> list[Recommendation]:
        """Map hypotheses -> recommendations, apply rules, and sort.

        Pure function: same input always produces the same output
        (modulo ``id`` and ``created_at`` which are time-dependent per R10).

        Args:
            hypotheses: List of ``OptimizationHypothesis`` from the Optimizer.
            health: Optional dict of failing module diagnostics (from Guardian).
                ``None`` or ``{}`` means no degradation.

        Returns:
            Sorted list of ``Recommendation`` instances.
        """
        if not hypotheses:
            return []

        now = _utc_now()
        recs: list[Recommendation] = []

        for hyp in hypotheses:
            base_priority, base_confidence = self._lookup_priority(hyp)
            final_priority = self._apply_bonus(base_priority, hyp)
            rec = self._build_rec(hyp, final_priority, base_confidence, now)
            recs.append(rec)

        # Apply expiration (on-read check)
        recs = [self._apply_expiration(r, now) for r in recs]

        # Apply health degradation
        if health:
            recs = [self._apply_health(r, health) for r in recs]

        # Deterministic sort
        recs.sort(key=self._sort_key)
        return recs

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _lookup_priority(
        hyp: OptimizationHypothesis,
    ) -> tuple[RecommendationPriority, float]:
        """Look up base priority and confidence from the mapping table.

        Falls back to ``(low, 0.5)`` for unknown (domain, type) pairs.
        """
        key = (hyp.domain, hyp.type)
        result = _PRIORITY_MAP.get(key)
        if result is not None:
            return result  # type: ignore[return-value]
        return _DEFAULT_MAPPING  # type: ignore[return-value]

    @staticmethod
    def _apply_bonus(
        priority: str,
        hyp: OptimizationHypothesis,
    ) -> RecommendationPriority:
        """Bump priority one tier if confidence >= 0.9 and domain qualifies."""
        if hyp.confidence >= 0.9 and hyp.domain in _BONUS_DOMAINS:
            return _bump_priority(priority)  # type: ignore[return-value]
        return priority  # type: ignore[return-value]

    @staticmethod
    def _apply_expiration(rec: Recommendation, now: datetime) -> Recommendation:
        """Check expiration and set status to 'expired' if past TTL."""
        expire_dt = datetime.fromisoformat(rec.expiration)
        if expire_dt >= now:
            return rec  # still active
        # Return new rec with updated status
        return Recommendation(
            id=rec.id,
            title=rec.title,
            description=rec.description,
            priority=rec.priority,
            confidence=rec.confidence,
            evidence=rec.evidence,
            justification=rec.justification,
            dependencies=rec.dependencies,
            expiration=rec.expiration,
            source_hypotheses=rec.source_hypotheses,
            domain=rec.domain,
            status="expired",
            created_at=rec.created_at,
        )

    @staticmethod
    def _apply_health(
        rec: Recommendation,
        health: dict[str, Any],
    ) -> Recommendation:
        """Degrade confidence for each failing module and annotate evidence."""
        if not health:
            return rec

        confidence = rec.confidence
        evidence = dict(rec.evidence)  # mutable copy
        degradation_notes: list[str] = []

        for module_name, diag in health.items():
            if not isinstance(diag, dict):
                continue
            diagnostic = diag.get("diagnostic", str(diag))
            # Degrade confidence by 0.9x for each failing module
            confidence *= 0.9
            degradation_notes.append(
                f"confidence degraded due to {module_name} health: {diagnostic}",
            )

        if degradation_notes:
            evidence["health_degradation"] = degradation_notes

        return Recommendation(
            id=rec.id,
            title=rec.title,
            description=rec.description,
            priority=rec.priority,
            confidence=confidence,
            evidence=evidence,
            justification=rec.justification,
            dependencies=rec.dependencies,
            expiration=rec.expiration,
            source_hypotheses=rec.source_hypotheses,
            domain=rec.domain,
            status=rec.status,
            created_at=rec.created_at,
        )

    def _build_rec(
        self,
        hyp: OptimizationHypothesis,
        priority: RecommendationPriority,
        confidence: float,
        now: datetime,  # noqa: ARG002 — unused, but kept for stable signature
    ) -> Recommendation:
        """Construct a Recommendation from a single hypothesis.

        ``created_at`` is set from the hypothesis ``generated_at`` so that
        TTL-based expiration is meaningful: a rec whose hypothesis was
        generated more than ``TTL`` minutes ago will be marked expired
        on read.
        """
        created_dt = datetime.fromisoformat(hyp.generated_at)
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=UTC)

        ttl = self._ttls.get(priority, 1440)
        expiration_dt = created_dt + timedelta(minutes=ttl)

        return Recommendation(
            id=_make_rec_id(hyp),
            title=_make_title(hyp),
            description=_make_description(hyp),
            priority=priority,
            confidence=confidence,
            evidence=dict(hyp.evidence),
            justification=_make_justification(hyp),
            dependencies=["pulse.measurements"],
            expiration=expiration_dt.isoformat(),
            source_hypotheses=[],
            domain=hyp.domain,  # type: ignore[arg-type]
            status="active",
            created_at=hyp.generated_at,
        )

    @staticmethod
    def _sort_key(rec: Recommendation) -> tuple[int, float, str, str]:
        """Sort key: priority ordinal -> -confidence -> created_at -> id."""
        return (
            PRIORITY_ORDER.get(rec.priority, 99),
            -rec.confidence,
            rec.created_at,
            rec.id,
        )


__all__ = [
    "PRIORITY_ORDER",
    "RecommendationEngine",
    "_utc_now",
]
