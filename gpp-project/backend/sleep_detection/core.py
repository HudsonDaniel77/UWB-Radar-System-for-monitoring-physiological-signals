"""
sleep_detection/core.py
───────────────────────
Core sleep‐event detection functions.

Functions
─────────
    compute_baseline_rr   – Compute baseline respiration amplitude from a
                            stable initial segment.
    mask_motion_segments  – Mark high‐motion epochs so they are not
                            labelled as apnea.
    detect_sleep_events   – Main entry point: divides the time series
                            into epochs, classifies each epoch, and
                            merges adjacent labels.
"""

from __future__ import annotations
import numpy as np
import datetime
from typing import Dict, List, Optional, Tuple

from . import config as CFG


# ────────────────────────────────────────────────────────────────────
#  HELPERS
# ────────────────────────────────────────────────────────────────────

def _epoch_indices(n_samples: int,
                   epoch_len: int,
                   overlap_len: int) -> List[Tuple[int, int]]:
    """Return (start, end) index pairs for overlapping epochs."""
    step = epoch_len - overlap_len
    indices = []
    start = 0
    while start + epoch_len <= n_samples:
        indices.append((start, start + epoch_len))
        start += step
    # capture trailing partial epoch if substantial
    if start < n_samples and (n_samples - start) > epoch_len // 2:
        indices.append((start, n_samples))
    return indices


def _peak_amplitude(segment: np.ndarray) -> float:
    """Peak‐to‐peak amplitude of a 1‑D signal segment."""
    if len(segment) < 2:
        return 0.0
    return float(np.max(segment) - np.min(segment))


def _rms_amplitude(segment: np.ndarray) -> float:
    """Root‑mean‑square of a 1‑D signal segment."""
    if len(segment) < 1:
        return 0.0
    return float(np.sqrt(np.mean(segment ** 2)))


# ────────────────────────────────────────────────────────────────────
#  BASELINE
# ────────────────────────────────────────────────────────────────────

def compute_baseline_rr(
    rr_amplitude: np.ndarray,
    timestamps: np.ndarray,
    motion_scores: Optional[np.ndarray] = None,
    baseline_window_sec: float = CFG.BASELINE_WINDOW_SEC,
    baseline_percentile: float = CFG.BASELINE_PERCENTILE,
    motion_threshold: float = CFG.MOTION_SCORE_THRESHOLD,
    sampling_rate: float = 20.0,
) -> float:
    """
    Compute a robust baseline respiration amplitude.

    Uses the first *baseline_window_sec* seconds of data, excluding
    any samples where the motion score exceeds the threshold.

    Parameters
    ──────────
    rr_amplitude     : 1‑D array of respiration amplitudes (breath‐wave
                       envelope or peak‐to‐peak per sample).
    timestamps       : 1‑D array of timestamps in seconds (monotonic).
    motion_scores    : optional 1‑D array of normalised motion scores
                       (0 = no motion, 1 = maximum motion).
    baseline_window_sec : how many seconds to use for baseline.
    baseline_percentile : which percentile to report as baseline amplitude.
    motion_threshold    : motion score above this masks the sample.
    sampling_rate       : samples per second (used as fallback if
                          timestamps are absent).

    Returns
    ───────
    baseline : float – the reference amplitude.
    """
    rr_amplitude = np.asarray(rr_amplitude, dtype=float)
    timestamps = np.asarray(timestamps, dtype=float)

    # select first N seconds
    t0 = timestamps[0] if len(timestamps) else 0.0
    mask = timestamps <= t0 + baseline_window_sec

    if motion_scores is not None:
        motion_scores = np.asarray(motion_scores, dtype=float)
        mask &= motion_scores < motion_threshold

    segment = rr_amplitude[mask]
    if len(segment) < 5:
        # fall back to entire signal (excluding motion)
        segment = rr_amplitude if motion_scores is None else rr_amplitude[motion_scores < motion_threshold]

    if len(segment) == 0:
        return 1.0  # safe fallback

    return float(np.percentile(np.abs(segment), baseline_percentile))


# ────────────────────────────────────────────────────────────────────
#  MOTION MASKING
# ────────────────────────────────────────────────────────────────────

