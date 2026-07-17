"""
validation/threshold_optimization.py
────────────────────────────────────
ROC-based and grid-search threshold optimization for:

• AHI cutoff selection (maximize sensitivity at acceptable specificity)
• Event detection confidence threshold tuning
• Optimal operating-point selection (Youden's J)
"""

from __future__ import annotations
import numpy as np
from typing import Dict, List, Optional, Tuple

from . import config as CFG
from .ahi import classify_ahi_severity


# ────────────────────────────────────────────────────────────────────
#  ROC CURVE FOR AHI SCREENING
# ────────────────────────────────────────────────────────────────────

def ahi_roc_curve(
    subjects: List[Dict],
    psg_cutoff: float = CFG.DEFAULT_SCREENING_CUTOFF,
    n_thresholds: int = 200,
) -> Dict:
    """
    Build an ROC curve for AHI-based OSA screening.

    The reference binary label is PSG AHI ≥ psg_cutoff.
    The system score is the system AHI value.
    We sweep thresholds over the range of system AHI values.

    Parameters
    ──────────
    subjects      : list of dicts with "system_ahi" and "psg_ahi"
    psg_cutoff    : PSG AHI cutoff for positive label
    n_thresholds  : number of threshold values to sweep

    Returns
    ───────
    dict with:
        thresholds : list of threshold values
        tpr        : true-positive rate at each threshold
        fpr        : false-positive rate at each threshold
        best_threshold : threshold maximising Youden's J
        best_sensitivity, best_specificity : at optimal point
        auc        : area under the ROC curve
    """
    sys_ahi = np.array([s["system_ahi"] for s in subjects], dtype=float)
    ref_pos = np.array([s["psg_ahi"] >= psg_cutoff for s in subjects], dtype=bool)

    n_pos = ref_pos.sum()
    n_neg = len(ref_pos) - n_pos

    if n_pos == 0 or n_neg == 0:
        return {
            "thresholds": [], "tpr": [], "fpr": [],
            "best_threshold": psg_cutoff,
            "best_sensitivity": 0.0, "best_specificity": 0.0,
            "auc": 0.0,
            "note": "All subjects belong to one class — ROC not meaningful",
        }

    lo = float(np.min(sys_ahi)) - 1
    hi = float(np.max(sys_ahi)) + 1
    thresholds = np.linspace(lo, hi, n_thresholds)

    tpr_list: List[float] = []
    fpr_list: List[float] = []

    for t in thresholds:
        pred_pos = sys_ahi >= t
        tp = np.sum(pred_pos & ref_pos)
        fp = np.sum(pred_pos & ~ref_pos)
        fn = np.sum(~pred_pos & ref_pos)
        tn = np.sum(~pred_pos & ~ref_pos)

        tpr_list.append(float(tp / max(tp + fn, 1)))
        fpr_list.append(float(fp / max(fp + tn, 1)))

    tpr_arr = np.array(tpr_list)
    fpr_arr = np.array(fpr_list)

    # AUC (trapezoidal)
    sorted_idx = np.argsort(fpr_arr)
    auc = float(np.abs(np.trapezoid(tpr_arr[sorted_idx], fpr_arr[sorted_idx])))

    # Youden's J = sensitivity + specificity − 1
    youdens_j = tpr_arr - fpr_arr
    best_idx  = int(np.argmax(youdens_j))

    return {
        "thresholds":       thresholds.tolist(),
        "tpr":              tpr_arr.tolist(),
        "fpr":              fpr_arr.tolist(),
        "best_threshold":   round(float(thresholds[best_idx]), 2),
        "best_sensitivity": round(float(tpr_arr[best_idx]), 4),
        "best_specificity": round(float(1 - fpr_arr[best_idx]), 4),
        "youdens_j":        round(float(youdens_j[best_idx]), 4),
        "auc":              round(auc, 4),
        "psg_cutoff":       psg_cutoff,
    }


# ────────────────────────────────────────────────────────────────────
#  GRID SEARCH FOR EVENT CONFIDENCE THRESHOLD
# ────────────────────────────────────────────────────────────────────

def optimize_event_confidence_threshold(
    ref_events: List[Dict],
    pred_events_with_scores: List[Dict],
    score_key: str = "confidence",
    n_thresholds: int = 50,
) -> Dict:
    """
    Find the optimal confidence threshold for event detection that
    maximises F1-score.

    Parameters
    ──────────
    ref_events                : ground-truth events
    pred_events_with_scores   : predicted events with a score field
    score_key                 : key name for the confidence score
    n_thresholds              : number of thresholds to try

    Returns
    ───────
    dict with:
        best_threshold, best_f1, best_precision, best_recall,
        threshold_curve (list of {threshold, f1, precision, recall})
    """
    from .event_metrics import compute_event_metrics

    scores = [e.get(score_key, 0.5) for e in pred_events_with_scores]
    if not scores:
        return {
            "best_threshold": 0.5, "best_f1": 0.0,
            "best_precision": 0.0, "best_recall": 0.0,
            "threshold_curve": [],
        }

    lo = min(scores) - 0.01
    hi = max(scores) + 0.01
    thresholds = np.linspace(lo, hi, n_thresholds)

    curve: List[Dict] = []
    best_f1 = -1.0
    best_entry: Dict = {}

    for t in thresholds:
        filtered = [e for e in pred_events_with_scores if e.get(score_key, 0) >= t]
        m = compute_event_metrics(ref_events, filtered)
        entry = {
            "threshold":  round(float(t), 4),
            "f1":         m["f1"],
            "precision":  m["precision"],
            "recall":     m["recall"],
            "tp": m["tp"], "fp": m["fp"], "fn": m["fn"],
        }
        curve.append(entry)
        if m["f1"] > best_f1:
            best_f1 = m["f1"]
            best_entry = entry

    return {
        "best_threshold": best_entry.get("threshold", 0.5),
        "best_f1":        best_entry.get("f1", 0.0),
        "best_precision": best_entry.get("precision", 0.0),
        "best_recall":    best_entry.get("recall", 0.0),
        "threshold_curve": curve,
    }


# ────────────────────────────────────────────────────────────────────
#  MULTI-CUTOFF SCREENING TABLE
# ────────────────────────────────────────────────────────────────────

def multi_cutoff_screening(
    subjects: List[Dict],
    cutoffs: Optional[List[float]] = None,
) -> List[Dict]:
    """
    Compute sensitivity/specificity at multiple clinical AHI cutoffs.

    Default cutoffs: 5, 15, 30 (Normal/Mild/Moderate/Severe boundaries).

    Returns list of dicts, one per cutoff.
    """
    from .ahi import screening_performance

    if cutoffs is None:
        cutoffs = CFG.CLINICAL_AHI_CUTOFFS

    return [screening_performance(subjects, c) for c in cutoffs]
