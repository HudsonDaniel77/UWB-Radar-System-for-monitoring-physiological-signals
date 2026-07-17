"""
validation/io_utils.py
──────────────────────
I/O utilities for loading reference (PSG) data, system outputs, and
saving validation reports.

Supported input formats
───────────────────────
PSG reference
    CSV/JSON with columns:
        subject_id, event_type, timestamp_start, timestamp_end
        (optional: ahi, severity, sleep_stages)

System output
    JSON produced by sleep_detection / sleep_staging modules, or
    CSV with the same epoch-record schema.
"""

from __future__ import annotations
import csv, json, os, datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# ────────────────────────────────────────────────────────────────────
#  PSG / REFERENCE LOADERS
# ────────────────────────────────────────────────────────────────────

def load_psg_events_csv(path: str) -> List[Dict]:
    """
    Load PSG ground-truth events from a CSV file.

    Expected columns (case-insensitive):
        subject_id, event_type, timestamp_start, timestamp_end
    Optional:
        duration, severity, notes

    Returns list of event dicts.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"PSG reference file not found: {path}")

    events: List[Dict] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # normalise headers to lowercase
        reader.fieldnames = [h.strip().lower() for h in (reader.fieldnames or [])]
        for row in reader:
            evt: Dict[str, Any] = {}
            evt["subject_id"] = row.get("subject_id", "unknown")
            evt["event_type"] = _normalise_event_type(row.get("event_type", ""))
            try:
                evt["timestamp_start"] = float(row.get("timestamp_start", 0))
            except (ValueError, TypeError):
                evt["timestamp_start"] = 0.0
            try:
                evt["timestamp_end"] = float(row.get("timestamp_end", 0))
            except (ValueError, TypeError):
                evt["timestamp_end"] = 0.0
            evt["duration"] = evt["timestamp_end"] - evt["timestamp_start"]
            evt["severity"] = row.get("severity", "")
            evt["notes"] = row.get("notes", "")
            events.append(evt)
    return events


def load_psg_events_json(path: str) -> List[Dict]:
    """
    Load PSG ground-truth events from a JSON file.

    Expected structure:
        [ {subject_id, event_type, timestamp_start, timestamp_end, ...}, ...]
    or:
        { "events": [ ... ] }
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"PSG reference file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        raw_events = data
    elif isinstance(data, dict):
        raw_events = data.get("events", data.get("epoch_records", []))
    else:
        raw_events = []

    events: List[Dict] = []
    for row in raw_events:
        evt: Dict[str, Any] = {
            "subject_id":      row.get("subject_id", "unknown"),
            "event_type":      _normalise_event_type(row.get("event_type", "")),
            "timestamp_start": float(row.get("timestamp_start", 0)),
            "timestamp_end":   float(row.get("timestamp_end", 0)),
        }
        evt["duration"] = evt["timestamp_end"] - evt["timestamp_start"]
        evt["severity"] = row.get("severity", "")
        events.append(evt)
    return events


def load_psg_stages_csv(path: str) -> List[Dict]:
    """
    Load PSG sleep-stage annotations from a CSV file.

    Expected columns:
        subject_id, epoch_index, timestamp_start, timestamp_end, stage
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"PSG stages file not found: {path}")

    stages: List[Dict] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [h.strip().lower() for h in (reader.fieldnames or [])]
        for row in reader:
            stages.append({
                "subject_id":      row.get("subject_id", "unknown"),
                "epoch_index":     int(row.get("epoch_index", 0)),
                "timestamp_start": float(row.get("timestamp_start", 0)),
                "timestamp_end":   float(row.get("timestamp_end", 0)),
                "stage":           row.get("stage", "Unknown"),
            })
    return stages


def load_psg_ahi_csv(path: str) -> List[Dict]:
    """
    Load per-subject PSG AHI scores from a CSV.

    Expected columns: subject_id, ahi  (optional: severity, total_sleep_time_hr)
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"PSG AHI file not found: {path}")

    records: List[Dict] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [h.strip().lower() for h in (reader.fieldnames or [])]
        for row in reader:
            records.append({
                "subject_id": row.get("subject_id", "unknown"),
                "ahi":        float(row.get("ahi", 0)),
                "severity":   row.get("severity", ""),
                "total_sleep_time_hr": float(row.get("total_sleep_time_hr", 0))
                    if row.get("total_sleep_time_hr") else None,
            })
    return records


