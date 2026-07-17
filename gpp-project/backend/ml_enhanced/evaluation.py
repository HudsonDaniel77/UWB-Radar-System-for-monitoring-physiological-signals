"""
ml_enhanced/evaluation.py
─────────────────────────
Evaluation metrics, model comparison tables, confusion matrices,
and ROC curve computation for the enhanced ML pipeline.
"""

from __future__ import annotations
import numpy as np
from typing import Dict, List, Optional, Tuple

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)


# ────────────────────────────────────────────────────────────────────
#  CLASSIFICATION METRICS
# ────────────────────────────────────────────────────────────────────

def compute_classification_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: Optional[np.ndarray] = None,
    label_names: Optional[List[str]] = None,
) -> Dict:
    """
    Compute standard classification metrics.

    Returns dict with accuracy, precision, recall, f1, roc_auc,
    confusion_matrix, per_class, classification_report.
    """
    n_true = len(y_true)
    if n_true == 0:
        return {"accuracy": 0, "n": 0}

    labels = sorted(set(y_true) | set(y_pred))
    n_classes = len(labels)

    acc  = float(accuracy_score(y_true, y_pred))
    prec = float(precision_score(y_true, y_pred, average="macro",
                                  zero_division=0))
    rec  = float(recall_score(y_true, y_pred, average="macro",
                               zero_division=0))
    f1_m = float(f1_score(y_true, y_pred, average="macro",
                           zero_division=0))

    cm = confusion_matrix(y_true, y_pred, labels=labels).tolist()

    report = classification_report(
        y_true, y_pred,
        labels=labels,
        target_names=label_names[:n_classes] if label_names else None,
        zero_division=0,
        output_dict=True,
    )

    # Per-class breakdown
    per_class: Dict[str, Dict] = {}
    for idx, lbl in enumerate(labels):
        name = label_names[idx] if label_names and idx < len(label_names) else str(lbl)
        y_t_bin = (np.array(y_true) == lbl).astype(int)
        y_p_bin = (np.array(y_pred) == lbl).astype(int)
        per_class[name] = {
            "precision": float(precision_score(y_t_bin, y_p_bin, zero_division=0)),
            "recall":    float(recall_score(y_t_bin, y_p_bin, zero_division=0)),
            "f1":        float(f1_score(y_t_bin, y_p_bin, zero_division=0)),
            "support":   int(np.sum(y_t_bin)),
        }

    # ROC-AUC
    roc_auc = _compute_roc_auc(y_true, y_proba, n_classes)

    return {
        "accuracy":       round(acc, 4),
        "precision_macro": round(prec, 4),
        "recall_macro":    round(rec, 4),
        "f1_macro":        round(f1_m, 4),
        "roc_auc":         round(roc_auc, 4) if roc_auc is not None else None,
        "confusion_matrix": cm,
        "per_class":       per_class,
        "classification_report": report,
        "n":               n_true,
    }


def _compute_roc_auc(
    y_true: np.ndarray,
    y_proba: Optional[np.ndarray],
    n_classes: int,
) -> Optional[float]:
    """Safely compute ROC-AUC (binary or multi-class OvR)."""
    if y_proba is None:
        return None
    try:
        if n_classes == 2:
            if y_proba.ndim == 2:
                auc = roc_auc_score(y_true, y_proba[:, 1])
            else:
                auc = roc_auc_score(y_true, y_proba)
        else:
            auc = roc_auc_score(y_true, y_proba,
                                multi_class="ovr", average="macro")
        return float(auc)
    except (ValueError, IndexError):
        return None


# ────────────────────────────────────────────────────────────────────
#  REGRESSION METRICS  (AHI prediction)
# ────────────────────────────────────────────────────────────────────

def compute_regression_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> Dict:
    """
    Compute regression metrics for AHI prediction.
    """
    n = len(y_true)
    if n == 0:
        return {"mae": 0, "rmse": 0, "r2": 0, "n": 0}

    mae  = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2   = float(r2_score(y_true, y_pred)) if n > 1 else 0.0

    return {
        "mae":  round(mae, 4),
        "rmse": round(rmse, 4),
        "r2":   round(r2, 4),
        "n":    n,
    }


# ────────────────────────────────────────────────────────────────────
#  ROC CURVE DATA
# ────────────────────────────────────────────────────────────────────

def compute_roc_curve(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    pos_label: int = 1,
) -> Dict:
    """
    Compute FPR, TPR arrays for plotting ROC curves.
    """
    from sklearn.metrics import roc_curve as sk_roc

    if y_proba.ndim == 2:
        scores = y_proba[:, pos_label]
    else:
        scores = y_proba

    fpr, tpr, thresholds = sk_roc(y_true, scores, pos_label=pos_label)
    return {
        "fpr":        fpr.tolist(),
        "tpr":        tpr.tolist(),
        "thresholds": thresholds.tolist(),
    }


# ────────────────────────────────────────────────────────────────────
#  MODEL COMPARISON TABLE
# ────────────────────────────────────────────────────────────────────

def build_comparison_table(
    results: Dict[str, Dict],
) -> List[Dict]:
    """
    Build a comparison table from multi-model training results.

    Parameters
    ──────────
    results : dict returned by ``train_ml_models()``

    Returns list of dicts with columns:
        model, accuracy, f1, precision, recall, roc_auc, elapsed_sec
    """
    rows: List[Dict] = []
    for model_type, res in results.items():
        if "error" in res:
            rows.append({"model": model_type, "error": res["error"]})
            continue

        val = res.get("val_metrics", {})
        rows.append({
            "model":       model_type,
            "accuracy":    val.get("accuracy", 0),
            "f1":          val.get("f1_macro", 0),
            "precision":   val.get("precision_macro", 0),
            "recall":      val.get("recall_macro", 0),
            "roc_auc":     val.get("roc_auc"),
            "elapsed_sec": res.get("elapsed_sec", 0),
        })

    # Sort by f1 descending
    rows.sort(key=lambda r: r.get("f1", 0), reverse=True)
    return rows


def evaluate_models(
    results: Dict[str, Dict],
    X_test: np.ndarray,
    y_test: np.ndarray,
    label_names: Optional[List[str]] = None,
    seq_len: int = 10,
) -> Dict[str, Dict]:
    """
    Evaluate all trained models on an unseen test set.

    Returns {model_type: metrics_dict}
    """
    from .dataset import build_sequences

    test_results: Dict[str, Dict] = {}

    for model_type, res in results.items():
        if "error" in res or res.get("model") is None:
            test_results[model_type] = {"error": res.get("error", "no model")}
            continue

        model = res["model"]
        is_deep = res.get("is_deep", False)

        if is_deep:
            scaler = res.get("scaler")
            X_s = scaler.transform(X_test) if scaler and scaler.fitted else X_test
            X_seq, y_seq = build_sequences(X_s, y_test, seq_len)
            y_pred = model.predict(X_seq)
            y_proba = model.predict_proba(X_seq)
            metrics = compute_classification_metrics(
                y_seq, y_pred, y_proba, label_names,
            )
        else:
            y_pred = model.predict(X_test)
            y_proba = model.predict_proba(X_test)
            metrics = compute_classification_metrics(
                y_test, y_pred, y_proba, label_names,
            )

        test_results[model_type] = metrics

    return test_results