def mask_motion_segments(
    motion_scores: np.ndarray,
    n_epochs: int,
    epoch_len: int,
    overlap_len: int,
    motion_threshold: float = CFG.MOTION_SCORE_THRESHOLD,
    guard_epochs: int = CFG.MOTION_GUARD_EPOCHS,
) -> np.ndarray:
    """
    Produce a boolean mask (True = motion artifact) per epoch.

    Parameters
    ──────────
    motion_scores    : 1‑D array of per‑sample motion scores.
    n_epochs         : total number of epochs.
    epoch_len        : samples per epoch.
    overlap_len      : overlap in samples.
    motion_threshold : threshold above which an epoch is motion.
    guard_epochs     : extra epochs masked around a detected motion epoch.

    Returns
    ───────
    motion_mask : 1‑D boolean array of length *n_epochs*.
    """
    motion_scores = np.asarray(motion_scores, dtype=float)
    indices = _epoch_indices(len(motion_scores), epoch_len, overlap_len)
    raw_mask = np.zeros(len(indices), dtype=bool)

    for k, (s, e) in enumerate(indices):
        epoch_motion = motion_scores[s:e]
        mean_motion = np.mean(epoch_motion)
        max_motion = np.max(epoch_motion) if len(epoch_motion) else 0.0
        # flag if either mean or peak exceeds threshold
        if mean_motion >= motion_threshold or max_motion >= motion_threshold * 1.5:
            raw_mask[k] = True

    # apply guard epochs
    guarded = raw_mask.copy()
    for k in range(len(guarded)):
        if raw_mask[k]:
            lo = max(0, k - guard_epochs)
            hi = min(len(guarded), k + guard_epochs + 1)
            guarded[lo:hi] = True

    return guarded[:n_epochs]


# ────────────────────────────────────────────────────────────────────
#  MAIN DETECTION
# ────────────────────────────────────────────────────────────────────

