"""
ml_enhanced/training.py
───────────────────────
Training orchestrator for the enhanced ML/DL pipeline.

Public API
──────────
train_ml_models(task, X, y, ...)    → Dict[str, Dict]
train_single_model(...)             → Dict
"""

from __future__ import annotations
import copy
import time
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from sklearn.model_selection import StratifiedKFold

from . import config as CFG
from .dataset import (
    generate_synthetic_event_data,
    generate_synthetic_stage_data,
    generate_synthetic_ahi_data,
    build_sequences,
    split_data,
)
from .feature_engineering import FeatureScaler
from .evaluation import compute_classification_metrics, compute_regression_metrics

# Model factories
from .models.classical import build_classical_model, list_classical_models
from .models.cnn import CNN1DModel, is_available as cnn_available
from .models.cnn_lstm import CNNLSTMModel, is_available as cnn_lstm_available
from .models.transformer import TransformerModel, is_available as tf_available


# ────────────────────────────────────────────────────────────────────
#  MODEL REGISTRY
# ────────────────────────────────────────────────────────────────────

_DEEP_BUILDERS = {
    "cnn_1d":      lambda **kw: CNN1DModel(**kw),
    "cnn_lstm":    lambda **kw: CNNLSTMModel(**kw),
    "transformer": lambda **kw: TransformerModel(**kw),
}

ALL_MODEL_NAMES = list_classical_models() + list(_DEEP_BUILDERS.keys())


def _is_deep(model_type: str) -> bool:
    return model_type in _DEEP_BUILDERS


# ────────────────────────────────────────────────────────────────────
#  TRAIN A SINGLE MODEL
# ────────────────────────────────────────────────────────────────────

def train_single_model(
    model_type: str,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: Optional[np.ndarray] = None,
    y_val: Optional[np.ndarray] = None,
    task: str = "event",            # event | stage | ahi
    n_classes: int = 2,
    label_names: Optional[List[str]] = None,
    seq_len: int = CFG.SEQUENCE_LEN,
    seed: int = CFG.RANDOM_SEED,
    **model_kwargs,
) -> Dict:
    """
    Train one model and return results dict.

    Returns
    ───────
    {
        "model_type", "model", "metrics", "train_info",
        "label_names", "is_deep", "scaler"
    }
    """
    t0 = time.time()
    is_deep = _is_deep(model_type)
    scaler = FeatureScaler()

    if is_deep:
        # Deep models need 3-D input
        X_tr_s = scaler.fit_transform(X_train)
        X_seq_tr, y_seq_tr = build_sequences(X_tr_s, y_train, seq_len)

        X_seq_val, y_seq_val = None, None
        if X_val is not None and y_val is not None:
            X_va_s = scaler.transform(X_val)
            X_seq_val, y_seq_val = build_sequences(X_va_s, y_val, seq_len)

        model = _DEEP_BUILDERS[model_type](
            n_classes=n_classes, **model_kwargs,
        )
        train_info = model.fit(X_seq_tr, y_seq_tr,
                               X_seq_val, y_seq_val,
                               **model_kwargs)

        y_pred = model.predict(X_seq_tr)
        y_proba = model.predict_proba(X_seq_tr)
        metrics = compute_classification_metrics(
            y_seq_tr, y_pred, y_proba, label_names,
        )

        # Validation metrics
        if X_seq_val is not None:
            y_val_pred = model.predict(X_seq_val)
            y_val_proba = model.predict_proba(X_seq_val)
            val_metrics = compute_classification_metrics(
                y_seq_val, y_val_pred, y_val_proba, label_names,
            )
        else:
            val_metrics = {}

    else:
        # Classical models take 2-D input
        model = build_classical_model(model_type, n_classes=n_classes,
                                      seed=seed, **model_kwargs)
        train_info = model.fit(X_train, y_train, X_val, y_val)

        y_pred = model.predict(X_train)
        y_proba = model.predict_proba(X_train)
        metrics = compute_classification_metrics(
            y_train, y_pred, y_proba, label_names,
        )

        if X_val is not None:
            y_val_pred = model.predict(X_val)
            y_val_proba = model.predict_proba(X_val)
            val_metrics = compute_classification_metrics(
                y_val, y_val_pred, y_val_proba, label_names,
            )
        else:
            val_metrics = {}

    elapsed = time.time() - t0

    return {
        "model_type":   model_type,
        "model":        model,
        "metrics":      metrics,        # train
        "val_metrics":  val_metrics,     # validation
        "train_info":   train_info,
        "label_names":  label_names,
        "is_deep":      is_deep,
        "scaler":       scaler if is_deep else None,
        "elapsed_sec":  round(elapsed, 2),
    }


