"""
field_testing/metrics.py
────────────────────────
Aggregate evaluation metrics across multiple field-test sessions.

Public API
──────────
evaluate_field_results(test_results)         → Dict
compute_placement_metrics(test_results)      → Dict[str, Dict]
compute_environment_metrics(test_results)    → Dict[str, Dict]
compute_subject_metrics(test_results)        → Dict[str, Dict]
compute_confidence_interval(values, level)   → Tuple
"""

from __future__ import annotations
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from . import config as CFG


# ────────────────────────────────────────────────────────────────────
#  TOP-LEVEL EVALUATOR
# ────────────────────────────────────────────────────────────────────

def evaluate_field_results(
    test_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compute aggregate performance metrics from multiple field tests.

    Parameters
    ──────────
    test_results : list of dicts returned by ``run_field_test()``

    Returns
    ───────
    {
        "n_tests":          int,
        "overall":          { aggregated scalar metrics },
        "per_placement":    { placement → metrics },
        "per_environment":  { env_key → metrics },
        "per_subject":      { subject_id → metrics },
    }
    """
    if not test_results:
        return {"n_tests": 0, "overall": {}, "per_placement": {},
                "per_environment": {}, "per_subject": {}}

    overall = _aggregate_summaries(
        [r["summary"] for r in test_results],
    )

    return {
        "n_tests":         len(test_results),
        "overall":         overall,
        "per_placement":   compute_placement_metrics(test_results),
        "per_environment": compute_environment_metrics(test_results),
        "per_subject":     compute_subject_metrics(test_results),
    }


# ────────────────────────────────────────────────────────────────────
#  PER-PLACEMENT METRICS
# ────────────────────────────────────────────────────────────────────

def compute_placement_metrics(
    test_results: List[Dict[str, Any]],
) -> Dict[str, Dict]:
    """Group results by placement and compute per-group metrics."""
    groups: Dict[str, List[Dict]] = {}
    for r in test_results:
        pl = r.get("placement", "unknown")
        groups.setdefault(pl, []).append(r["summary"])

    return {pl: _aggregate_summaries(sums) for pl, sums in groups.items()}


# ────────────────────────────────────────────────────────────────────
#  PER-ENVIRONMENT METRICS
# ────────────────────────────────────────────────────────────────────

def compute_environment_metrics(
    test_results: List[Dict[str, Any]],
) -> Dict[str, Dict]:
    """
    Group by environment key = ``mattress / bedding``.
    """
    groups: Dict[str, List[Dict]] = {}
    for r in test_results:
        env = r.get("environment", {})
        key = f"{env.get('mattress', '?')}/{env.get('bedding', '?')}"
        groups.setdefault(key, []).append(r["summary"])

    return {k: _aggregate_summaries(sums) for k, sums in groups.items()}


# ────────────────────────────────────────────────────────────────────
#  PER-SUBJECT METRICS
# ────────────────────────────────────────────────────────────────────

def compute_subject_metrics(
    test_results: List[Dict[str, Any]],
) -> Dict[str, Dict]:
    """Group by subject_id."""
    groups: Dict[str, List[Dict]] = {}
    for r in test_results:
        sid = r.get("subject_id", "unknown")
        groups.setdefault(sid, []).append(r["summary"])

    return {sid: _aggregate_summaries(sums) for sid, sums in groups.items()}


# ────────────────────────────────────────────────────────────────────
#  CONFIDENCE INTERVAL
# ────────────────────────────────────────────────────────────────────

def compute_confidence_interval(
    values: np.ndarray | List[float],
    level: float = CFG.CI_LEVEL,
    n_bootstrap: int = CFG.BOOTSTRAP_N,
    seed: int = CFG.RANDOM_SEED,
) -> Tuple[float, float, float]:
    """
    Compute bootstrap confidence interval.

    Returns (mean, ci_lower, ci_upper).
    """
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return (0.0, 0.0, 0.0)
    if len(values) == 1:
        v = float(values[0])
        return (v, v, v)

    rng = np.random.RandomState(seed)
    means = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        sample = rng.choice(values, size=len(values), replace=True)
        means[i] = sample.mean()

    alpha = (1.0 - level) / 2
    lo = float(np.percentile(means, 100 * alpha))
    hi = float(np.percentile(means, 100 * (1 - alpha)))
    return (float(np.mean(values)), lo, hi)


# ────────────────────────────────────────────────────────────────────
#  INTERNAL HELPERS
# ────────────────────────────────────────────────────────────────────

def _aggregate_summaries(
    summaries: List[Dict],
) -> Dict[str, Any]:
    """
    Aggregate scalar metrics across multiple session summaries.

    For each metric key, compute mean, std, min, max, and 95 % CI.
    """
    if not summaries:
        return {}

    scalar_keys = [
        "rr_mae", "rr_std", "rr_drift",
        "hr_mae", "hr_std", "hr_drift",
        "dropout_rate",
        "event_acc", "event_f1",
        "stage_acc", "stage_kappa",
        "posture_acc", "motion_std",
    ]

    agg: Dict[str, Any] = {"n_sessions": len(summaries)}

    for key in scalar_keys:
        vals = [s.get(key) for s in summaries if s.get(key) is not None]
        if not vals:
            agg[key] = {"mean": None, "std": None, "min": None, "max": None}
            continue

        arr = np.array(vals, dtype=float)
        mean_val, ci_lo, ci_hi = compute_confidence_interval(arr)
        agg[key] = {
            "mean":   round(float(np.mean(arr)), 4),
            "std":    round(float(np.std(arr)), 4),
            "min":    round(float(np.min(arr)), 4),
            "max":    round(float(np.max(arr)), 4),
            "ci_low": round(ci_lo, 4),
            "ci_high": round(ci_hi, 4),
        }

    # Total epochs
    total_epochs = sum(s.get("n_epochs", 0) for s in summaries)
    total_valid  = sum(s.get("n_valid", 0)  for s in summaries)
    agg["total_epochs"] = total_epochs
    agg["total_valid"]  = total_valid

    return agg
