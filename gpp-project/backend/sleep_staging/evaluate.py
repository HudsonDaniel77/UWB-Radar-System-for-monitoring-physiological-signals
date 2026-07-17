"""
sleep_staging/evaluate.py
─────────────────────────
Evaluation metrics for sleep‑stage classification.

Reports:
    • Accuracy, Precision, Recall, F1  (macro & per‑class)
    • Confusion matrix
    • Cohen's Kappa
    • ROC AUC (one‑vs‑rest, when probabilities available)
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
    confusion_matrix,
    cohen_kappa_score,
)

# Optional ROC/AUC
try:
    from sklearn.metrics import roc_auc_score
    _HAS_ROC = True
except ImportError:
    _HAS_ROC = False


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: Optional[np.ndarray] = None,
    label_names: Optional[List[str]] = None,
) -> Dict:
    """
    Compute comprehensive classification metrics.

    Parameters
    ──────────
    y_true      : ground‑truth integer labels
    y_pred      : predicted integer labels
    y_proba     : (n_samples, n_classes) probability matrix (optional)
    label_names : list of class name strings

    Returns
    ───────
    dict with "accuracy", "precision", "recall", "f1", "kappa",
    "confusion_matrix", "classification_report", "roc_auc"
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    acc = float(accuracy_score(y_true, y_pred))
    prec = float(precision_score(y_true, y_pred, average="macro", zero_division=0))
    rec  = float(recall_score(y_true, y_pred, average="macro", zero_division=0))
    f1   = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    kappa = float(cohen_kappa_score(y_true, y_pred))

    # Per‑class F1
    present_labels = sorted(set(np.concatenate([y_true, y_pred])))
    report = classification_report(
        y_true, y_pred,
        labels=present_labels,
        target_names=[label_names[i] for i in present_labels] if label_names else None,
        output_dict=True,
        zero_division=0,
    )

    cm = confusion_matrix(y_true, y_pred, labels=present_labels)

    # per‑class F1
    per_class_f1 = {}
    if label_names:
        for i in present_labels:
            name = label_names[i]
            per_class_f1[name] = report.get(name, {}).get("f1-score", 0.0)

    # ROC AUC (one‑vs‑rest)
    roc_auc = None
    roc_auc_per_class = {}
    if y_proba is not None and _HAS_ROC:
        try:
            roc_auc = float(roc_auc_score(
                y_true, y_proba, multi_class="ovr", average="macro",
            ))
            # per‑class
            for i in present_labels:
                name = label_names[i] if label_names else str(i)
                binary_true = (y_true == i).astype(int)
                if binary_true.sum() > 0 and y_proba.shape[1] > i:
                    roc_auc_per_class[name] = float(roc_auc_score(
                        binary_true, y_proba[:, i],
                    ))
        except Exception:
            pass

    return {
        "accuracy": round(acc, 4),
        "precision_macro": round(prec, 4),
        "recall_macro": round(rec, 4),
        "f1_macro": round(f1, 4),
        "cohens_kappa": round(kappa, 4),
        "per_class_f1": {k: round(v, 4) for k, v in per_class_f1.items()},
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
        "roc_auc_macro": round(roc_auc, 4) if roc_auc is not None else None,
        "roc_auc_per_class": {k: round(v, 4) for k, v in roc_auc_per_class.items()},
    }
