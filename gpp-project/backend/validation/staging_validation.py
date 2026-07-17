"""
validation/staging_validation.py
────────────────────────────────
Validate system-predicted sleep stages against PSG-annotated stages.

Produces:
• Per-epoch accuracy
• Confusion matrix
• Cohen's Kappa
• Per-stage precision / recall / F1
• Stage transition agreement
"""

from __future__ import annotations
import numpy as np
from typing import Dict, List, Optional

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix as sk_confusion_matrix,
    cohen_kappa_score,
)

from . import config as CFG
from .agreement import build_confusion_matrix, cohens_kappa


# ────────────────────────────────────────────────────────────────────
#  STAGE-LEVEL VALIDATION
# ────────────────────────────────────────────────────────────────────

def validate_stages(
    ref_stages: List[str],
    pred_stages: List[str],
    labels: Optional[List[str]] = None,
) -> Dict:
    """
    Full validation of predicted sleep stages vs. reference.

    Parameters
    ──────────
    ref_stages   : ground-truth stage per epoch
    pred_stages  : system-predicted stage per epoch
    labels       : ordered label list (default: inferred)

    Returns
    ───────
    dict with:
        accuracy, kappa,
        precision_macro, recall_macro, f1_macro,
        per_class (precision, recall, f1 per stage),
        confusion_matrix (labels + matrix),
        classification_report (sklearn-format dict),
        n_epochs
    """
    n = min(len(ref_stages), len(pred_stages))
    ref  = ref_stages[:n]
    pred = pred_stages[:n]

    if labels is None:
        labels = sorted(set(ref) | set(pred))

    # Numeric encoding
    lbl_idx = {lbl: i for i, lbl in enumerate(labels)}
    y_true = np.array([lbl_idx.get(s, -1) for s in ref])
    y_pred = np.array([lbl_idx.get(s, -1) for s in pred])

    # Filter out unknown
    mask = (y_true >= 0) & (y_pred >= 0)
    y_true = y_true[mask]
    y_pred = y_pred[mask]

    if len(y_true) == 0:
        return _empty_result(labels)

    acc   = float(accuracy_score(y_true, y_pred))
    kappa = float(cohen_kappa_score(y_true, y_pred))
    prec  = float(precision_score(y_true, y_pred, average="macro", zero_division=0))
    rec   = float(recall_score(y_true, y_pred, average="macro", zero_division=0))
    f1    = float(f1_score(y_true, y_pred, average="macro", zero_division=0))

    # Per-class
    present = sorted(set(np.concatenate([y_true, y_pred])))
    report = classification_report(
        y_true, y_pred,
        labels=present,
        target_names=[labels[i] for i in present],
        output_dict=True,
        zero_division=0,
    )

    per_class: Dict[str, Dict] = {}
    for i in present:
        name = labels[i]
        per_class[name] = {
            "precision": round(report.get(name, {}).get("precision", 0), 4),
            "recall":    round(report.get(name, {}).get("recall", 0), 4),
            "f1":        round(report.get(name, {}).get("f1-score", 0), 4),
            "support":   int(report.get(name, {}).get("support", 0)),
        }

    cm = sk_confusion_matrix(y_true, y_pred, labels=list(range(len(labels))))

    return {
        "accuracy":          round(acc, 4),
        "cohens_kappa":      round(kappa, 4),
        "precision_macro":   round(prec, 4),
        "recall_macro":      round(rec, 4),
        "f1_macro":          round(f1, 4),
        "per_class":         per_class,
        "confusion_matrix":  {
            "labels": labels,
            "matrix": cm.tolist(),
        },
        "classification_report": report,
        "n_epochs":          int(len(y_true)),
    }


# ────────────────────────────────────────────────────────────────────
#  STAGE TRANSITION AGREEMENT
# ────────────────────────────────────────────────────────────────────

def stage_transition_agreement(
    ref_stages: List[str],
    pred_stages: List[str],
) -> Dict:
    """
    Compare the number and pattern of stage transitions.

    A transition occurs when consecutive epochs have different labels.

    Returns
    ───────
    dict with:
        ref_transitions, pred_transitions,
        transition_count_error,
        transition_match_rate (ratio of matching transitions)
    """
    n = min(len(ref_stages), len(pred_stages))

    ref_trans  = 0
    pred_trans = 0
    both_trans = 0

    for i in range(1, n):
        r_changed = ref_stages[i] != ref_stages[i - 1]
        p_changed = pred_stages[i] != pred_stages[i - 1]
        if r_changed:
            ref_trans += 1
        if p_changed:
            pred_trans += 1
        if r_changed and p_changed:
            both_trans += 1

    match_rate = both_trans / max(ref_trans, 1)

    return {
        "ref_transitions":        ref_trans,
        "pred_transitions":       pred_trans,
        "transition_count_error": pred_trans - ref_trans,
        "both_transitions":       both_trans,
        "transition_match_rate":  round(match_rate, 4),
        "n_epochs":               n,
    }


# ────────────────────────────────────────────────────────────────────
#  HELPER
# ────────────────────────────────────────────────────────────────────

def _empty_result(labels: List[str]) -> Dict:
    return {
        "accuracy":        0.0,
        "cohens_kappa":    0.0,
        "precision_macro": 0.0,
        "recall_macro":    0.0,
        "f1_macro":        0.0,
        "per_class":       {},
        "confusion_matrix": {"labels": labels, "matrix": []},
        "classification_report": {},
        "n_epochs":        0,
    }
