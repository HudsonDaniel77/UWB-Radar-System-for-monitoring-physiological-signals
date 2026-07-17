"""
sleep_staging/training.py
─────────────────────────
Training pipeline for sleep‑stage classifiers.

• Generates synthetic labelled data when no real labels exist.
• Supports classical (sklearn) and deep (Keras) models.
• Provides train/test split, k‑fold cross‑validation, and metric
  reporting.
"""

from __future__ import annotations
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.preprocessing import StandardScaler

from . import config as CFG
from .features import FEATURE_DIM
from .models_classical import build_model as build_classical, save_model
from .models_deep import (
    is_available as tf_available,
    build_deep_model,
    save_deep_model,
)
from .evaluate import compute_metrics


# ────────────────────────────────────────────────────────────────────
#  SYNTHETIC DATA GENERATOR
# ────────────────────────────────────────────────────────────────────

def generate_synthetic_sleep_data(
    n_per_class: int = CFG.SYNTHETIC_SAMPLES_PER_CLASS,
    n_classes: int = 4,
    use_full_stages: bool = CFG.USE_FULL_STAGES,
    seed: int = CFG.RANDOM_SEED,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic feature vectors for sleep stages.

    Each stage has characteristic physiological signatures:
      Wake  – high HR variability, high motion, high RR
      REM   – irregular RR, moderate HR, very low motion
      Light – steady moderate RR/HR, low motion
      Deep  – very low RR, very low HR, minimal motion, high breath amp

    Returns (X, y)  with  X.shape = (n_total, FEATURE_DIM)
    """
    rng = np.random.RandomState(seed)

    if use_full_stages:
        labels = CFG.STAGE_LABELS_FULL
        n_classes = len(labels)
    else:
        labels = CFG.STAGE_LABELS_REDUCED
        n_classes = len(labels)

    X_parts, y_parts = [], []

    for cls_id, stage in enumerate(labels[:n_classes]):
        n = n_per_class
        feats = np.zeros((n, FEATURE_DIM))

        # Feature layout (see features.py FEATURE_NAMES):
        #   0-9:   RR stats (mean, median, std, var, min, max, skew, kurt, slope, iqr)
        #  10-19:  HR stats
        #  20-29:  Chest displacement stats
        #  30-39:  Breath waveform stats
        #  40-42:  RRV (sdnn, rmssd, range)
        #  43-45:  HRV (sdnn, rmssd, range)
        #  46-50:  motion (mean, max, std, spikes, frac_still)
        #  51-52:  posture (changes, stability)
        #  53-55:  events (irregular, apnea, motion)

        if stage == "Wake":
            feats[:, 0] = rng.normal(18, 2, n)          # RR mean ~18 BPM
            feats[:, 2] = rng.uniform(1.5, 4, n)        # RR std high
            feats[:, 10] = rng.normal(80, 8, n)         # HR mean ~80
            feats[:, 12] = rng.uniform(3, 8, n)         # HR std high
            feats[:, 22] = rng.uniform(0.3, 0.8, n)     # chest std moderate
            feats[:, 32] = rng.uniform(0.3, 0.7, n)     # breath std
            feats[:, 40] = rng.uniform(1, 4, n)         # RRV sdnn high
            feats[:, 43] = rng.uniform(3, 8, n)         # HRV sdnn high
            feats[:, 46] = rng.uniform(0.3, 0.8, n)     # motion mean high
            feats[:, 47] = rng.uniform(0.5, 1.0, n)     # motion max
            feats[:, 50] = rng.uniform(0.0, 0.4, n)     # frac still low

        elif stage == "REM":
            feats[:, 0] = rng.normal(16, 2.5, n)        # RR mean ~16
            feats[:, 2] = rng.uniform(1.5, 3.5, n)      # RR std irregular
            feats[:, 6] = rng.normal(0, 0.8, n)         # RR skew variable
            feats[:, 10] = rng.normal(70, 6, n)         # HR mean ~70
            feats[:, 12] = rng.uniform(2, 5, n)         # HR std moderate
            feats[:, 22] = rng.uniform(0.15, 0.4, n)    # chest std low-mod
            feats[:, 32] = rng.uniform(0.3, 0.6, n)     # breath std moderate
            feats[:, 40] = rng.uniform(0.5, 2.5, n)     # RRV
            feats[:, 43] = rng.uniform(2, 5, n)         # HRV moderate
            feats[:, 46] = rng.uniform(0.02, 0.15, n)   # motion very low
            feats[:, 50] = rng.uniform(0.6, 0.95, n)    # frac still high

        elif stage in ("Light", "N1", "N2"):
            feats[:, 0] = rng.normal(14, 1.5, n)        # RR mean ~14
            feats[:, 2] = rng.uniform(0.5, 2.0, n)      # RR std moderate
            feats[:, 10] = rng.normal(62, 5, n)         # HR mean ~62
            feats[:, 12] = rng.uniform(1, 3, n)         # HR std low
            feats[:, 22] = rng.uniform(0.2, 0.5, n)     # chest
            feats[:, 32] = rng.uniform(0.3, 0.5, n)     # breath
            feats[:, 40] = rng.uniform(0.3, 1.5, n)     # RRV
            feats[:, 43] = rng.uniform(1, 3, n)         # HRV
            feats[:, 46] = rng.uniform(0.01, 0.10, n)   # motion low
            feats[:, 50] = rng.uniform(0.8, 1.0, n)     # frac still

        elif stage in ("Deep", "N3"):
            feats[:, 0] = rng.normal(12, 1.0, n)        # RR mean ~12 (slow)
            feats[:, 2] = rng.uniform(0.2, 1.0, n)      # RR std very low
            feats[:, 10] = rng.normal(56, 4, n)         # HR mean ~56
            feats[:, 12] = rng.uniform(0.5, 2, n)       # HR std very low
            feats[:, 22] = rng.uniform(0.4, 0.9, n)     # chest high amplitude
            feats[:, 32] = rng.uniform(0.5, 0.9, n)     # breath high
            feats[:, 40] = rng.uniform(0.1, 0.8, n)     # RRV low
            feats[:, 43] = rng.uniform(0.5, 2, n)       # HRV low
            feats[:, 46] = rng.uniform(0.0, 0.05, n)    # motion minimal
            feats[:, 50] = rng.uniform(0.9, 1.0, n)     # frac still max

        # Fill remaining feature slots with correlated noise
        for i in range(FEATURE_DIM):
            if feats[:, i].sum() == 0:
                feats[:, i] = rng.normal(0, 0.3, n)

        feats[:, 51] = rng.uniform(0, 2, n)             # posture changes
        feats[:, 52] = rng.uniform(0.6, 1.0, n)         # posture stability

        # event features (small counts for sleep, more for wake)
        if stage == "Wake":
            feats[:, 53] = rng.poisson(0.3, n)
            feats[:, 55] = rng.poisson(1.0, n)
        else:
            feats[:, 53] = rng.poisson(0.05, n)
            feats[:, 55] = rng.poisson(0.02, n)

        X_parts.append(feats)
        y_parts.append(np.full(n, cls_id, dtype=int))

    X = np.vstack(X_parts)
    y = np.concatenate(y_parts)

    # add global noise
    X += rng.normal(0, 0.01, X.shape)

    return X, y


# ────────────────────────────────────────────────────────────────────
#  SEQUENCE BUILDER (for deep models)
# ────────────────────────────────────────────────────────────────────

def build_sequences(
    X: np.ndarray,
    y: np.ndarray,
    seq_len: int = CFG.DL_SEQUENCE_LEN,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert (n_epochs, n_features) into (n_seq, seq_len, n_features)
    for recurrent / temporal models.  The label for each sequence is
    the label of the **last** epoch in the window.
    """
    n = X.shape[0]
    if n < seq_len:
        # pad with zeros at beginning
        pad = np.zeros((seq_len - n, X.shape[1]))
        X_pad = np.vstack([pad, X])
        y_pad = np.concatenate([np.full(seq_len - n, y[0]), y])
        return X_pad[np.newaxis, :, :], y_pad[-1:]

    X_seq, y_seq = [], []
    for i in range(seq_len, n + 1):
        X_seq.append(X[i - seq_len: i])
        y_seq.append(y[i - 1])
    return np.array(X_seq), np.array(y_seq)


# ────────────────────────────────────────────────────────────────────
#  TRAIN CLASSICAL MODEL
# ────────────────────────────────────────────────────────────────────

def train_classical(
    X: Optional[np.ndarray] = None,
    y: Optional[np.ndarray] = None,
    model_type: str = CFG.DEFAULT_MODEL_TYPE,
    test_size: float = CFG.TEST_SIZE,
    cv_folds: int = CFG.CV_FOLDS,
    seed: int = CFG.RANDOM_SEED,
    save_path: Optional[str] = None,
    use_full_stages: bool = CFG.USE_FULL_STAGES,
    **model_kwargs,
) -> Dict:
    """
    Train a classical ML sleep‑stage classifier.

    If X/y are None, synthetic data is generated.

    Returns dict with:
        "model", "model_type", "metrics", "cv_scores",
        "model_path", "label_names"
    """
    if use_full_stages:
        label_names = CFG.STAGE_LABELS_FULL
    else:
        label_names = CFG.STAGE_LABELS_REDUCED

    n_classes = len(label_names)

    if X is None or y is None:
        X, y = generate_synthetic_sleep_data(
            n_classes=n_classes, use_full_stages=use_full_stages, seed=seed,
        )

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=seed, stratify=y,
    )

    # Build model
    pipeline = build_classical(model_type, n_classes=n_classes, seed=seed, **model_kwargs)
    pipeline.fit(X_train, y_train)

    # Evaluate
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test) if hasattr(pipeline, "predict_proba") else None
    metrics = compute_metrics(y_test, y_pred, y_proba, label_names)

    # Cross‑validation
    cv_scores = _cross_validate(pipeline, X, y, cv_folds, seed)

    # Save
    model_path = save_model(pipeline, model_type, path=save_path)

    return {
        "model": pipeline,
        "model_type": model_type,
        "metrics": metrics,
        "cv_scores": cv_scores,
        "model_path": model_path,
        "label_names": label_names,
    }


