"""Detector protocol and all six Optimizer detector implementations.

Spec: optimizer-engineering-optimization §R1–R8
Design: Optimizer — Engineering Optimization Intelligence §Detector Protocol, §Confidence Scoring
"""

from __future__ import annotations

import datetime
import math
import statistics
from typing import TYPE_CHECKING, Protocol

from apoch.modules.optimizer._confidence import cap_underpowered
from apoch.modules.optimizer.models import OptimizationHypothesis

if TYPE_CHECKING:
    from apoch.modules.pulse.models import WorkUnit

# ── Protocol ─────────────────────────────────────────────────────────


class Detector(Protocol):
    """Protocol every internal detector must satisfy.

    Detectors are pure functions — they receive WorkUnits and return
    hypotheses.  No side effects, no state mutation, no I/O.
    """

    def detect(self, units: list[WorkUnit]) -> list[OptimizationHypothesis]:
        """Analyze WorkUnits and return hypotheses."""
        ...


# ── Helpers ──────────────────────────────────────────────────────────


def _now_iso() -> str:
    """Return the current UTC timestamp as ISO 8601.

    This is the only source of non-determinism in the detector pipeline.
    """
    return datetime.datetime.now(datetime.UTC).isoformat()


def _float_or_none(val: object) -> float | None:
    """Convert a value to float, returning None for non-numeric or None."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


# ── BaselineGenerator ────────────────────────────────────────────────


class BaselineGenerator:
    """Generates descriptive statistics from WorkUnits (§R1).

    Computes mean, standard deviation, min, and max for tokens_input,
    tokens_output, cost, and wall_clock_s.  Partial data is handled per
    metric — fields with ``None`` values are skipped for that unit.
    """

    def detect(self, units: list[WorkUnit]) -> list[OptimizationHypothesis]:
        """Compute baseline statistics for the given WorkUnits.

        Returns a single ``OptimizationHypothesis`` with mean, std, min,
        max, and count for each metric.  Empty input returns an empty list.
        """
        if not units:
            return []

        metrics = ["tokens_input", "tokens_output", "cost", "wall_clock_s"]
        evidence: dict = {}

        for metric in metrics:
            values: list[float] = []
            for u in units:
                v = _float_or_none(getattr(u, metric, None))
                if v is not None:
                    values.append(v)

            if not values:
                continue

            evidence[metric] = {
                "mean": statistics.mean(values),
                "std": statistics.stdev(values) if len(values) > 1 else 0.0,
                "min": min(values),
                "max": max(values),
                "count": len(values),
            }

        if not evidence:
            return []

        # Confidence: use the metric with the most data, capped
        max_count = max(v["count"] for v in evidence.values())
        raw_conf = min(max_count / 10.0, 1.0)
        confidence = cap_underpowered(raw_conf, max_count)

        return [
            OptimizationHypothesis(
                type="pattern",
                domain="cost",
                confidence=confidence,
                evidence=evidence,
                affected_scope="all sessions — baseline metrics",
                generated_at=_now_iso(),
            )
        ]


# ── DegradationDetector ──────────────────────────────────────────────


class DegradationDetector:
    """Detects metric degradations via z-score against baseline (§R2).

    Compares each measurement against the distribution of all units.
    A z-score > threshold indicates potential degradation.
    """

    def detect(self, units: list[WorkUnit]) -> list[OptimizationHypothesis]:
        """Detect degradations by computing leave-one-out z-scores.

        Each unit is compared against a baseline derived from the
        remaining units.  A z-score above the threshold produces an
        ``OptimizationHypothesis`` with sigmoid-mapped confidence.
        """
        if not units:
            return []

        metrics = ["tokens_input", "tokens_output", "cost", "wall_clock_s"]
        n = len(units)

        # Build a per-unit leave-one-out baseline so the unit being tested
        # does not contaminate its own baseline statistics.
        hypotheses: list[OptimizationHypothesis] = []

        for i, u in enumerate(units):
            # All units except the current one
            others = [units[j] for j in range(n) if j != i]

            for metric in metrics:
                v = _float_or_none(getattr(u, metric, None))
                if v is None:
                    continue

                # Baseline from other units only
                other_values: list[float] = []
                for o in others:
                    ov = _float_or_none(getattr(o, metric, None))
                    if ov is not None:
                        other_values.append(ov)

                # Require at least 3 other measurements for a meaningful
                # z-score baseline (total n >= 4).
                if len(other_values) < 3:
                    continue

                b_mean = statistics.mean(other_values)
                b_std = statistics.stdev(other_values)
                std = max(b_std, 1e-10)
                z = (v - b_mean) / std
                threshold = 2.0

                if z > threshold:
                    # Sigmoid-mapped confidence based on z-score magnitude
                    raw = 1.0 / (1.0 + math.exp(-(z - threshold)))
                    conf = cap_underpowered(raw, n)

                    hypotheses.append(
                        OptimizationHypothesis(
                            type="anomaly",
                            domain="cost"
                            if metric in ("cost", "tokens_input", "tokens_output")
                            else "time",
                            confidence=conf,
                            evidence={
                                "metric": metric,
                                "value": v,
                                "mean": b_mean,
                                "std": b_std,
                                "z_score": z,
                                "threshold": threshold,
                                "unit_id": u.id,
                            },
                            affected_scope=(
                                f"degradation in {metric} — z-score {z:.2f} > {threshold}"
                            ),
                            generated_at=_now_iso(),
                        )
                    )

        return hypotheses


# ── ModelEfficiencyDetector ──────────────────────────────────────────


class ModelEfficiencyDetector:
    """Compares cost-per-token and time-per-unit across models (§R3).

    Groups WorkUnits by model, computes averages, and flags models that
    underperform relative to peers.
    """

    def detect(self, units: list[WorkUnit]) -> list[OptimizationHypothesis]:
        """Compare efficiency metrics (cost/token, time/unit) across models.

        When multiple models are present, produces hypotheses for both
        cost and time efficiency with ``effect_size / max_effect`` confidence.
        A single model produces no hypotheses.
        """
        if not units:
            return []

        # Group by model
        by_model: dict[str, dict] = {}
        for u in units:
            model = getattr(u, "model", None)
            if not model:
                continue

            if model not in by_model:
                by_model[model] = {
                    "cost_sum": 0.0,
                    "cost_count": 0,
                    "time_sum": 0.0,
                    "time_count": 0,
                    "total_tokens": 0,
                    "unit_count": 0,
                }

            g = by_model[model]
            g["unit_count"] += 1

            tokens = (getattr(u, "tokens_input", 0) or 0) + (getattr(u, "tokens_output", 0) or 0)
            g["total_tokens"] += tokens

            cost = _float_or_none(getattr(u, "cost", None))
            if cost is not None:
                g["cost_sum"] += cost
                g["cost_count"] += 1

            wt = _float_or_none(getattr(u, "wall_clock_s", None))
            if wt is not None:
                g["time_sum"] += wt
                g["time_count"] += 1

        if len(by_model) < 2:
            return []

        # Compute average metrics per model
        model_metrics: dict[str, dict] = {}
        for model, g in by_model.items():
            mm: dict = {"unit_count": g["unit_count"]}
            if g["cost_count"] > 0:
                mm["avg_cost_per_token"] = g["cost_sum"] / max(g["total_tokens"], 1)
                mm["cost_data_units"] = g["cost_count"]
            if g["time_count"] > 0:
                mm["avg_time_per_unit"] = g["time_sum"] / max(g["unit_count"], 1)
                mm["time_data_units"] = g["time_count"]
            model_metrics[model] = mm

        # Find best and worst for each metric
        cost_models = {
            m: d["avg_cost_per_token"]
            for m, d in model_metrics.items()
            if "avg_cost_per_token" in d
        }
        time_models = {
            m: d["avg_time_per_unit"] for m, d in model_metrics.items() if "avg_time_per_unit" in d
        }

        hypotheses: list[OptimizationHypothesis] = []

        # Cost efficiency hypothesis
        if len(cost_models) >= 2:
            min_cost = min(cost_models.values())
            max_cost = max(cost_models.values())
            spread = max_cost - min_cost
            if spread > 0:
                effect_size = spread / max(min_cost, 1e-10)
                max_effect = 5.0  # normalization ceiling
                raw_conf = min(effect_size / max_effect, 1.0)
                conf = cap_underpowered(raw_conf, len(units))

                hypotheses.append(
                    OptimizationHypothesis(
                        type="opportunity",
                        domain="model_efficiency",
                        confidence=conf,
                        evidence={
                            "comparison": "cost_per_token",
                            "models": cost_models,
                            "best_model": min(cost_models, key=cost_models.get),  # type: ignore[arg-type]
                            "worst_model": max(cost_models, key=cost_models.get),  # type: ignore[arg-type]
                            "spread": spread,
                            "partial_cost_data": any(
                                g["cost_count"] < g["unit_count"] for g in by_model.values()
                            ),
                        },
                        affected_scope=(
                            f"model cost efficiency — "
                            f"{max(cost_models, key=cost_models.get)}"
                            f" costs {max_cost:.6f}/token vs "
                            f"{min(cost_models, key=cost_models.get)}"
                            f" at {min_cost:.6f}/token"
                        ),
                        generated_at=_now_iso(),
                    )
                )

        # Time efficiency hypothesis
        if len(time_models) >= 2:
            min_time = min(time_models.values())
            max_time = max(time_models.values())
            spread = max_time - min_time
            if spread > 0:
                effect_size = spread / max(min_time, 1e-10)
                max_effect = 5.0
                raw_conf = min(effect_size / max_effect, 1.0)
                conf = cap_underpowered(raw_conf, len(units))

                hypotheses.append(
                    OptimizationHypothesis(
                        type="opportunity",
                        domain="model_efficiency",
                        confidence=conf,
                        evidence={
                            "comparison": "time_per_unit",
                            "models": time_models,
                            "best_model": min(time_models, key=time_models.get),  # type: ignore[arg-type]
                            "worst_model": max(time_models, key=time_models.get),  # type: ignore[arg-type]
                            "spread": spread,
                        },
                        affected_scope=(
                            f"model time efficiency — "
                            f"{max(time_models, key=time_models.get)}"
                            f" takes {max_time:.1f}s/unit vs "
                            f"{min(time_models, key=time_models.get)}"
                            f" at {min_time:.1f}s/unit"
                        ),
                        generated_at=_now_iso(),
                    )
                )

        return hypotheses


# ── AnomalyDetector ──────────────────────────────────────────────────


class AnomalyDetector:
    """Identifies IQR-based outliers in cost and time measurements (§R4).

    Uses the interquartile range method: values outside
    [Q1 - 1.5*IQR, Q3 + 1.5*IQR] are flagged as outliers.
    """

    def detect(self, units: list[WorkUnit]) -> list[OptimizationHypothesis]:
        """Detect outliers using the IQR method on cost and time metrics.

        For each metric with >= 3 data points, computes Q1, Q3, IQR
        and flags values outside ``[Q1 - 1.5*IQR, Q3 + 1.5*IQR]`` with
        ``1 - (distance / max_distance)`` confidence.
        """
        metrics = ["cost", "wall_clock_s"]
        hypotheses: list[OptimizationHypothesis] = []

        for metric in metrics:
            values: list[float] = []
            for u in units:
                v = _float_or_none(getattr(u, metric, None))
                if v is not None:
                    values.append(v)

            if len(values) < 3:
                continue

            sorted_vals = sorted(values)
            n = len(sorted_vals)

            # Q1, Q3 via percentile approximation
            q1 = sorted_vals[n // 4]
            q3 = sorted_vals[(3 * n) // 4]
            iqr = q3 - q1

            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr

            median = statistics.median(sorted_vals)

            for v in sorted_vals:
                if v < lower or v > upper:
                    distance = abs(v - median)
                    max_dist = max(abs(sorted_vals[0] - median), abs(sorted_vals[-1] - median))
                    raw_conf = 1.0 - (distance / max(max_dist, 1e-10))
                    conf = cap_underpowered(raw_conf, n)

                    domain = "cost" if metric == "cost" else "time"

                    hypotheses.append(
                        OptimizationHypothesis(
                            type="anomaly",
                            domain=domain,  # type: ignore[arg-type]
                            confidence=conf,
                            evidence={
                                "metric": metric,
                                "value": v,
                                "median": median,
                                "q1": q1,
                                "q3": q3,
                                "iqr": iqr,
                                "lower_fence": lower,
                                "upper_fence": upper,
                                "method": "iqr",
                            },
                            affected_scope=(
                                f"outlier in {metric}: {v:.4f} "
                                f"(IQR bounds: [{lower:.4f}, {upper:.4f}])"
                            ),
                            generated_at=_now_iso(),
                        )
                    )

        return hypotheses


# ── SessionPatternDetector ───────────────────────────────────────────


class SessionPatternDetector:
    """Detects temporal patterns via time-of-day clustering (§R5).

    Builds an hour histogram from WorkUnit timestamps and looks for
    4-hour windows where >60% of sessions are concentrated.
    """

    def detect(self, units: list[WorkUnit]) -> list[OptimizationHypothesis]:
        """Detect time-of-day clusters via sliding 4-hour window histogram.

        Returns a single hypothesis when >60% of sessions with timestamps
        fall within a 4-hour window.  Units with missing or unparseable
        ``created_at`` values are excluded.  Requires >= 3 total units.
        """
        if len(units) < 3:
            return []

        # Extract hours from created_at
        hours: list[int] = []
        for u in units:
            ts = getattr(u, "created_at", "")
            if not ts:
                continue
            try:
                dt = datetime.datetime.fromisoformat(ts)
                hours.append(dt.hour)
            except (ValueError, TypeError):
                continue

        if len(hours) < 3:
            return []

        total = len(hours)
        # Build hour histogram
        hist: dict[int, int] = {}
        for h in hours:
            hist[h] = hist.get(h, 0) + 1

        # Slide 4-hour window
        best_cluster = 0
        best_start = 0
        for start_hour in range(24):
            cluster = 0
            for h in range(start_hour, start_hour + 4):
                cluster += hist.get(h % 24, 0)
            if cluster > best_cluster:
                best_cluster = cluster
                best_start = start_hour

        ratio = best_cluster / total
        if ratio <= 0.6:
            return []

        raw_conf = ratio
        conf = cap_underpowered(raw_conf, total)

        return [
            OptimizationHypothesis(
                type="pattern",
                domain="session_behavior",
                confidence=conf,
                evidence={
                    "cluster_start_hour": best_start,
                    "cluster_end_hour": (best_start + 4) % 24,
                    "cluster_size": best_cluster,
                    "total_sessions": total,
                    "ratio": ratio,
                    "hour_histogram": dict(sorted(hist.items())),
                },
                affected_scope=(
                    f"{best_cluster}/{total} sessions ({ratio:.0%}) occur "
                    f"between {best_start:02d}:00-{(best_start + 4) % 24:02d}:00"
                ),
                generated_at=_now_iso(),
            )
        ]


# ── ReworkCorrelationDetector ────────────────────────────────────────


class ReworkCorrelationDetector:
    """Correlates rework metrics with session conditions (§R6).

    Groups by model, computes average rework per model, and flags cases
    where one model has >2x the rework of another.
    """

    def detect(self, units: list[WorkUnit]) -> list[OptimizationHypothesis]:
        """Detect rework correlations by grouping units by model.

        Returns hypotheses when one model shows >2x the average rework
        of another model.  Units without ``rework_cycles`` or
        ``rework_tokens`` attributes are excluded from analysis.
        """
        # Collect units with rework data
        rework_units: list[dict] = []
        for u in units:
            rc = getattr(u, "rework_cycles", None)
            rt = getattr(u, "rework_tokens", None)
            if rc is None and rt is None:
                continue
            rework_units.append(
                {
                    "unit": u,
                    "rework_cycles": rc or 0,
                    "rework_tokens": rt or 0,
                    "model": getattr(u, "model", None) or "",
                }
            )

        if not rework_units:
            return []

        # Group by model
        by_model: dict[str, list[int]] = {}
        for ru in rework_units:
            model = ru["model"]
            if model not in by_model:
                by_model[model] = []
            by_model[model].append(ru["rework_cycles"])

        if len(by_model) < 2:
            return []

        # Compute average rework per model
        model_avg: dict[str, float] = {}
        for model, cycles in by_model.items():
            model_avg[model] = statistics.mean(cycles)

        # Find models with >2x rework of another
        hypotheses: list[OptimizationHypothesis] = []
        models_list = sorted(model_avg.keys())

        for i, m1 in enumerate(models_list):
            for m2 in models_list[i + 1 :]:
                v1, v2 = model_avg[m1], model_avg[m2]
                if v1 == 0 and v2 == 0:
                    continue

                if v1 > 0 and v2 > 0:
                    ratio = max(v1, v2) / min(v1, v2)
                elif v1 > 0:
                    ratio = v1 / 0.5  # treat near-zero as baseline
                else:
                    ratio = v2 / 0.5

                if ratio > 2.0:
                    worse_model = m1 if v1 > v2 else m2
                    better_model = m2 if v1 > v2 else m1
                    worse_val = max(v1, v2)
                    better_val = min(v1, v2)

                    # Simple correlation coefficient proxy
                    all_cycles = [ru["rework_cycles"] for ru in rework_units]
                    all_models_num = [
                        1.0 if ru["model"] == worse_model else 0.0 for ru in rework_units
                    ]

                    # Point-biserial-like correlation
                    if len(set(all_cycles)) > 1 and len(set(all_models_num)) > 1:
                        try:
                            corr = statistics.correlation(all_models_num, all_cycles)
                        except statistics.StatisticsError:
                            corr = 0.0
                    else:
                        corr = 0.0

                    raw_conf = abs(corr) if abs(corr) > 0 else min(ratio / 10.0, 0.8)
                    conf = cap_underpowered(raw_conf, len(rework_units))

                    partial_fields = []
                    for ru in rework_units:
                        if not ru["model"]:
                            partial_fields.append("model")

                    evidence: dict = {
                        "correlation_type": "model_to_rework",
                        "correlation_coefficient": corr,
                        "worse_model": worse_model,
                        "better_model": better_model,
                        "worse_avg_rework": worse_val,
                        "better_avg_rework": better_val,
                        "ratio": ratio,
                        "total_rework_units": len(rework_units),
                    }
                    if partial_fields:
                        evidence["partial_fields"] = list(set(partial_fields))

                    hypotheses.append(
                        OptimizationHypothesis(
                            type="pattern",
                            domain="rework",
                            confidence=conf,
                            evidence=evidence,
                            affected_scope=(
                                f"model {worse_model} has {ratio:.1f}x "
                                f"more rework than {better_model}"
                            ),
                            generated_at=_now_iso(),
                        )
                    )

        return hypotheses


__all__ = [
    "AnomalyDetector",
    "BaselineGenerator",
    "DegradationDetector",
    "Detector",
    "ModelEfficiencyDetector",
    "ReworkCorrelationDetector",
    "SessionPatternDetector",
]
