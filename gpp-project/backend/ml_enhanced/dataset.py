"""
ml_enhanced/dataset.py
──────────────────────
Data loading, synthetic data generation, windowing, and stratified
train/test splitting for the enhanced ML pipeline.

Supports three tasks:
  • event   – binary apnea/hypopnea classification
  • stage   – multi-class sleep-stage classification
  • ahi     – AHI severity regression / classification
"""

from __future__ import annotations
import os
import numpy as np
import csv
from typing import Dict, List, Optional, Tuple

from . import config as CFG
from .feature_engineering import FeatureScaler

# ────────────────────────────────────────────────────────────────────
#  SYNTHETIC DATA GENERATOR
# ────────────────────────────────────────────────────────────────────

def generate_synthetic_event_data(
    n_per_class: int = 500,
    seed: int = CFG.RANDOM_SEED,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic feature vectors for binary apnea/normal detection.

    Normal : steady moderate RR/HR, low motion
    Apnea  : RR drop / variance spike, HR compensatory rise, reduced motion
    """
    rng = np.random.RandomState(seed)
    n_feat = CFG.FEATURE_DIM

    parts_X, parts_y = [], []

    for cls_id, label in enumerate(CFG.EVENT_LABELS_BINARY):
        n = n_per_class
        X = np.zeros((n, n_feat))

        if label == "Normal":
            X[:, 0] = rng.normal(15, 1.5, n)        # rr_mean
            X[:, 1] = rng.uniform(0.3, 1.0, n)      # rr_std
            X[:, 2] = X[:, 1] ** 2                   # rr_var
            X[:, 9]  = rng.normal(68, 5, n)          # hr_mean
            X[:, 10] = rng.uniform(1, 3, n)          # hr_std
            X[:, 18] = rng.uniform(0.01, 0.1, n)     # motion_index
            X[:, 24] = 0                              # event_marker = normal
        else:
            X[:, 0] = rng.normal(8, 3.0, n)          # rr_mean drops
            X[:, 1] = rng.uniform(2, 5, n)           # rr_std high
            X[:, 2] = X[:, 1] ** 2
            X[:, 9]  = rng.normal(82, 8, n)          # hr_mean rises
            X[:, 10] = rng.uniform(3, 7, n)          # hr_std high
            X[:, 18] = rng.uniform(0.0, 0.05, n)     # motion_index very low
            X[:, 24] = rng.choice([1, 2], n)          # event_marker = irregular/apnea

        # Fill remaining columns with small noise
        for c in range(n_feat):
            if np.all(X[:, c] == 0):
                X[:, c] = rng.normal(0, 0.2, n)

        parts_X.append(X)
        parts_y.append(np.full(n, cls_id, dtype=int))

    X = np.vstack(parts_X)
    y = np.concatenate(parts_y)

    # Add global noise
    X += rng.normal(0, 0.01, X.shape)
    return X, y


def generate_synthetic_stage_data(
    n_per_class: int = 400,
    use_full_stages: bool = False,
    seed: int = CFG.RANDOM_SEED,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic feature vectors for sleep-stage classification.
    """
    rng = np.random.RandomState(seed)
    labels = CFG.STAGE_LABELS_FULL if use_full_stages else CFG.STAGE_LABELS_REDUCED
    n_classes = len(labels)
    n_feat = CFG.FEATURE_DIM

    parts_X, parts_y = [], []

    for cls_id, stage in enumerate(labels):
        n = n_per_class
        X = np.zeros((n, n_feat))

        if stage == "Wake":
            X[:, 0]  = rng.normal(18, 2, n)         # rr_mean high
            X[:, 1]  = rng.uniform(1.5, 4, n)       # rr_std high
            X[:, 9]  = rng.normal(80, 8, n)          # hr_mean high
            X[:, 10] = rng.uniform(3, 8, n)          # hr_std high
            X[:, 18] = rng.uniform(0.3, 0.8, n)      # motion high
            X[:, 23] = 0                              # baseline_stage = Wake
        elif stage == "REM":
            X[:, 0]  = rng.normal(16, 2.5, n)
            X[:, 1]  = rng.uniform(1.5, 3.5, n)
            X[:, 9]  = rng.normal(72, 6, n)
            X[:, 10] = rng.uniform(2, 5, n)
            X[:, 18] = rng.uniform(0.02, 0.12, n)
            X[:, 23] = 1
        elif stage in ("Light", "N1", "N2"):
            X[:, 0]  = rng.normal(14, 1.5, n)
            X[:, 1]  = rng.uniform(0.5, 2, n)
            X[:, 9]  = rng.normal(62, 5, n)
            X[:, 10] = rng.uniform(1, 3, n)
            X[:, 18] = rng.uniform(0.01, 0.10, n)
            X[:, 23] = 2
        elif stage in ("Deep", "N3"):
            X[:, 0]  = rng.normal(12, 1, n)
            X[:, 1]  = rng.uniform(0.2, 1, n)
            X[:, 9]  = rng.normal(56, 4, n)
            X[:, 10] = rng.uniform(0.5, 2, n)
            X[:, 18] = rng.uniform(0.0, 0.05, n)
            X[:, 23] = 3

        for c in range(n_feat):
            if np.all(X[:, c] == 0):
                X[:, c] = rng.normal(0, 0.3, n)

        parts_X.append(X)
        parts_y.append(np.full(n, cls_id, dtype=int))

    X = np.vstack(parts_X)
    y = np.concatenate(parts_y)
    X += rng.normal(0, 0.01, X.shape)
    return X, y


def generate_synthetic_ahi_data(
    n_subjects: int = CFG.SYNTHETIC_N_SUBJECTS,
    epochs_per_subject: int = CFG.SYNTHETIC_EPOCHS_PER_SUBJ,
    seed: int = CFG.RANDOM_SEED,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic data for AHI regression.

    Returns (X, y) where y = AHI value (float).
    Each row is a *subject-level* aggregated feature vector.
    """
    rng = np.random.RandomState(seed)
    n_feat = CFG.FEATURE_DIM
    X_all = []
    y_all = []

    for _ in range(n_subjects):
        ahi = rng.exponential(12.0)               # realistic skewed distribution
        ahi = min(ahi, 80.0)

        # Subject-level averages
        row = np.zeros(n_feat)
        row[0] = rng.normal(14 - 0.05 * ahi, 1.5)   # rr_mean decreases with AHI
        row[1] = rng.uniform(0.5, 1.5) + 0.05 * ahi  # rr_std increases
        row[2] = row[1] ** 2
        row[9]  = rng.normal(65 + 0.2 * ahi, 5)      # hr_mean increases
        row[10] = rng.uniform(1, 3) + 0.1 * ahi       # hr_std increases
        row[18] = rng.uniform(0.01, 0.15)
        row[24] = 2 if ahi > 15 else (1 if ahi > 5 else 0)

        for c in range(n_feat):
            if row[c] == 0:
                row[c] = rng.normal(0, 0.2)

        X_all.append(row)
        y_all.append(ahi)

    return np.array(X_all), np.array(y_all)


# ────────────────────────────────────────────────────────────────────
#  LOAD CSV DATA
# ────────────────────────────────────────────────────────────────────

def load_features_csv(
    path: str,
    feature_cols: Optional[List[str]] = None,
    label_col: str = "label",
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Load features and labels from a CSV file.

    Returns (X, y, feature_names)
    """
    import pandas as pd
    df = pd.read_csv(path)

    if feature_cols is None:
        feature_cols = [c for c in df.columns if c != label_col]

    X = df[feature_cols].values.astype(np.float64)
    y = df[label_col].values

    # Encode string labels to int if needed
    if y.dtype.kind in ("U", "O", "S"):
        uniq = sorted(set(y))
        mapping = {lbl: i for i, lbl in enumerate(uniq)}
        y = np.array([mapping[v] for v in y], dtype=int)

    return X, y.astype(int), feature_cols


# ────────────────────────────────────────────────────────────────────
#  SEQUENCE BUILDER
# ────────────────────────────────────────────────────────────────────

def build_sequences(
    X: np.ndarray,
    y: np.ndarray,
    seq_len: int = CFG.SEQUENCE_LEN,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert (n_epochs, n_features) → (n_seq, seq_len, n_features).

    Label for each sequence = label of the **last** epoch.
    """
    n = X.shape[0]
    if n < seq_len:
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
#  TRAIN / TEST SPLIT
# ────────────────────────────────────────────────────────────────────

def split_data(
    X: np.ndarray,
    y: np.ndarray,
    test_size: float = CFG.TEST_SIZE,
    seed: int = CFG.RANDOM_SEED,
    stratify: bool = True,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Stratified train/test split."""
    from sklearn.model_selection import train_test_split
    strat = y if stratify else None
    return train_test_split(X, y, test_size=test_size,
                            random_state=seed, stratify=strat)