# ────────────────────────────────────────────────────────────────────
#  TRAIN DEEP MODEL
# ────────────────────────────────────────────────────────────────────

def train_deep(
    X: Optional[np.ndarray] = None,
    y: Optional[np.ndarray] = None,
    model_type: str = "lstm",
    test_size: float = CFG.TEST_SIZE,
    seed: int = CFG.RANDOM_SEED,
    epochs: int = CFG.DL_EPOCHS,
    batch_size: int = CFG.DL_BATCH_SIZE,
    save_path: Optional[str] = None,
    use_full_stages: bool = CFG.USE_FULL_STAGES,
) -> Dict:
    """
    Train a deep‑learning sleep‑stage classifier.

    Returns dict with:
        "model", "model_type", "metrics", "history", "model_path", "label_names"
    """
    if not tf_available():
        return {
            "model": None,
            "model_type": model_type,
            "metrics": {},
            "history": {},
            "model_path": "",
            "label_names": [],
            "error": "TensorFlow not installed. Install with: pip install tensorflow",
        }

    label_names = CFG.STAGE_LABELS_FULL if use_full_stages else CFG.STAGE_LABELS_REDUCED
    n_classes = len(label_names)

    if X is None or y is None:
        X, y = generate_synthetic_sleep_data(
            n_classes=n_classes, use_full_stages=use_full_stages, seed=seed,
        )

    # Standardise
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Build sequences
    X_seq, y_seq = build_sequences(X_scaled, y)

    # Split (stratified on sequence labels)
    split_idx = int(len(X_seq) * (1 - test_size))
    X_train, X_test = X_seq[:split_idx], X_seq[split_idx:]
    y_train, y_test = y_seq[:split_idx], y_seq[split_idx:]

    # Build model
    input_shape = (X_train.shape[1], X_train.shape[2])
    model = build_deep_model(model_type, input_shape, n_classes)

    if model is None:
        return {"model": None, "model_type": model_type, "metrics": {},
                "history": {}, "model_path": "", "label_names": label_names,
                "error": "Model build returned None (TF issue)"}

    history = model.fit(
        X_train, y_train,
        validation_data=(X_test, y_test),
        epochs=epochs,
        batch_size=batch_size,
        verbose=0,
    )

    # Evaluate
    y_pred_proba = model.predict(X_test, verbose=0)
    y_pred = np.argmax(y_pred_proba, axis=1)
    metrics = compute_metrics(y_test, y_pred, y_pred_proba, label_names)

    # Save
    model_path = save_deep_model(model, model_type, path=save_path)

    return {
        "model": model,
        "model_type": model_type,
        "metrics": metrics,
        "history": {k: [float(v) for v in vals] for k, vals in history.history.items()},
        "model_path": model_path,
        "label_names": label_names,
        "scaler": scaler,
    }


# ────────────────────────────────────────────────────────────────────
#  CROSS‑VALIDATION HELPER
# ────────────────────────────────────────────────────────────────────

def _cross_validate(
    pipeline: Any,
    X: np.ndarray,
    y: np.ndarray,
    n_folds: int,
    seed: int,
) -> Dict:
    """Stratified k‑fold cross‑validation scores."""
    from sklearn.metrics import accuracy_score
    import copy

    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    fold_accs: List[float] = []

    for train_idx, val_idx in skf.split(X, y):
        clf = copy.deepcopy(pipeline)
        clf.fit(X[train_idx], y[train_idx])
        preds = clf.predict(X[val_idx])
        fold_accs.append(float(accuracy_score(y[val_idx], preds)))

    return {
        "fold_accuracies": fold_accs,
        "mean_accuracy": float(np.mean(fold_accs)),
        "std_accuracy": float(np.std(fold_accs)),
    }
