"""
validation/ahi.py
─────────────────
Apnea–Hypopnea Index (AHI) computation and comparison.

AHI = (total apnea + hypopnea events) / total sleep time (hours)

Severity classification per AASM:
    Normal   : AHI <  5
    Mild     : 5  ≤ AHI < 15
    Moderate : 15 ≤ AHI < 30
    Severe   : AHI ≥ 30

This module computes system AHI from detected events, compares it
against PSG AHI, and provides correlation / agreement statistics.
"""

from __future__ import annotations
import numpy as np
from typing import Dict, List, Optional, Tuple

from . import config as CFG


# ────────────────────────────────────────────────────────────────────
#  AHI COMPUTATION
# ────────────────────────────────────────────────────────────────────

def compute_ahi(
    events: List[Dict],
    total_sleep_time_hr: Optional[float] = None,
    total_duration_sec: Optional[float] = None,
    count_types: Optional[List[str]] = None,
) -> Dict:
    """
    Compute AHI from a list of detected events.

    Parameters
    ──────────
    events              : list of event dicts with "event_type"
    total_sleep_time_hr : total sleep time in hours (gold standard)
    total_duration_sec  : total recording duration in seconds (fallback)
    count_types         : event types counted towards AHI
                          (default: ["Apnea", "Hypopnea", "Irregular"])

    Returns
    ───────
    dict with: ahi, event_count, total_hours, severity, counts_by_type
    """
    if count_types is None:
        count_types = ["Apnea", "Hypopnea", "Irregular"]

    type_set = set(count_types)
    relevant = [e for e in events if e.get("event_type") in type_set]
    event_count = len(relevant)

    # Determine denominator in hours
    if total_sleep_time_hr and total_sleep_time_hr > 0:
        total_hours = total_sleep_time_hr
    elif total_duration_sec and total_duration_sec > 0:
        total_hours = total_duration_sec / 3600.0
    elif events:
        # Estimate from event timestamps
        all_starts = [e.get("timestamp_start", 0) for e in events]
        all_ends   = [e.get("timestamp_end", 0) for e in events]
        span_sec = max(max(all_ends) - min(all_starts), 1)
        total_hours = span_sec / 3600.0
    else:
        total_hours = 1.0   # avoid division by zero

    ahi = event_count / max(total_hours, 1e-6)

    # Counts by type
    counts_by_type: Dict[str, int] = {}
    for t in count_types:
        counts_by_type[t] = sum(1 for e in relevant if e["event_type"] == t)

    return {
        "ahi":             round(ahi, 2),
        "event_count":     event_count,
        "total_hours":     round(total_hours, 3),
        "severity":        classify_ahi_severity(ahi),
        "counts_by_type":  counts_by_type,
    }


# ────────────────────────────────────────────────────────────────────
#  AHI SEVERITY CLASSIFICATION
# ────────────────────────────────────────────────────────────────────

def classify_ahi_severity(ahi: float) -> str:
    """
    Classify AHI into a severity category.

    Returns one of: "Normal", "Mild", "Moderate", "Severe"
    """
    if ahi < CFG.AHI_SEVERITY_CUTOFFS["Normal"]:
        return "Normal"
    elif ahi < CFG.AHI_SEVERITY_CUTOFFS["Mild"]:
        return "Mild"
    elif ahi < CFG.AHI_SEVERITY_CUTOFFS["Moderate"]:
        return "Moderate"
    else:
        return "Severe"


# ────────────────────────────────────────────────────────────────────
#  AHI COMPARISON (SYSTEM vs. PSG)
# ────────────────────────────────────────────────────────────────────

