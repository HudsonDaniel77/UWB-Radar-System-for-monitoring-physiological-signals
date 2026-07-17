"""
validation/event_metrics.py
───────────────────────────
Event-level detection performance metrics.

Compares predicted respiratory events (from the radar system) against
ground-truth events (from PSG or another reference).

Metrics produced
────────────────
• True Positives (TP), False Positives (FP), False Negatives (FN)
• Precision, Recall (Sensitivity), F1-score
• Event-duration error statistics (MAE, RMSE, bias)
• Per-event-type breakdown

Event matching
──────────────
Two events are matched if their temporal overlap ≥ OVERLAP_THRESHOLD
(intersection-over-union) **or** their midpoints are within
MATCH_TOLERANCE_SEC.  Each reference event is matched to at most one
predicted event (greedy, closest-first).
"""

from __future__ import annotations
import numpy as np
from typing import Dict, List, Optional, Tuple

from . import config as CFG


# ────────────────────────────────────────────────────────────────────
#  EVENT MATCHING
# ────────────────────────────────────────────────────────────────────

def _event_midpoint(evt: Dict) -> float:
    return (evt["timestamp_start"] + evt["timestamp_end"]) / 2.0


def _event_duration(evt: Dict) -> float:
    return max(evt["timestamp_end"] - evt["timestamp_start"], 0.0)


def _overlap_iou(a: Dict, b: Dict) -> float:
    """
    Intersection-over-union of two time intervals.

    IoU = overlap / (union)
    """
    s = max(a["timestamp_start"], b["timestamp_start"])
    e = min(a["timestamp_end"], b["timestamp_end"])
    intersection = max(0.0, e - s)
    dur_a = _event_duration(a)
    dur_b = _event_duration(b)
    union = dur_a + dur_b - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def match_events(
    ref_events: List[Dict],
    pred_events: List[Dict],
    tolerance_sec: float = CFG.MATCH_TOLERANCE_SEC,
    overlap_threshold: float = CFG.OVERLAP_THRESHOLD,
) -> Tuple[List[Tuple[Dict, Dict]], List[Dict], List[Dict]]:
    """
    Match predicted events to reference events.

    Uses greedy matching: for each reference event, find the closest
    unmatched predicted event that satisfies the overlap or tolerance
    criterion.

    Parameters
    ──────────
    ref_events         : ground-truth events
    pred_events        : system-predicted events
    tolerance_sec      : max midpoint distance for matching
    overlap_threshold  : min IoU for matching

    Returns
    ───────
    matched    : list of (ref, pred) tuples  → True Positives
    unmatched_ref  : list of ref events with no match  → False Negatives
    unmatched_pred : list of pred events with no match → False Positives
    """
    used_pred = set()
    matched: List[Tuple[Dict, Dict]] = []
    unmatched_ref: List[Dict] = []

    # Sort reference by start time
    sorted_ref = sorted(ref_events, key=lambda e: e["timestamp_start"])

    for ref in sorted_ref:
        best_idx = -1
        best_score = -1.0
        ref_mid = _event_midpoint(ref)

        for j, pred in enumerate(pred_events):
            if j in used_pred:
                continue

            iou = _overlap_iou(ref, pred)
            mid_dist = abs(_event_midpoint(pred) - ref_mid)

            if iou >= overlap_threshold or mid_dist <= tolerance_sec:
                # Score: prefer higher IoU, then smaller distance
                score = iou * 1000 + (1.0 / (1.0 + mid_dist))
                if score > best_score:
                    best_score = score
                    best_idx = j

        if best_idx >= 0:
            matched.append((ref, pred_events[best_idx]))
            used_pred.add(best_idx)
        else:
            unmatched_ref.append(ref)

    unmatched_pred = [p for j, p in enumerate(pred_events) if j not in used_pred]

    return matched, unmatched_ref, unmatched_pred


# ────────────────────────────────────────────────────────────────────
#  EVENT DETECTION METRICS
# ────────────────────────────────────────────────────────────────────

