"""
field_testing/field_runner.py
─────────────────────────────
Orchestrate a single field test:

1.  Accept a recording (real or synthetic) + its config
2.  Compute per-epoch errors / matches
3.  Aggregate into a results dict ready for metrics evaluation

Public API
──────────
run_field_test(recording, config)   → Dict   (per-session results)
run_field_tests(recordings)         → List[Dict]
"""

from __future__ import annotations
import numpy as np
from typing import Any, Dict, List, Optional

from . import config as CFG


# ────────────────────────────────────────────────────────────────────
#  SINGLE FIELD TEST
# ────────────────────────────────────────────────────────────────────

def run_field_test(
    recording: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluate a single recording against its ground truth.

    Parameters
    ──────────
    recording : dict produced by ``synthetic_data.generate_recording``
                or loaded from a real session.  Must contain arrays:
                rr_radar, rr_truth, hr_radar, hr_truth,
                event_pred, event_truth, stage_pred, stage_truth,
                motion_index, posture_pred, posture_truth
    config    : optional test config dict (overrides recording["config"])

    Returns
    ───────
    dict with keys:
        test_id, subject_id, placement, environment,
        rr_errors, hr_errors, dropout_mask,
        event_match, stage_match, posture_match,
        summary   (dict of aggregate scalars)
    """
    if config is None:
        config = recording.get("config", {})

    rr_radar = np.asarray(recording["rr_radar"], dtype=float)
    rr_truth = np.asarray(recording["rr_truth"], dtype=float)
    hr_radar = np.asarray(recording["hr_radar"], dtype=float)
    hr_truth = np.asarray(recording["hr_truth"], dtype=float)

    event_pred  = np.asarray(recording["event_pred"], dtype=int)
    event_truth = np.asarray(recording["event_truth"], dtype=int)
    stage_pred  = np.asarray(recording["stage_pred"], dtype=int)
    stage_truth = np.asarray(recording["stage_truth"], dtype=int)
    posture_pred  = np.asarray(recording["posture_pred"], dtype=int)
    posture_truth = np.asarray(recording["posture_truth"], dtype=int)

    motion_index = np.asarray(recording.get("motion_index",
                                             np.zeros(len(rr_radar))))

    n = len(rr_radar)

    # ── Vital-sign errors (ignore dropout epochs) ──────────────────
    valid = ~(np.isnan(rr_radar) | np.isnan(hr_radar))
    dropout_mask = ~valid

    rr_err = np.full(n, np.nan)
    hr_err = np.full(n, np.nan)
    rr_err[valid] = rr_radar[valid] - rr_truth[valid]
    hr_err[valid] = hr_radar[valid] - hr_truth[valid]

    rr_abs = np.abs(rr_err[valid]) if valid.sum() > 0 else np.array([])
    hr_abs = np.abs(hr_err[valid]) if valid.sum() > 0 else np.array([])

    rr_mae = float(np.mean(rr_abs)) if len(rr_abs) > 0 else np.nan
    hr_mae = float(np.mean(hr_abs)) if len(hr_abs) > 0 else np.nan
    rr_std = float(np.std(rr_abs))  if len(rr_abs) > 0 else np.nan
    hr_std = float(np.std(hr_abs))  if len(hr_abs) > 0 else np.nan

    dropout_rate = float(dropout_mask.sum() / n) if n > 0 else 0.0

    # ── Classification matches ─────────────────────────────────────
    event_match  = (event_pred == event_truth)
    stage_match  = (stage_pred == stage_truth)
    posture_match = (posture_pred == posture_truth)

    event_acc   = float(event_match.mean()) if n > 0 else 0.0
    stage_acc   = float(stage_match.mean()) if n > 0 else 0.0
    posture_acc = float(posture_match.mean()) if n > 0 else 0.0

    # ── Event F1 (binary) ─────────────────────────────────────────
    event_f1 = _binary_f1(event_truth, event_pred)

    # ── Stage Cohen's kappa ────────────────────────────────────────
    stage_kappa = _cohens_kappa(stage_truth, stage_pred, n_classes=4)

    # ── RR / HR drift (slope of error over time) ──────────────────
    rr_drift = _linear_drift(rr_err, valid)
    hr_drift = _linear_drift(hr_err, valid)

    # ── Motion stability (std of motion index) ────────────────────
    motion_std = float(np.std(motion_index)) if len(motion_index) > 0 else 0.0

    summary = {
        "rr_mae":        round(rr_mae, 4) if not np.isnan(rr_mae) else None,
        "rr_std":        round(rr_std, 4) if not np.isnan(rr_std) else None,
        "rr_drift":      round(rr_drift, 6),
        "hr_mae":        round(hr_mae, 4) if not np.isnan(hr_mae) else None,
        "hr_std":        round(hr_std, 4) if not np.isnan(hr_std) else None,
        "hr_drift":      round(hr_drift, 6),
        "dropout_rate":  round(dropout_rate, 4),
        "event_acc":     round(event_acc, 4),
        "event_f1":      round(event_f1, 4),
        "stage_acc":     round(stage_acc, 4),
        "stage_kappa":   round(stage_kappa, 4),
        "posture_acc":   round(posture_acc, 4),
        "motion_std":    round(motion_std, 4),
        "n_epochs":      int(n),
        "n_valid":       int(valid.sum()),
    }

    return {
        "test_id":        config.get("test_id", recording.get("test_id", "")),
        "subject_id":     config.get("subject_id",
                                     recording.get("subject_id", "")),
        "placement":      config.get("placement", "unknown"),
        "environment": {
            "mattress":    config.get("mattress", "unknown"),
            "bedding":     config.get("bedding", "unknown"),
            "occlusions":  config.get("occlusions", []),
            "room_size":   config.get("room_size", "unknown"),
        },
        "rr_errors":      rr_err,
        "hr_errors":      hr_err,
        "dropout_mask":   dropout_mask,
        "event_match":    event_match,
        "stage_match":    stage_match,
        "posture_match":  posture_match,
        "summary":        summary,
    }


# ────────────────────────────────────────────────────────────────────
#  BATCH RUNNER
# ────────────────────────────────────────────────────────────────────

def run_field_tests(
    recordings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Run ``run_field_test`` on every recording, return list of results."""
    return [run_field_test(r) for r in recordings]


# ────────────────────────────────────────────────────────────────────
#  INTERNAL HELPERS
# ────────────────────────────────────────────────────────────────────

def _binary_f1(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Compute F1 for binary classification (positive class = 1)."""
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    if tp == 0:
        return 0.0
    precision = tp / (tp + fp)
    recall    = tp / (tp + fn)
    return 2 * precision * recall / (precision + recall)


def _cohens_kappa(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n_classes: int = 4,
) -> float:
    """Compute Cohen's kappa for multi-class agreement."""
    n = len(y_true)
    if n == 0:
        return 0.0

    # Confusion matrix
    cm = np.zeros((n_classes, n_classes), dtype=int)
    for t, p in zip(y_true, y_pred):
        if 0 <= t < n_classes and 0 <= p < n_classes:
            cm[int(t), int(p)] += 1

    p_o = np.trace(cm) / n  # observed agreement
    row_sums = cm.sum(axis=1)
    col_sums = cm.sum(axis=0)
    p_e = (row_sums * col_sums).sum() / (n * n)  # expected agreement

    if p_e >= 1.0:
        return 1.0 if p_o >= 1.0 else 0.0
    return float((p_o - p_e) / (1.0 - p_e))


def _linear_drift(
    errors: np.ndarray,
    valid: np.ndarray,
) -> float:
    """Fit linear slope to error time-series (drift per epoch)."""
    idx = np.where(valid)[0]
    if len(idx) < 3:
        return 0.0
    vals = errors[idx]
    t = idx.astype(float)
    t_mean = t.mean()
    v_mean = vals.mean()
    denom = ((t - t_mean) ** 2).sum()
    if denom == 0:
        return 0.0
    slope = ((t - t_mean) * (vals - v_mean)).sum() / denom
    return float(slope)