def compare_ahi(
    subjects: List[Dict],
) -> Dict:
    """
    Compare system AHI against PSG AHI across multiple subjects.

    Parameters
    ──────────
    subjects : list of dicts, each with:
        "subject_id", "system_ahi", "psg_ahi"
        (optional: "system_severity", "psg_severity")

    Returns
    ───────
    dict with:
        per_subject   : list of per-subject comparison records
        aggregate     : aggregate statistics
        correlation   : Pearson r, Spearman rho
        ahi_errors    : error statistics (MAE, RMSE, bias)
        severity_agreement : confusion data for severity categories
    """
    sys_ahi  = np.array([s["system_ahi"] for s in subjects], dtype=float)
    psg_ahi  = np.array([s["psg_ahi"]    for s in subjects], dtype=float)

    # Per-subject records
    per_subject: List[Dict] = []
    for s in subjects:
        s_ahi = s["system_ahi"]
        p_ahi = s["psg_ahi"]
        per_subject.append({
            "subject_id":      s["subject_id"],
            "system_ahi":      round(s_ahi, 2),
            "psg_ahi":         round(p_ahi, 2),
            "ahi_error":       round(s_ahi - p_ahi, 2),
            "ahi_abs_error":   round(abs(s_ahi - p_ahi), 2),
            "system_severity": classify_ahi_severity(s_ahi),
            "psg_severity":    classify_ahi_severity(p_ahi),
            "severity_match":  classify_ahi_severity(s_ahi) == classify_ahi_severity(p_ahi),
        })

    # Error statistics
    errors = sys_ahi - psg_ahi
    mae  = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    bias = float(np.mean(errors))

    # Correlation
    corr = _correlation(sys_ahi, psg_ahi)

    # Severity category agreement
    sys_sev  = [classify_ahi_severity(a) for a in sys_ahi]
    psg_sev  = [classify_ahi_severity(a) for a in psg_ahi]
    sev_match = sum(1 for a, b in zip(sys_sev, psg_sev) if a == b)
    sev_total = len(subjects)

    return {
        "per_subject": per_subject,
        "aggregate": {
            "n_subjects":         len(subjects),
            "mean_system_ahi":    round(float(np.mean(sys_ahi)), 2),
            "mean_psg_ahi":       round(float(np.mean(psg_ahi)), 2),
            "std_system_ahi":     round(float(np.std(sys_ahi)), 2),
            "std_psg_ahi":        round(float(np.std(psg_ahi)), 2),
        },
        "ahi_errors": {
            "mae":  round(mae, 3),
            "rmse": round(rmse, 3),
            "bias": round(bias, 3),
        },
        "correlation": corr,
        "severity_agreement": {
            "exact_match_count": sev_match,
            "exact_match_pct":   round(100 * sev_match / max(sev_total, 1), 1),
            "n_subjects":        sev_total,
        },
    }


# ────────────────────────────────────────────────────────────────────
#  SCREENING PERFORMANCE AT SPECIFIC AHI CUTOFF
# ────────────────────────────────────────────────────────────────────

def screening_performance(
    subjects: List[Dict],
    cutoff: float = CFG.DEFAULT_SCREENING_CUTOFF,
) -> Dict:
    """
    Compute sensitivity / specificity for OSA screening at a given
    AHI cutoff.

    A subject is "positive" if AHI ≥ cutoff.

    Returns: tp, tn, fp, fn, sensitivity, specificity, ppv, npv
    """
    tp = tn = fp = fn = 0

    for s in subjects:
        ref_pos  = s["psg_ahi"] >= cutoff
        pred_pos = s["system_ahi"] >= cutoff
        if ref_pos and pred_pos:
            tp += 1
        elif not ref_pos and not pred_pos:
            tn += 1
        elif not ref_pos and pred_pos:
            fp += 1
        else:
            fn += 1

    sens = tp / max(tp + fn, 1)
    spec = tn / max(tn + fp, 1)
    ppv  = tp / max(tp + fp, 1)
    npv  = tn / max(tn + fn, 1)

    return {
        "cutoff":       cutoff,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "sensitivity":  round(sens, 4),
        "specificity":  round(spec, 4),
        "ppv":          round(ppv, 4),
        "npv":          round(npv, 4),
    }


# ────────────────────────────────────────────────────────────────────
#  CORRELATION HELPERS
# ────────────────────────────────────────────────────────────────────

def _correlation(x: np.ndarray, y: np.ndarray) -> Dict:
    """
    Compute Pearson and Spearman correlation between x and y.
    """
    from scipy import stats

    result: Dict = {}
    if len(x) >= 3:
        r, p = stats.pearsonr(x, y)
        result["pearson_r"] = round(float(r), 4)
        result["pearson_p"] = round(float(p), 6)

        rho, p_s = stats.spearmanr(x, y)
        result["spearman_rho"] = round(float(rho), 4)
        result["spearman_p"]   = round(float(p_s), 6)
    else:
        result["pearson_r"]    = None
        result["pearson_p"]    = None
        result["spearman_rho"] = None
        result["spearman_p"]   = None

    return result
