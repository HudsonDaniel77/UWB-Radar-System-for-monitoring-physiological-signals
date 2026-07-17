"""
sleep_staging/features.py
─────────────────────────
Per‑epoch feature extraction for sleep‑stage classification.

Computes statistical, variability, motion, posture, and event
features from radar vital‑sign time series for each 30 s epoch.
"""

from __future__ import annotations
import numpy as np
from scipy.stats import skew, kurtosis
from typing import Dict, List, Optional, Tuple

from . import config as CFG


# ────────────────────────────────────────────────────────────────────
#  EPOCH INDEX HELPER
# ────────────────────────────────────────────────────────────────────

def epoch_indices(
    n_samples: int,
    epoch_len: int,
    overlap_len: int = 0,
) -> List[Tuple[int, int]]:
    """Return (start, end) index pairs for (optionally overlapping) epochs."""
    step = max(1, epoch_len - overlap_len)
    indices: List[Tuple[int, int]] = []
    start = 0
    while start + epoch_len <= n_samples:
        indices.append((start, start + epoch_len))
        start += step
    # trailing partial epoch
    if start < n_samples and (n_samples - start) > epoch_len // 2:
        indices.append((start, n_samples))
    return indices


# ────────────────────────────────────────────────────────────────────
#  SIGNAL STATISTICS
# ────────────────────────────────────────────────────────────────────

def _signal_stats(seg: np.ndarray) -> np.ndarray:
    """
    10 statistical features from a 1‑D segment:
    mean, median, std, var, min, max, skew, kurtosis, slope, IQR
    """
    n = len(seg)
    if n < 3:
        return np.zeros(10)

    s_mean   = np.mean(seg)
    s_median = np.median(seg)
    s_std    = np.std(seg)
    s_var    = np.var(seg)
    s_min    = np.min(seg)
    s_max    = np.max(seg)
    s_skew   = float(skew(seg, nan_policy="omit"))
    s_kurt   = float(kurtosis(seg, nan_policy="omit"))

    # linear slope (samples → value trend)
    x = np.arange(n, dtype=float)
    if s_std > 1e-12:
        s_slope = float(np.polyfit(x, seg, 1)[0])
    else:
        s_slope = 0.0

    s_iqr = float(np.percentile(seg, 75) - np.percentile(seg, 25))

    return np.array([s_mean, s_median, s_std, s_var, s_min, s_max,
                     s_skew, s_kurt, s_slope, s_iqr])


# ────────────────────────────────────────────────────────────────────
#  HRV / RRV FEATURES
# ────────────────────────────────────────────────────────────────────

def _variability_features(seg: np.ndarray) -> np.ndarray:
    """
    3 variability features (SDNN, RMSSD, range) from a BPM signal.
    Models HRV or RRV within an epoch.
    """
    if len(seg) < 3:
        return np.zeros(3)
    diffs = np.diff(seg)
    sdnn  = float(np.std(seg))
    rmssd = float(np.sqrt(np.mean(diffs ** 2))) if len(diffs) > 0 else 0.0
    rng   = float(np.max(seg) - np.min(seg))
    return np.array([sdnn, rmssd, rng])


# ────────────────────────────────────────────────────────────────────
#  MOTION FEATURES
# ────────────────────────────────────────────────────────────────────

def _motion_features(motion_seg: np.ndarray, still_thresh: float = 0.10) -> np.ndarray:
    """
    5 motion features for one epoch:
    mean, max, std, spike_count, fraction_still
    """
    if len(motion_seg) < 1:
        return np.zeros(5)
    m_mean = float(np.mean(motion_seg))
    m_max  = float(np.max(motion_seg))
    m_std  = float(np.std(motion_seg))
    m_spikes = int(np.sum(motion_seg > 0.5))
    m_still  = float(np.mean(motion_seg <= still_thresh))
    return np.array([m_mean, m_max, m_std, m_spikes, m_still])


# ────────────────────────────────────────────────────────────────────
#  POSTURE FEATURES
# ────────────────────────────────────────────────────────────────────

def _posture_features(
    posture_labels: Optional[List[str]],
    epoch_idx: int,
    posture_epoch_map: Optional[Dict[int, str]],
) -> np.ndarray:
    """
    2 posture features: changes_count, stability (1 = single posture, 0 = many).
    """
    if posture_epoch_map is None or len(posture_epoch_map) == 0:
        return np.array([0.0, 1.0])

    # look at a small window around this epoch
    window = 3
    labels_in_window = []
    for k in range(max(0, epoch_idx - window), epoch_idx + window + 1):
        if k in posture_epoch_map:
            labels_in_window.append(posture_epoch_map[k])

    if not labels_in_window:
        return np.array([0.0, 1.0])

    changes = sum(1 for i in range(1, len(labels_in_window))
                  if labels_in_window[i] != labels_in_window[i - 1])
    stability = 1.0 - (changes / max(len(labels_in_window) - 1, 1))
    return np.array([float(changes), stability])


# ────────────────────────────────────────────────────────────────────
#  EVENT FEATURES
# ────────────────────────────────────────────────────────────────────

def _event_features(
    sleep_events: Optional[List[Dict]],
    ts_start: float,
    ts_end: float,
) -> np.ndarray:
    """
    3 event counts within this epoch window:
    irregular_count, apnea_count, motion_event_count
    """
    if not sleep_events:
        return np.zeros(3)

    irr = ap = mot = 0
    for ev in sleep_events:
        ev_s = ev.get("timestamp_start", 0)
        ev_e = ev.get("timestamp_end", 0)
        # check overlap
        if ev_s <= ts_end and ev_e >= ts_start:
            etype = ev.get("event_type", "Normal")
            if etype == "Irregular":
                irr += 1
            elif etype == "Apnea":
                ap += 1
            elif etype == "Motion":
                mot += 1
    return np.array([float(irr), float(ap), float(mot)])


