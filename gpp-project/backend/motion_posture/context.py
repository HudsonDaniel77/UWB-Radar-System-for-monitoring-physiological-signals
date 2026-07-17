"""
motion_posture/context.py
─────────────────────────
Context fusion: align posture + motion labels with sleep‐event
detection results to produce contextual annotations.
"""

from __future__ import annotations
import numpy as np
from typing import Dict, List, Optional

from . import config as CFG


# ────────────────────────────────────────────────────────────────────
#  ALIGN CONTEXT WITH EVENTS
# ────────────────────────────────────────────────────────────────────

def align_context_with_events(
    motion_records: List[Dict],
    posture_records: List[Dict],
    sleep_events: Optional[List[Dict]] = None,
    look_back_sec: float = CFG.EVENT_LOOK_BACK_SEC,
    look_ahead_sec: float = CFG.EVENT_LOOK_AHEAD_SEC,
) -> Dict:
    """
    Merge motion, posture, and (optional) sleep‑event timelines into
    a unified context report.

    Parameters
    ──────────
    motion_records  : list of dicts from classify_motion_segments()
    posture_records : list of dicts with timestamp_start/end + posture_label
    sleep_events    : list of dicts from sleep_detection.detect_sleep_events()
                      (optional – if None, sleep context is skipped)
    look_back_sec   : seconds before a sleep event to scan for motion
    look_ahead_sec  : seconds after a sleep event to scan for motion

    Returns
    ───────
    result : dict with keys
        "combined_timeline" – list[dict] merged epoch records
        "event_annotations" – list[dict] per‑sleep‑event context
        "session_stats"     – dict aggregate statistics
    """

    # ── Build combined timeline ─────────────────────────────────────
    combined: List[Dict] = []
    n_epochs = max(len(motion_records), len(posture_records))

    for k in range(n_epochs):
        rec: Dict = {}

        if k < len(motion_records):
            m = motion_records[k]
            rec["epoch_index"] = m.get("epoch_index", k)
            rec["timestamp_start"] = m["timestamp_start"]
            rec["timestamp_end"] = m["timestamp_end"]
            rec["motion_type"] = m["motion_type"]
            rec["motion_score"] = m["motion_score"]
        else:
            rec["epoch_index"] = k
            rec["motion_type"] = "N/A"
            rec["motion_score"] = None

        if k < len(posture_records):
            p = posture_records[k]
            rec["posture_label"] = p.get("posture_label", "Unknown")
            rec["posture_confidence"] = p.get("posture_confidence", 0.0)
            if "timestamp_start" not in rec:
                rec["timestamp_start"] = p["timestamp_start"]
                rec["timestamp_end"] = p["timestamp_end"]
        else:
            rec["posture_label"] = "Unknown"
            rec["posture_confidence"] = 0.0

        rec["associated_sleep_event"] = None
        combined.append(rec)

    # ── Associate sleep events with nearest posture/motion epochs ───
    event_annotations: List[Dict] = []

    if sleep_events:
        for sev in sleep_events:
            if sev.get("event_type", "Normal") == "Normal":
                continue  # skip normal epochs for annotations

            ev_start = sev["timestamp_start"]
            ev_end = sev["timestamp_end"]

            # find overlapping/nearest motion & posture
            posture_at_event = _find_label_at_time(
                posture_records, "posture_label", ev_start, ev_end,
            )
            motion_before = _find_motion_before(
                motion_records, ev_start, look_back_sec,
            )
            motion_after = _find_motion_after(
                motion_records, ev_end, look_ahead_sec,
            )

            annotation = {
                "event_type": sev["event_type"],
                "event_start": ev_start,
                "event_end": ev_end,
                "posture_during": posture_at_event,
                "motion_before": motion_before,
                "motion_after": motion_after,
                "description": _build_description(
                    sev["event_type"], posture_at_event,
                    motion_before, motion_after,
                ),
                "RR_mean": sev.get("RR_mean"),
                "HR_mean": sev.get("HR_mean"),
            }
            event_annotations.append(annotation)

            # Mark combined timeline epochs that overlap with this event
            for rec in combined:
                if rec.get("timestamp_start") is not None:
                    if (rec["timestamp_start"] <= ev_end and
                            rec["timestamp_end"] >= ev_start):
                        rec["associated_sleep_event"] = sev["event_type"]

    # ── Session‑level aggregate statistics ──────────────────────────
    session_stats = _compute_session_stats(
        combined, event_annotations, posture_records,
    )

    return {
        "combined_timeline": combined,
        "event_annotations": event_annotations,
        "session_stats": session_stats,
    }