def detect_sleep_events(
    rr_amplitude: np.ndarray,
    timestamps: np.ndarray,
    motion_scores: Optional[np.ndarray] = None,
    hr_values: Optional[np.ndarray] = None,
    sampling_rate: float = 20.0,
    epoch_duration_sec: float = CFG.EPOCH_DURATION_SEC,
    epoch_overlap_frac: float = CFG.EPOCH_OVERLAP_FRAC,
    amplitude_drop_threshold: float = CFG.AMPLITUDE_DROP_THRESHOLD,
    apnea_min_consecutive: int = CFG.APNEA_MIN_CONSECUTIVE,
    irregular_min_consecutive: int = CFG.IRREGULAR_MIN_CONSECUTIVE,
    motion_threshold: float = CFG.MOTION_SCORE_THRESHOLD,
    motion_guard_epochs: int = CFG.MOTION_GUARD_EPOCHS,
    baseline_window_sec: float = CFG.BASELINE_WINDOW_SEC,
    baseline_percentile: float = CFG.BASELINE_PERCENTILE,
) -> Dict:
    """
    Detect and label sleep breathing events from processed vital‐sign
    time series.

    Parameters
    ──────────
    rr_amplitude         : 1‑D array – respiration amplitude (e.g.
                           breath‐wave envelope).
    timestamps           : 1‑D array – time in seconds, monotonically
                           increasing.
    motion_scores        : optional 1‑D array – normalised motion
                           indicator (0–1).  If None, a zero‑array is
                           used (no motion masking).
    hr_values            : optional 1‑D array – heart rate in BPM.
    sampling_rate        : samples per second.
    (remaining kwargs)   : override any default from config.py.

    Returns
    ───────
    result : dict with keys
        "events"         – list[dict] per‐epoch event records
        "summary"        – dict with aggregate statistics
        "epoch_labels"   – np.ndarray of per‐epoch string labels
        "epoch_centers"  – np.ndarray of epoch centre timestamps
        "baseline_amplitude" – float
    """
    rr_amplitude = np.asarray(rr_amplitude, dtype=float)
    timestamps = np.asarray(timestamps, dtype=float)
    n_samples = len(rr_amplitude)

    if motion_scores is None:
        motion_scores = np.zeros(n_samples, dtype=float)
    else:
        motion_scores = np.asarray(motion_scores, dtype=float)

    if hr_values is not None:
        hr_values = np.asarray(hr_values, dtype=float)

    # ── Convert time parameters to samples ──────────────────────────
    epoch_len = int(epoch_duration_sec * sampling_rate)
    overlap_len = int(epoch_len * epoch_overlap_frac)
    epoch_indices = _epoch_indices(n_samples, epoch_len, overlap_len)
    n_epochs = len(epoch_indices)

    if n_epochs == 0:
        return {
            "events": [],
            "summary": _empty_summary(),
            "epoch_labels": np.array([]),
            "epoch_centers": np.array([]),
            "baseline_amplitude": 0.0,
        }

    # ── Baseline ────────────────────────────────────────────────────
    baseline = compute_baseline_rr(
        rr_amplitude, timestamps, motion_scores,
        baseline_window_sec=baseline_window_sec,
        baseline_percentile=baseline_percentile,
        motion_threshold=motion_threshold,
        sampling_rate=sampling_rate,
    )

    # ── Motion mask ─────────────────────────────────────────────────
    motion_mask = mask_motion_segments(
        motion_scores, n_epochs, epoch_len, overlap_len,
        motion_threshold=motion_threshold,
        guard_epochs=motion_guard_epochs,
    )

    # ── Per‐epoch amplitude & statistics ────────────────────────────
    epoch_amplitudes = np.zeros(n_epochs)
    epoch_rr_mean = np.zeros(n_epochs)
    epoch_rr_std = np.zeros(n_epochs)
    epoch_motion_mean = np.zeros(n_epochs)
    epoch_hr_mean = np.full(n_epochs, np.nan)
    epoch_centers = np.zeros(n_epochs)

    for k, (s, e) in enumerate(epoch_indices):
        seg = rr_amplitude[s:e]
        epoch_amplitudes[k] = _peak_amplitude(seg)
        epoch_rr_mean[k] = np.mean(seg)
        epoch_rr_std[k] = np.std(seg)
        epoch_motion_mean[k] = np.mean(motion_scores[s:e])
        epoch_centers[k] = np.mean(timestamps[s:e])
        if hr_values is not None:
            hr_seg = hr_values[s:e]
            valid = hr_seg[(hr_seg >= 30) & (hr_seg <= 200)]
            epoch_hr_mean[k] = np.mean(valid) if len(valid) else np.nan

    # ── Raw label per epoch ─────────────────────────────────────────
    #    "N" = Normal, "A" = Abnormal (amplitude drop), "M" = Motion
    raw_labels = np.full(n_epochs, "N", dtype="U1")
    threshold_amp = baseline * (1.0 - amplitude_drop_threshold)

    for k in range(n_epochs):
        if motion_mask[k]:
            raw_labels[k] = "M"
        elif epoch_amplitudes[k] < threshold_amp:
            raw_labels[k] = "A"  # abnormal

    # ── Merge consecutive abnormals into Irregular / Apnea ──────────
    event_labels = np.full(n_epochs, "Normal", dtype="U20")
    k = 0
    while k < n_epochs:
        if raw_labels[k] == "M":
            event_labels[k] = "Motion"
            k += 1
        elif raw_labels[k] == "A":
            # count consecutive abnormal epochs
            run_start = k
            while k < n_epochs and raw_labels[k] == "A":
                k += 1
            run_len = k - run_start
            if run_len >= apnea_min_consecutive:
                event_labels[run_start:k] = "Apnea"
            elif run_len >= irregular_min_consecutive:
                event_labels[run_start:k] = "Irregular"
            else:
                event_labels[run_start:k] = "Normal"
        else:
            k += 1

    # ── Build event records ─────────────────────────────────────────
    events: List[Dict] = []
    for k, (s, e) in enumerate(epoch_indices):
        ts_start = timestamps[s]
        ts_end = timestamps[min(e - 1, n_samples - 1)]
        rec = {
            "epoch_index": k,
            "timestamp_start": round(float(ts_start), 3),
            "timestamp_end": round(float(ts_end), 3),
            "event_type": str(event_labels[k]),
            "RR_mean": round(float(epoch_rr_mean[k]), 4),
            "RR_std": round(float(epoch_rr_std[k]), 4),
            "amplitude": round(float(epoch_amplitudes[k]), 4),
            "motion_score_mean": round(float(epoch_motion_mean[k]), 4),
        }
        if hr_values is not None:
            rec["HR_mean"] = round(float(epoch_hr_mean[k]), 2) if not np.isnan(epoch_hr_mean[k]) else None
        events.append(rec)

    # ── Summary statistics ──────────────────────────────────────────
    total_duration_sec = float(timestamps[-1] - timestamps[0]) if n_samples > 1 else 0.0
    total_hours = total_duration_sec / 3600.0 if total_duration_sec > 0 else 1.0

    label_counts = {lab: int(np.sum(event_labels == lab)) for lab in ["Normal", "Irregular", "Apnea", "Motion"]}
    label_time = {lab: label_counts[lab] * epoch_duration_sec for lab in label_counts}

    apnea_events_per_hour = label_counts["Apnea"] / total_hours if total_hours > 0 else 0.0

    severity = "Normal"
    for sev, thresh in sorted(CFG.SEVERITY_THRESHOLDS.items(), key=lambda x: x[1]):
        if apnea_events_per_hour <= thresh:
            severity = sev
            break
    else:
        severity = "Severe"

    summary = {
        "total_duration_sec": round(total_duration_sec, 2),
        "total_epochs": n_epochs,
        "baseline_amplitude": round(baseline, 4),
        "amplitude_threshold": round(threshold_amp, 4),
        "event_counts": label_counts,
        "event_time_sec": label_time,
        "apnea_events_per_hour": round(apnea_events_per_hour, 2),
        "severity": severity,
    }

    return {
        "events": events,
        "summary": summary,
        "epoch_labels": event_labels,
        "epoch_centers": epoch_centers,
        "baseline_amplitude": baseline,
    }


def _empty_summary() -> Dict:
    return {
        "total_duration_sec": 0,
        "total_epochs": 0,
        "baseline_amplitude": 0,
        "amplitude_threshold": 0,
        "event_counts": {"Normal": 0, "Irregular": 0, "Apnea": 0, "Motion": 0},
        "event_time_sec": {"Normal": 0, "Irregular": 0, "Apnea": 0, "Motion": 0},
        "apnea_events_per_hour": 0,
        "severity": "Normal",
    }