# ────────────────────────────────────────────────────────────────────
#  SYSTEM OUTPUT LOADERS
# ────────────────────────────────────────────────────────────────────

def load_system_events_json(path: str) -> List[Dict]:
    """
    Load system-predicted events from a sleep_detection JSON report.

    The JSON is expected to have:
        { "events": [ {event_type, timestamp_start, timestamp_end, ...} ] }
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"System output file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw = data.get("events", data.get("epoch_records", []))
    events: List[Dict] = []
    for e in raw:
        events.append({
            "event_type":      _normalise_event_type(e.get("event_type", "")),
            "timestamp_start": float(e.get("timestamp_start", 0)),
            "timestamp_end":   float(e.get("timestamp_end", 0)),
            "confidence":      float(e.get("confidence", 1.0)),
        })
    return events


def load_system_stages_json(path: str) -> List[Dict]:
    """
    Load system-predicted sleep stages from a sleep_staging JSON report.

    Expected structure:
        { "epoch_records": [ {epoch_index, predicted_stage, timestamp_start, ...} ] }
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"System stages file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw = data.get("epoch_records", [])
    stages: List[Dict] = []
    for r in raw:
        stages.append({
            "epoch_index":     int(r.get("epoch_index", 0)),
            "stage":           r.get("predicted_stage", r.get("stage", "Unknown")),
            "timestamp_start": float(r.get("timestamp_start", 0)),
            "timestamp_end":   float(r.get("timestamp_end", 0)),
            "confidence":      float(r.get("confidence", 1.0)),
        })
    return stages


def load_system_summary_json(path: str) -> Dict:
    """
    Load a full system output JSON and return the summary dict.

    Returns dict with keys like apnea_events_per_hour, severity, etc.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"System summary file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    return data.get("summary", data)


# ────────────────────────────────────────────────────────────────────
#  HELPERS
# ────────────────────────────────────────────────────────────────────

def _normalise_event_type(raw: str) -> str:
    """Map various event-type spellings to canonical labels."""
    s = raw.strip().lower()
    if s in ("apnea", "obstructive_apnea", "osa", "central_apnea"):
        return "Apnea"
    if s in ("hypopnea", "hyp"):
        return "Hypopnea"
    if s in ("irregular", "abnormal"):
        return "Irregular"
    if s in ("normal", ""):
        return "Normal"
    if s in ("motion", "artifact"):
        return "Motion"
    return raw.strip()


def save_validation_report(
    results: Dict,
    output_dir: str,
    prefix: str = "validation_report",
) -> Dict[str, str]:
    """
    Save validation results to CSV + JSON.

    Parameters
    ──────────
    results    : dict with keys like "per_subject", "aggregate",
                 "event_metrics", "ahi_comparison", etc.
    output_dir : target directory
    prefix     : filename prefix

    Returns
    ───────
    paths : dict mapping format → file path
    """
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    paths: Dict[str, str] = {}

    # JSON
    json_path = os.path.join(output_dir, f"{prefix}_{ts}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=_json_default)
    paths["json"] = json_path

    # CSV – per-subject table
    per_subj = results.get("per_subject", [])
    if per_subj:
        csv_path = os.path.join(output_dir, f"{prefix}_per_subject_{ts}.csv")
        _write_dicts_csv(per_subj, csv_path)
        paths["csv"] = csv_path

    return paths


def _write_dicts_csv(rows: List[Dict], path: str) -> None:
    """Write a list of flat dicts to a CSV file."""
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _json_default(obj: Any) -> Any:
    """JSON fallback serialiser for numpy types."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)