# ────────────────────────────────────────────────────────────────────
#  PRIVATE HELPERS
# ────────────────────────────────────────────────────────────────────

def _find_label_at_time(
    records: List[Dict], key: str, t_start: float, t_end: float,
) -> str:
    """Find the most common label in records overlapping [t_start, t_end]."""
    labels = []
    for r in records:
        rs = r.get("timestamp_start", 0)
        re_ = r.get("timestamp_end", 0)
        if rs <= t_end and re_ >= t_start:
            labels.append(r.get(key, "Unknown"))
    if not labels:
        return "Unknown"
    # majority vote
    from collections import Counter
    return Counter(labels).most_common(1)[0][0]


def _find_motion_before(
    motion_records: List[Dict], event_start: float, look_back: float,
) -> str:
    """Find the dominant motion type in the look‑back window."""
    labels = []
    for r in motion_records:
        if r["timestamp_end"] <= event_start and r["timestamp_end"] >= event_start - look_back:
            labels.append(r["motion_type"])
    if not labels:
        return "N/A"
    from collections import Counter
    return Counter(labels).most_common(1)[0][0]


def _find_motion_after(
    motion_records: List[Dict], event_end: float, look_ahead: float,
) -> str:
    """Find the dominant motion type in the look‑ahead window."""
    labels = []
    for r in motion_records:
        if r["timestamp_start"] >= event_end and r["timestamp_start"] <= event_end + look_ahead:
            labels.append(r["motion_type"])
    if not labels:
        return "N/A"
    from collections import Counter
    return Counter(labels).most_common(1)[0][0]


def _build_description(
    event_type: str, posture: str, motion_before: str, motion_after: str,
) -> str:
    """Generate a human‑readable contextual annotation."""
    parts = [f"{event_type} event occurred"]

    if posture != "Unknown":
        parts.append(f"during {posture} posture")

    if motion_before not in ("N/A", "Still"):
        parts.append(f"(preceded by {motion_before})")

    if motion_after not in ("N/A", "Still"):
        parts.append(f"(followed by {motion_after})")

    return " ".join(parts) + "."


def _compute_session_stats(
    combined: List[Dict],
    annotations: List[Dict],
    posture_records: List[Dict],
) -> Dict:
    """Aggregate statistics for the session."""
    from collections import Counter

    # Posture distribution
    posture_counts = Counter(r.get("posture_label", "Unknown") for r in posture_records)
    total_posture = max(sum(posture_counts.values()), 1)
    posture_pct = {k: round(100 * v / total_posture, 1) for k, v in posture_counts.items()}

    # Motion distribution
    motion_counts = Counter(r.get("motion_type", "N/A") for r in combined if r.get("motion_type") != "N/A")

    # Event ↔ posture correlation
    event_posture = Counter()
    for ann in annotations:
        key = f"{ann['event_type']}_{ann['posture_during']}"
        event_posture[key] += 1

    return {
        "posture_distribution_pct": posture_pct,
        "posture_epoch_counts": dict(posture_counts),
        "motion_epoch_counts": dict(motion_counts),
        "event_posture_correlation": dict(event_posture),
        "total_annotations": len(annotations),
    }