# ────────────────────────────────────────────────────────────────────
#  MAIN FEATURE EXTRACTOR
# ────────────────────────────────────────────────────────────────────

# Feature name list (for interpretability)
FEATURE_NAMES: List[str] = (
    [f"rr_{s}" for s in CFG.STAT_FEATURES] +          # 10
    [f"hr_{s}" for s in CFG.STAT_FEATURES] +          # 10
    [f"chest_{s}" for s in CFG.STAT_FEATURES] +       # 10
    [f"breath_{s}" for s in CFG.STAT_FEATURES] +      # 10
    CFG.RRV_FEATURES +                                 # 3
    CFG.HRV_FEATURES +                                 # 3
    CFG.MOTION_FEATURES +                              # 5
    CFG.POSTURE_FEATURES +                             # 2
    CFG.EVENT_FEATURES                                 # 3
)
FEATURE_DIM = len(FEATURE_NAMES)  # 56


def extract_epoch_features(
    rr_bpm: np.ndarray,
    hr_bpm: np.ndarray,
    chest_disp: np.ndarray,
    breath_wave: np.ndarray,
    motion_scores: np.ndarray,
    start: int,
    end: int,
    epoch_idx: int = 0,
    timestamps: Optional[np.ndarray] = None,
    sleep_events: Optional[List[Dict]] = None,
    posture_epoch_map: Optional[Dict[int, str]] = None,
) -> np.ndarray:
    """
    Extract a fixed‑length feature vector for one epoch.

    Returns 1‑D array of length FEATURE_DIM (56).
    """
    rr_seg     = rr_bpm[start:end]
    hr_seg     = hr_bpm[start:end]
    chest_seg  = chest_disp[start:end]
    breath_seg = breath_wave[start:end]
    motion_seg = motion_scores[start:end]

    # statistical features (4 signals × 10 stats = 40)
    rr_stats    = _signal_stats(rr_seg)
    hr_stats    = _signal_stats(hr_seg)
    chest_stats = _signal_stats(chest_seg)
    breath_stats = _signal_stats(breath_seg)

    # variability features (RRV + HRV = 6)
    rrv = _variability_features(rr_seg)
    hrv = _variability_features(hr_seg)

    # motion features (5)
    mot = _motion_features(motion_seg)

    # posture features (2)
    pos = _posture_features(None, epoch_idx, posture_epoch_map)

    # event features (3)
    ts_s = float(timestamps[start]) if timestamps is not None and len(timestamps) > start else 0.0
    ts_e = float(timestamps[min(end - 1, len(timestamps) - 1)]) if timestamps is not None and end > 0 else 0.0
    evt = _event_features(sleep_events, ts_s, ts_e)

    return np.concatenate([rr_stats, hr_stats, chest_stats, breath_stats,
                           rrv, hrv, mot, pos, evt])


def extract_all_features(
    data: Dict[str, np.ndarray],
    sampling_rate: float = CFG.SAMPLING_RATE,
    epoch_duration_sec: float = CFG.EPOCH_DURATION_SEC,
    epoch_overlap_frac: float = CFG.EPOCH_OVERLAP_FRAC,
    sleep_events: Optional[List[Dict]] = None,
    posture_epoch_map: Optional[Dict[int, str]] = None,
) -> Tuple[np.ndarray, List[Tuple[int, int]], np.ndarray]:
    """
    Extract features for all epochs.

    Parameters
    ──────────
    data : dict with keys
        "timestamps", "rr_bpm", "hr_bpm", "chest_disp",
        "breath_wave", "motion_scores"
    sampling_rate, epoch_duration_sec, epoch_overlap_frac : config
    sleep_events      : optional list of sleep‑event dicts
    posture_epoch_map : optional {epoch_index → posture_label}

    Returns
    ───────
    X              : (n_epochs, FEATURE_DIM) feature matrix
    indices        : list of (start, end) index pairs
    epoch_centers  : (n_epochs,) epoch centre timestamps
    """
    n = len(data["timestamps"])
    epoch_len = int(epoch_duration_sec * sampling_rate)
    overlap_len = int(epoch_len * epoch_overlap_frac)
    idx = epoch_indices(n, epoch_len, overlap_len)

    ts = data["timestamps"]
    rr  = data.get("rr_bpm",        np.zeros(n))
    hr  = data.get("hr_bpm",        np.zeros(n))
    cd  = data.get("chest_disp",    np.zeros(n))
    bw  = data.get("breath_wave",   np.zeros(n))
    mot = data.get("motion_scores", np.zeros(n))

    rows: List[np.ndarray] = []
    centers: List[float] = []

    for k, (s, e) in enumerate(idx):
        vec = extract_epoch_features(
            rr, hr, cd, bw, mot, s, e,
            epoch_idx=k,
            timestamps=ts,
            sleep_events=sleep_events,
            posture_epoch_map=posture_epoch_map,
        )
        rows.append(vec)
        centers.append(float(np.mean(ts[s:e])))

    if rows:
        X = np.vstack(rows)
    else:
        X = np.empty((0, FEATURE_DIM))

    return X, idx, np.array(centers)