# ────────────────────────────────────────────────────────────────────
#  CROSS-VALIDATION
# ────────────────────────────────────────────────────────────────────

def cross_validate_model(
    model_type: str,
    X: np.ndarray,
    y: np.ndarray,
    n_folds: int = CFG.CV_FOLDS,
    n_classes: int = 2,
    label_names: Optional[List[str]] = None,
    seed: int = CFG.RANDOM_SEED,
    **model_kwargs,
) -> Dict:
    """
    Stratified k-fold cross-validation for a single model type.

    Returns {fold_metrics, mean_accuracy, std_accuracy}
    """
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    fold_metrics: List[Dict] = []

    for fold_idx, (train_idx, val_idx) in enumerate(skf.split(X, y)):
        X_tr, X_va = X[train_idx], X[val_idx]
        y_tr, y_va = y[train_idx], y[val_idx]

        result = train_single_model(
            model_type, X_tr, y_tr, X_va, y_va,
            n_classes=n_classes, label_names=label_names,
            seed=seed, **model_kwargs,
        )
        fold_metrics.append({
            "fold": fold_idx + 1,
            "val_accuracy":  result["val_metrics"].get("accuracy", 0),
            "val_f1":        result["val_metrics"].get("f1_macro", 0),
        })

    accs = [fm["val_accuracy"] for fm in fold_metrics]
    return {
        "model_type":    model_type,
        "fold_metrics":  fold_metrics,
        "mean_accuracy": float(np.mean(accs)),
        "std_accuracy":  float(np.std(accs)),
    }


# ────────────────────────────────────────────────────────────────────
#  TRAIN ALL MODELS (multi-model comparison)
# ────────────────────────────────────────────────────────────────────

def train_ml_models(
    task: str = "event",
    X: Optional[np.ndarray] = None,
    y: Optional[np.ndarray] = None,
    model_types: Optional[List[str]] = None,
    use_full_stages: bool = False,
    seed: int = CFG.RANDOM_SEED,
    skip_deep: bool = False,
    **kwargs,
) -> Dict[str, Dict]:
    """
    Train and compare multiple models on the same data.

    Parameters
    ──────────
    task         : "event" | "stage" | "ahi"
    X, y         : feature matrix and labels.  If None, synthetic data
                   is generated for the chosen task.
    model_types  : list of model names to train.  Default = all.
    skip_deep    : if True, skip deep-learning models entirely
    **kwargs     : forwarded to train_single_model

    Returns dict  {model_type: result_dict, ...}
    """
    # Resolve task config
    if task == "event":
        label_names = CFG.EVENT_LABELS_BINARY
        n_classes = 2
        if X is None or y is None:
            X, y = generate_synthetic_event_data(seed=seed)
    elif task == "stage":
        label_names = (CFG.STAGE_LABELS_FULL if use_full_stages
                       else CFG.STAGE_LABELS_REDUCED)
        n_classes = len(label_names)
        if X is None or y is None:
            X, y = generate_synthetic_stage_data(
                use_full_stages=use_full_stages, seed=seed)
    elif task == "ahi":
        label_names = list(CFG.AHI_SEVERITY.keys()) + ["Severe"]
        n_classes = 4
        if X is None or y is None:
            X, y = generate_synthetic_ahi_data(seed=seed)
            # Discretise AHI into severity classes for classification
            y = _ahi_to_class(y)
    else:
        raise ValueError(f"Unknown task: {task}")

    # Resolve model list
    if model_types is None:
        model_types = list_classical_models()
        if not skip_deep:
            model_types += list(_DEEP_BUILDERS.keys())

    if skip_deep:
        model_types = [m for m in model_types if not _is_deep(m)]

    # Split once
    X_train, X_val, y_train, y_val = split_data(X, y, seed=seed)

    results: Dict[str, Dict] = {}
    for mt in model_types:
        print(f"  [ml_enhanced] training {mt} …")
        try:
            res = train_single_model(
                mt, X_train, y_train, X_val, y_val,
                task=task, n_classes=n_classes,
                label_names=label_names, seed=seed,
                **kwargs,
            )
            results[mt] = res
        except Exception as exc:
            results[mt] = {"model_type": mt,
                           "error": str(exc)}

    return results


# ────────────────────────────────────────────────────────────────────
#  HELPERS
# ────────────────────────────────────────────────────────────────────

def _ahi_to_class(ahi_values: np.ndarray) -> np.ndarray:
    """Convert continuous AHI to severity class (0-3)."""
    classes = np.zeros(len(ahi_values), dtype=int)
    for i, v in enumerate(ahi_values):
        if v < 5:
            classes[i] = 0
        elif v < 15:
            classes[i] = 1
        elif v < 30:
            classes[i] = 2
        else:
            classes[i] = 3
    return classes
