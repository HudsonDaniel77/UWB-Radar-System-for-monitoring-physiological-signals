"""
motion_posture/features.py
──────────────────────────
Feature extraction utilities for motion classification and posture
recognition from radar vital‑sign time series.
"""

from __future__ import annotations
import numpy as np
from scipy.stats import skew, kurtosis
from typing import Dict, List, Optional, Tuple

from . import config as CFG


# ────────────────────────────────────────────────────────────────────
#  EPOCH INDICES (shared helper)
# ────────────────────────────────────────────────────────────────────

def epoch_indices(n_samples: int,
                  epoch_len: int,
                  overlap_len: int) -> List[Tuple[int, int]]:
    """Return (start, end) index pairs for overlapping epochs."""
    step = max(1, epoch_len - overlap_len)
    indices = []
    start = 0
    while start + epoch_len <= n_samples:
        indices.append((start, start + epoch_len))
        start += step
    if start < n_samples and (n_samples - start) > epoch_len // 2:
        indices.append((start, n_samples))
    return indices


# ────────────────────────────────────────────────────────────────────
#  STATISTICAL FEATURES PER SEGMENT
# ────────────────────────────────────────────────────────────────────

def _segment_stats(seg: np.ndarray) -> np.ndarray:
    """
    Compute 6 statistical features from a 1‑D segment:
        mean, std, min, max, skewness, kurtosis
    """
    if len(seg) < 2:
        return np.zeros(CFG.N_STAT_FEATURES)
    return np.array([
        np.mean(seg),
        np.std(seg),
        np.min(seg),
        np.max(seg),
        float(skew(seg, nan_policy="omit")),
        float(kurtosis(seg, nan_policy="omit")),
    ])


def extract_epoch_features(
    chest_disp: np.ndarray,
    breath_wave: np.ndarray,
    heart_wave: np.ndarray,
    combined_sig: np.ndarray,
    range_m: np.ndarray,
    motion_score: np.ndarray,
    rr_bpm: np.ndarray,
    hr_bpm: np.ndarray,
    start: int,
    end: int,
) -> np.ndarray:
    """
    Extract a fixed‑length feature vector for one epoch window.

    Feature composition (30 + 4 = 34 features):
        6 stats × 5 signals  = 30
        + mean motion score
        + mean RR BPM
        + mean HR BPM
        + epoch energy (RMS of combined signal)

    Returns 1‑D array of length 34.
    """
    signals = [
        chest_disp[start:end],
        breath_wave[start:end],
        heart_wave[start:end],
        combined_sig[start:end],
        range_m[start:end],
    ]

    stats = np.concatenate([_segment_stats(s) for s in signals])

    extras = np.array([
        float(np.mean(motion_score[start:end])),
        float(np.nanmean(rr_bpm[start:end])),
        float(np.nanmean(hr_bpm[start:end])),
        float(np.sqrt(np.mean(combined_sig[start:end] ** 2)))
        if len(combined_sig[start:end]) > 0 else 0.0,
    ])

    return np.concatenate([stats, extras])


def extract_all_features(
    data: Dict[str, np.ndarray],
    epoch_duration_sec: float = CFG.EPOCH_DURATION_SEC,
    epoch_overlap_frac: float = CFG.EPOCH_OVERLAP_FRAC,
    sampling_rate: float = 20.0,
) -> Tuple[np.ndarray, List[Tuple[int, int]]]:
    """
    Extract feature matrix for all epochs.

    Parameters
    ──────────
    data : dict with keys
        "timestamps", "chest_disp", "breath_wave", "heart_wave",
        "combined", "range_m", "motion_scores", "rr_bpm", "hr_bpm"
    epoch_duration_sec, epoch_overlap_frac, sampling_rate : config

    Returns
    ───────
    X       : (n_epochs, n_features) feature matrix
    indices : list of (start, end) epoch index pairs
    """
    n = len(data["timestamps"])
    epoch_len = int(epoch_duration_sec * sampling_rate)
    overlap_len = int(epoch_len * epoch_overlap_frac)
    idx = epoch_indices(n, epoch_len, overlap_len)

    chest  = data.get("chest_disp",    np.zeros(n))
    breath = data.get("breath_wave",   np.zeros(n))
    heart  = data.get("heart_wave",    np.zeros(n))
    comb   = data.get("combined",      np.zeros(n))
    rng    = data.get("range_m",       np.zeros(n))
    motion = data.get("motion_scores", np.zeros(n))
    rr     = data.get("rr_bpm",        np.zeros(n))
    hr     = data.get("hr_bpm",        np.zeros(n))

    rows = []
    for s, e in idx:
        rows.append(extract_epoch_features(
            chest, breath, heart, comb, rng, motion, rr, hr, s, e,
        ))

    X = np.vstack(rows) if rows else np.empty((0, CFG.N_STAT_FEATURES * CFG.N_FEATURE_SIGNALS + CFG.EXTRA_FEATURES))
    return X, idx


# ────────────────────────────────────────────────────────────────────
#  FEATURE DIMENSION CONSTANT (for model input)
# ────────────────────────────────────────────────────────────────────
FEATURE_DIM = CFG.N_STAT_FEATURES * CFG.N_FEATURE_SIGNALS + CFG.EXTRA_FEATURES  # 34
