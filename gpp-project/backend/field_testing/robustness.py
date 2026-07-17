"""
field_testing/robustness.py
───────────────────────────
Quantitative robustness scoring system.

Scoring tiers for each metric:
    Excellent  → 1.0
    Good       → 0.75
    Acceptable → 0.50
    Poor       → 0.25
    Failing    → 0.0

Public API
──────────
score_single_result(summary)                → Dict   (per-metric scores)
score_placement(placement_metrics)          → float  (0-1)
score_environment(env_metrics)              → float  (0-1)
aggregate_robustness(field_evaluation)      → Dict   (full breakdown)
classify_tier(score)                        → str
"""

from __future__ import annotations
import numpy as np
from typing import Any, Dict, List, Optional

from . import config as CFG


# ────────────────────────────────────────────────────────────────────
#  TIER CLASSIFICATION
# ────────────────────────────────────────────────────────────────────

def classify_tier(score: float) -> str:
    """Map a 0-1 score to a tier label."""
    if score >= 0.875:
        return "Excellent"
    if score >= 0.625:
        return "Good"
    if score >= 0.375:
        return "Acceptable"
    if score >= 0.125:
        return "Poor"
    return "Failing"


# ────────────────────────────────────────────────────────────────────
#  METRIC → SCORE MAPPERS
# ────────────────────────────────────────────────────────────────────

def _rr_score(mae: Optional[float]) -> float:
    """Map RR MAE to a 0-1 score."""
    if mae is None:
        return 0.0
    if mae <= CFG.RR_MAE_EXCELLENT:
        return 1.0
    if mae <= CFG.RR_MAE_GOOD:
        return 0.75
    if mae <= CFG.RR_MAE_ACCEPTABLE:
        return 0.50
    if mae <= CFG.RR_MAE_POOR:
        return 0.25
    return 0.0


def _hr_score(mae: Optional[float]) -> float:
    if mae is None:
        return 0.0
    if mae <= CFG.HR_MAE_EXCELLENT:
        return 1.0
    if mae <= CFG.HR_MAE_GOOD:
        return 0.75
    if mae <= CFG.HR_MAE_ACCEPTABLE:
        return 0.50
    if mae <= CFG.HR_MAE_POOR:
        return 0.25
    return 0.0


def _event_score(f1: Optional[float]) -> float:
    if f1 is None:
        return 0.0
    if f1 >= CFG.EVENT_F1_EXCELLENT:
        return 1.0
    if f1 >= CFG.EVENT_F1_GOOD:
        return 0.75
    if f1 >= CFG.EVENT_F1_ACCEPTABLE:
        return 0.50
    if f1 >= CFG.EVENT_F1_POOR:
        return 0.25
    return 0.0


def _stage_score(kappa: Optional[float]) -> float:
    if kappa is None:
        return 0.0
    if kappa >= CFG.STAGE_KAPPA_EXCELLENT:
        return 1.0
    if kappa >= CFG.STAGE_KAPPA_GOOD:
        return 0.75
    if kappa >= CFG.STAGE_KAPPA_ACCEPTABLE:
        return 0.50
    if kappa >= CFG.STAGE_KAPPA_POOR:
        return 0.25
    return 0.0


def _motion_score(acc: Optional[float]) -> float:
    if acc is None:
        return 0.0
    if acc >= CFG.MOTION_ACC_EXCELLENT:
        return 1.0
    if acc >= CFG.MOTION_ACC_GOOD:
        return 0.75
    if acc >= CFG.MOTION_ACC_ACCEPTABLE:
        return 0.50
    if acc >= CFG.MOTION_ACC_POOR:
        return 0.25
    return 0.0


# ────────────────────────────────────────────────────────────────────
#  SCORE A SINGLE SESSION
# ────────────────────────────────────────────────────────────────────

