"""
motion_posture/motion.py
────────────────────────
Motion‑type classification from radar‑derived motion scores and
signal features.

Motion types (threshold‑based):
    Still           – negligible body movement
    Minor Movement  – small postural shifts, limb adjustments
    Major Movement  – significant body motion (rolling, sitting up)
    Turning         – large body rotation / position change
"""

from __future__ import annotations
import numpy as np
from typing import Dict, List, Optional, Tuple

from . import config as CFG
from .features import epoch_indices


# ────────────────────────────────────────────────────────────────────
#  MOTION SCORE PER EPOCH
# ────────────────────────────────────────────────────────────────────

def _epoch_motion_score(
    motion_scores: np.ndarray,
    chest_disp: np.ndarray,
    start: int,
    end: int,
) -> float:
    """
    Composite motion score for one epoch.

    Combines:
      - mean raw motion score  (weight 0.5)
      - std of chest displacement  (weight 0.3)  → captures shift
      - peak‐to‐peak range change (weight 0.2)   → captures large moves

    The result is clipped to [0, 1].
    """
    ms = motion_scores[start:end]
    cd = chest_disp[start:end]

    mean_ms = np.mean(ms)

    cd_std = np.std(cd)
    cd_std_norm = min(cd_std / max(np.mean(np.abs(cd) + 1e-9), 1e-9), 1.0)

    cd_ptp = np.ptp(cd)
    cd_ptp_norm = min(cd_ptp / max(np.mean(np.abs(cd) + 1e-9), 1e-9), 1.0)

    composite = 0.5 * mean_ms + 0.3 * cd_std_norm + 0.2 * cd_ptp_norm
    return float(np.clip(composite, 0.0, 1.0))


# ────────────────────────────────────────────────────────────────────
#  CLASSIFY MOTION SEGMENTS
# ────────────────────────────────────────────────────────────────────

def classify_motion_segments(
    motion_scores: np.ndarray,
    chest_disp: np.ndarray,
    timestamps: np.ndarray,
    sampling_rate: float = 20.0,
    epoch_duration_sec: float = CFG.EPOCH_DURATION_SEC,
    epoch_overlap_frac: float = CFG.EPOCH_OVERLAP_FRAC,
    still_max: float = CFG.MOTION_STILL_MAX,
    minor_max: float = CFG.MOTION_MINOR_MAX,
    major_max: float = CFG.MOTION_MAJOR_MAX,
) -> Dict:
    """
    Classify each epoch into a motion type.

    Parameters
    ──────────
    motion_scores      : 1‑D array of per‑sample motion scores (0–1).
    chest_disp         : 1‑D array of chest displacement signal.
    timestamps         : 1‑D array of timestamps in seconds.
    sampling_rate      : samples per second.
    (remaining kwargs) : override thresholds from config.py.

    Returns
    ───────
    result : dict with keys
        "epoch_labels"     – list[str]   per‑epoch motion type
        "epoch_scores"     – list[float] per‑epoch composite score
        "epoch_indices"    – list[(int,int)]
        "epoch_centers"    – np.ndarray  epoch centre timestamps
        "epoch_records"    – list[dict]  per‑epoch records
    """
    n = len(motion_scores)
    epoch_len = int(epoch_duration_sec * sampling_rate)
    overlap_len = int(epoch_len * epoch_overlap_frac)
    idx = epoch_indices(n, epoch_len, overlap_len)

    labels: List[str] = []
    scores: List[float] = []
    centers: List[float] = []
    records: List[Dict] = []

    for k, (s, e) in enumerate(idx):
        score = _epoch_motion_score(motion_scores, chest_disp, s, e)

        if score <= still_max:
            label = "Still"
        elif score <= minor_max:
            label = "Minor Movement"
        elif score <= major_max:
            label = "Major Movement"
        else:
            label = "Turning"

        ts_start = float(timestamps[s])
        ts_end = float(timestamps[min(e - 1, n - 1)])

        labels.append(label)
        scores.append(score)
        centers.append((ts_start + ts_end) / 2.0)
        records.append({
            "epoch_index": k,
            "timestamp_start": round(ts_start, 3),
            "timestamp_end": round(ts_end, 3),
            "motion_type": label,
            "motion_score": round(score, 4),
        })

    return {
        "epoch_labels": labels,
        "epoch_scores": scores,
        "epoch_indices": idx,
        "epoch_centers": np.array(centers),
        "epoch_records": records,
    }