def compute_event_metrics(
    ref_events: List[Dict],
    pred_events: List[Dict],
    event_types: Optional[List[str]] = None,
    tolerance_sec: float = CFG.MATCH_TOLERANCE_SEC,
    overlap_threshold: float = CFG.OVERLAP_THRESHOLD,
) -> Dict:
    """
    Compute event-level detection performance.

    Parameters
    ──────────
    ref_events        : ground-truth event list
    pred_events       : system-predicted event list
    event_types       : if provided, filter to only these event types
                        (e.g. ["Apnea", "Hypopnea"])
    tolerance_sec     : matching tolerance
    overlap_threshold : matching IoU threshold

    Returns
    ───────
    dict with:
        tp, fp, fn, precision, recall, f1,
        duration_errors (mae, rmse, bias, errors list),
        per_type  (same metrics broken down by event type)
    """
    # Filter by event types if specified
    if event_types:
        type_set = set(event_types)
        ref_filtered = [e for e in ref_events if e["event_type"] in type_set]
        pred_filtered = [e for e in pred_events if e["event_type"] in type_set]
    else:
        ref_filtered = ref_events
        pred_filtered = pred_events

    matched, unmatched_ref, unmatched_pred = match_events(
        ref_filtered, pred_filtered, tolerance_sec, overlap_threshold,
    )

    tp = len(matched)
    fp = len(unmatched_pred)
    fn = len(unmatched_ref)

    precision = tp / max(tp + fp, 1)
    recall    = tp / max(tp + fn, 1)
    f1 = (2 * precision * recall / max(precision + recall, 1e-12)
          if (precision + recall) > 0 else 0.0)

    # Duration error analysis
    dur_errors = _duration_errors(matched)

    # Per-type breakdown
    all_types = set(e["event_type"] for e in ref_filtered + pred_filtered)
    per_type: Dict[str, Dict] = {}
    for etype in sorted(all_types):
        ref_t = [e for e in ref_filtered if e["event_type"] == etype]
        pred_t = [e for e in pred_filtered if e["event_type"] == etype]
        m_t, ur_t, up_t = match_events(ref_t, pred_t, tolerance_sec, overlap_threshold)
        tp_t = len(m_t)
        fp_t = len(up_t)
        fn_t = len(ur_t)
        prec_t = tp_t / max(tp_t + fp_t, 1)
        rec_t  = tp_t / max(tp_t + fn_t, 1)
        f1_t   = (2 * prec_t * rec_t / max(prec_t + rec_t, 1e-12)
                  if (prec_t + rec_t) > 0 else 0.0)
        per_type[etype] = {
            "tp": tp_t, "fp": fp_t, "fn": fn_t,
            "precision": round(prec_t, 4),
            "recall":    round(rec_t, 4),
            "f1":        round(f1_t, 4),
            "ref_count": len(ref_t),
            "pred_count": len(pred_t),
        }

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision":  round(precision, 4),
        "recall":     round(recall, 4),
        "f1":         round(f1, 4),
        "sensitivity": round(recall, 4),
        "specificity": None,  # requires TN count (epoch-level)
        "ref_total":  len(ref_filtered),
        "pred_total": len(pred_filtered),
        "duration_errors": dur_errors,
        "per_type": per_type,
    }


# ────────────────────────────────────────────────────────────────────
#  EPOCH-LEVEL METRICS (for specificity)
# ────────────────────────────────────────────────────────────────────

def compute_epoch_metrics(
    ref_labels: List[str],
    pred_labels: List[str],
    positive_labels: Optional[List[str]] = None,
) -> Dict:
    """
    Compute epoch-level binary classification metrics.

    Parameters
    ──────────
    ref_labels      : ground-truth label per epoch
    pred_labels     : predicted label per epoch
    positive_labels : labels treated as "positive" (e.g. ["Apnea", "Irregular"])
                      Everything else is "negative".

    Returns
    ───────
    dict with tp, tn, fp, fn, sensitivity, specificity, precision, recall, f1
    """
    if positive_labels is None:
        positive_labels = ["Apnea", "Irregular", "Hypopnea"]

    pos = set(positive_labels)
    n = min(len(ref_labels), len(pred_labels))

    tp = tn = fp = fn = 0
    for i in range(n):
        r_pos = ref_labels[i] in pos
        p_pos = pred_labels[i] in pos
        if r_pos and p_pos:
            tp += 1
        elif not r_pos and not p_pos:
            tn += 1
        elif not r_pos and p_pos:
            fp += 1
        else:
            fn += 1

    sensitivity = tp / max(tp + fn, 1)
    specificity = tn / max(tn + fp, 1)
    precision   = tp / max(tp + fp, 1)
    recall      = sensitivity
    f1 = (2 * precision * recall / max(precision + recall, 1e-12)
          if (precision + recall) > 0 else 0.0)

    return {
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "sensitivity":  round(sensitivity, 4),
        "specificity":  round(specificity, 4),
        "precision":    round(precision, 4),
        "recall":       round(recall, 4),
        "f1":           round(f1, 4),
        "total_epochs": n,
    }


# ────────────────────────────────────────────────────────────────────
#  DURATION ERROR ANALYSIS
# ────────────────────────────────────────────────────────────────────

def _duration_errors(matched: List[Tuple[Dict, Dict]]) -> Dict:
    """
    Compute duration error statistics for matched event pairs.

    error = pred_duration − ref_duration  (positive = over-estimation)
    """
    if not matched:
        return {"mae": 0.0, "rmse": 0.0, "bias": 0.0, "n": 0, "errors": []}

    errors = []
    for ref, pred in matched:
        ref_dur  = _event_duration(ref)
        pred_dur = _event_duration(pred)
        errors.append(pred_dur - ref_dur)

    errors_arr = np.array(errors)
    mae  = float(np.mean(np.abs(errors_arr)))
    rmse = float(np.sqrt(np.mean(errors_arr ** 2)))
    bias = float(np.mean(errors_arr))

    return {
        "mae":    round(mae, 3),
        "rmse":   round(rmse, 3),
        "bias":   round(bias, 3),
        "n":      len(errors),
        "errors": [round(e, 3) for e in errors],
    }