def score_single_result(summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute per-metric robustness scores for one test session.

    Parameters
    ──────────
    summary : the ``"summary"`` dict from ``run_field_test()``

    Returns dict with per-metric scores and weighted aggregate.
    """
    scores = {
        "rr_score":     _rr_score(summary.get("rr_mae")),
        "hr_score":     _hr_score(summary.get("hr_mae")),
        "event_score":  _event_score(summary.get("event_f1")),
        "stage_score":  _stage_score(summary.get("stage_kappa")),
        "motion_score": _motion_score(summary.get("posture_acc")),
    }

    weighted = sum(scores[k] * CFG.METRIC_WEIGHTS[k]
                   for k in CFG.METRIC_WEIGHTS)
    scores["aggregate"] = round(weighted, 4)
    scores["tier"] = classify_tier(weighted)

    return scores


# ────────────────────────────────────────────────────────────────────
#  SCORE A GROUP (placement / environment)
# ────────────────────────────────────────────────────────────────────

def _score_group_metrics(group_agg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score aggregate metrics for a group of sessions.

    Parameters
    ──────────
    group_agg : dict from ``_aggregate_summaries()`` with nested
                ``{ "mean": ..., "std": ... }`` per metric.
    """
    def _mean(key):
        v = group_agg.get(key, {})
        return v.get("mean") if isinstance(v, dict) else v

    scores = {
        "rr_score":     _rr_score(_mean("rr_mae")),
        "hr_score":     _hr_score(_mean("hr_mae")),
        "event_score":  _event_score(_mean("event_f1")),
        "stage_score":  _stage_score(_mean("stage_kappa")),
        "motion_score": _motion_score(_mean("posture_acc")),
    }

    weighted = sum(scores[k] * CFG.METRIC_WEIGHTS[k]
                   for k in CFG.METRIC_WEIGHTS)
    scores["aggregate"] = round(weighted, 4)
    scores["tier"] = classify_tier(weighted)
    scores["n_sessions"] = group_agg.get("n_sessions", 0)

    return scores


def score_placement(
    placement_metrics: Dict[str, Dict],
) -> Dict[str, Dict]:
    """Score each placement group.  Returns {placement → scores}."""
    return {pl: _score_group_metrics(agg)
            for pl, agg in placement_metrics.items()}


def score_environment(
    env_metrics: Dict[str, Dict],
) -> Dict[str, Dict]:
    """Score each environment group.  Returns {env_key → scores}."""
    return {ek: _score_group_metrics(agg)
            for ek, agg in env_metrics.items()}


# ────────────────────────────────────────────────────────────────────
#  FULL ROBUSTNESS AGGREGATION
# ────────────────────────────────────────────────────────────────────

def aggregate_robustness(
    field_evaluation: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Produce the final robustness report from an ``evaluate_field_results``
    output.

    Returns
    ───────
    {
        "overall_score":       float  (0-1),
        "overall_tier":        str,
        "per_placement":       { placement → scores },
        "per_environment":     { env_key → scores },
        "best_placement":      str,
        "worst_placement":     str,
        "best_environment":    str,
        "worst_environment":   str,
        "n_tests":             int,
    }
    """
    overall_agg = field_evaluation.get("overall", {})
    overall_scores = _score_group_metrics(overall_agg)

    pl_scores = score_placement(
        field_evaluation.get("per_placement", {}),
    )
    env_scores = score_environment(
        field_evaluation.get("per_environment", {}),
    )

    best_pl  = _best_key(pl_scores)
    worst_pl = _worst_key(pl_scores)
    best_env  = _best_key(env_scores)
    worst_env = _worst_key(env_scores)

    return {
        "overall_score":     overall_scores["aggregate"],
        "overall_tier":      overall_scores["tier"],
        "overall_detail":    overall_scores,
        "per_placement":     pl_scores,
        "per_environment":   env_scores,
        "best_placement":    best_pl,
        "worst_placement":   worst_pl,
        "best_environment":  best_env,
        "worst_environment": worst_env,
        "n_tests":           field_evaluation.get("n_tests", 0),
    }


# ────────────────────────────────────────────────────────────────────
#  HELPERS
# ────────────────────────────────────────────────────────────────────

def _best_key(scores: Dict[str, Dict]) -> Optional[str]:
    if not scores:
        return None
    return max(scores, key=lambda k: scores[k].get("aggregate", 0))


def _worst_key(scores: Dict[str, Dict]) -> Optional[str]:
    if not scores:
        return None
    return min(scores, key=lambda k: scores[k].get("aggregate", 0))
