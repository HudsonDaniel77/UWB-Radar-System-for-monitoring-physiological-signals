"""
validation/agreement.py
───────────────────────
Statistical agreement and reliability analyses.

• Bland–Altman analysis (limits of agreement)
• Intra-class correlation coefficient  (ICC)
• Confusion matrix construction for categorical variables
• Cohen's Kappa for inter-rater agreement
"""

from __future__ import annotations
import numpy as np
from typing import Dict, List, Optional, Tuple

from . import config as CFG


# ────────────────────────────────────────────────────────────────────
#  BLAND–ALTMAN ANALYSIS
# ────────────────────────────────────────────────────────────────────

def bland_altman(
    system_values: np.ndarray,
    reference_values: np.ndarray,
    ci_z: float = CFG.BLAND_ALTMAN_CI,
) -> Dict:
    """
    Bland–Altman analysis for numeric score comparison.

    For each pair (system, reference):
        mean_pair  = (system + reference) / 2
        diff       = system − reference

    Returns
    ───────
    dict with:
        mean_diff          : mean of differences (bias)
        std_diff           : std of differences
        upper_loa          : mean_diff + ci_z * std_diff
        lower_loa          : mean_diff − ci_z * std_diff
        ci_z               : z-score used (default 1.96 for 95%)
        means              : array of pair means
        diffs              : array of differences
        n                  : sample count
        pct_within_loa     : % of points within limits of agreement
    """
    sys = np.asarray(system_values, dtype=float)
    ref = np.asarray(reference_values, dtype=float)

    if len(sys) != len(ref):
        raise ValueError("system_values and reference_values must have same length")

    diffs = sys - ref
    means = (sys + ref) / 2.0

    mean_diff = float(np.mean(diffs))
    std_diff  = float(np.std(diffs, ddof=1)) if len(diffs) > 1 else 0.0

    upper_loa = mean_diff + ci_z * std_diff
    lower_loa = mean_diff - ci_z * std_diff

    within = np.sum((diffs >= lower_loa) & (diffs <= upper_loa))
    pct_within = float(within / max(len(diffs), 1) * 100)

    return {
        "mean_diff":       round(mean_diff, 4),
        "std_diff":        round(std_diff, 4),
        "upper_loa":       round(upper_loa, 4),
        "lower_loa":       round(lower_loa, 4),
        "ci_z":            ci_z,
        "means":           means.tolist(),
        "diffs":           diffs.tolist(),
        "n":               len(diffs),
        "pct_within_loa":  round(pct_within, 1),
    }


# ────────────────────────────────────────────────────────────────────
#  INTRA-CLASS CORRELATION COEFFICIENT (ICC)
# ────────────────────────────────────────────────────────────────────

def compute_icc(
    system_values: np.ndarray,
    reference_values: np.ndarray,
) -> Dict:
    """
    Compute ICC(2,1) — two-way random, single measures, absolute
    agreement — for comparing system vs. reference numeric scores.

    Uses a two-way ANOVA decomposition:
        ICC(2,1) = (MS_subjects − MS_error) /
                   (MS_subjects + (k−1)*MS_error + k*(MS_raters−MS_error)/n)

    where k = 2 (two raters: system, reference), n = number of subjects.

    Returns
    ───────
    dict with: icc, ms_subjects, ms_raters, ms_error, n
    """
    sys = np.asarray(system_values, dtype=float)
    ref = np.asarray(reference_values, dtype=float)
    n = len(sys)
    k = 2  # two raters

    if n < 3:
        return {"icc": None, "n": n, "note": "Insufficient samples (need ≥ 3)"}

    # Stack as (n, 2) matrix
    data = np.column_stack([sys, ref])

    # Grand mean
    grand_mean = np.mean(data)

    # Subject means (row means)
    subj_means = np.mean(data, axis=1)
    # Rater means (column means)
    rater_means = np.mean(data, axis=0)

    # Sum of squares
    ss_total   = np.sum((data - grand_mean) ** 2)
    ss_subjects = k * np.sum((subj_means - grand_mean) ** 2)
    ss_raters  = n * np.sum((rater_means - grand_mean) ** 2)
    ss_error   = ss_total - ss_subjects - ss_raters

    # Mean squares
    ms_subjects = ss_subjects / max(n - 1, 1)
    ms_raters   = ss_raters / max(k - 1, 1)
    ms_error    = ss_error / max((n - 1) * (k - 1), 1)

    # ICC(2,1)
    numerator   = ms_subjects - ms_error
    denominator = (ms_subjects + (k - 1) * ms_error +
                   k * (ms_raters - ms_error) / max(n, 1))

    icc = numerator / denominator if denominator != 0 else 0.0

    return {
        "icc":          round(float(icc), 4),
        "ms_subjects":  round(float(ms_subjects), 4),
        "ms_raters":    round(float(ms_raters), 4),
        "ms_error":     round(float(ms_error), 4),
        "n":            n,
        "model":        CFG.ICC_MODEL,
    }


# ────────────────────────────────────────────────────────────────────
#  CONFUSION MATRIX
# ────────────────────────────────────────────────────────────────────

def build_confusion_matrix(
    y_true: List[str],
    y_pred: List[str],
    labels: Optional[List[str]] = None,
) -> Dict:
    """
    Build a confusion matrix from categorical labels.

    Parameters
    ──────────
    y_true  : ground-truth labels
    y_pred  : predicted labels
    labels  : ordered label list (default: sorted union)

    Returns
    ───────
    dict with: matrix (list of lists), labels, total, accuracy
    """
    if labels is None:
        labels = sorted(set(y_true) | set(y_pred))

    label_idx = {lbl: i for i, lbl in enumerate(labels)}
    n = len(labels)
    matrix = [[0] * n for _ in range(n)]

    total = min(len(y_true), len(y_pred))
    correct = 0
    for i in range(total):
        r_idx = label_idx.get(y_true[i])
        p_idx = label_idx.get(y_pred[i])
        if r_idx is not None and p_idx is not None:
            matrix[r_idx][p_idx] += 1
            if r_idx == p_idx:
                correct += 1

    accuracy = correct / max(total, 1)

    return {
        "matrix":   matrix,
        "labels":   labels,
        "total":    total,
        "accuracy": round(accuracy, 4),
    }


# ────────────────────────────────────────────────────────────────────
#  COHEN'S KAPPA
# ────────────────────────────────────────────────────────────────────

def cohens_kappa(
    y_true: List[str],
    y_pred: List[str],
    labels: Optional[List[str]] = None,
) -> Dict:
    """
    Compute Cohen's Kappa for inter-rater agreement.

    κ = (p_o − p_e) / (1 − p_e)

    Returns dict with: kappa, p_observed, p_expected, n
    """
    if labels is None:
        labels = sorted(set(y_true) | set(y_pred))

    n = min(len(y_true), len(y_pred))
    if n == 0:
        return {"kappa": 0.0, "p_observed": 0.0, "p_expected": 0.0, "n": 0}

    cm = build_confusion_matrix(y_true[:n], y_pred[:n], labels)
    mat = np.array(cm["matrix"])

    p_o = np.trace(mat) / max(n, 1)

    # Expected agreement
    row_sums = mat.sum(axis=1)
    col_sums = mat.sum(axis=0)
    p_e = float(np.sum(row_sums * col_sums)) / max(n ** 2, 1)

    kappa = (p_o - p_e) / max(1 - p_e, 1e-12) if p_e < 1.0 else 1.0

    return {
        "kappa":       round(float(kappa), 4),
        "p_observed":  round(float(p_o), 4),
        "p_expected":  round(float(p_e), 4),
        "n":           n,
    }
