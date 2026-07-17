"""
motion_posture/io_utils.py
──────────────────────────
Data loading from existing pipeline CSVs and output writers for the
motion & posture context pipeline.
"""

from __future__ import annotations
import csv, json, os, datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


# ────────────────────────────────────────────────────────────────────
#  INPUT LOADERS
# ────────────────────────────────────────────────────────────────────

def load_pipeline_csv(
    filepath: str,
    user_email: Optional[str] = None,
) -> Dict[str, np.ndarray]:
    """
    Load a *vital_signs_data_new*.csv produced by vitalsigns.py.

    Returns dict with keys:
        timestamps, chest_disp, breath_wave, heart_wave, combined,
        range_m, motion_scores, rr_bpm, hr_bpm
    """
    df = pd.read_csv(filepath, on_bad_lines="skip")
    df.columns = [c.strip() for c in df.columns]

    if user_email and "User" in df.columns:
        df = df[df["User"].str.strip().str.lower() == user_email.lower()]

    df = df.sort_values("SessionTime").reset_index(drop=True)

    timestamps = pd.to_numeric(df["SessionTime"], errors="coerce").values
    if np.any(np.isnan(timestamps)) or (len(timestamps) > 1 and np.any(np.diff(timestamps) < 0)):
        timestamps = np.arange(len(df)) / 20.0

    def _col(name):
        if name in df.columns:
            return pd.to_numeric(df[name], errors="coerce").fillna(0).values
        return np.zeros(len(df))

    chest_disp  = _col("ChestDisplacement")
    breath_wave = _col("BreathWaveform")
    heart_wave  = _col("HeartWaveform")
    combined    = _col("CombinedSignal")
    range_m     = _col("Range_m")
    rr_bpm      = _col("RespirationRate_BPM")
    hr_bpm      = _col("HeartRate_BPM")

    # Synthesise motion score (same logic as sleep_detection)
    motion_raw = np.abs(np.diff(chest_disp, prepend=chest_disp[0]))
    mx = np.percentile(motion_raw, 99) if len(motion_raw) > 1 else 1.0
    motion_scores = np.clip(motion_raw / max(mx, 1e-8), 0, 1)

    return {
        "timestamps":    timestamps,
        "chest_disp":    chest_disp,
        "breath_wave":   breath_wave,
        "heart_wave":    heart_wave,
        "combined":      combined,
        "range_m":       range_m,
        "motion_scores": motion_scores,
        "rr_bpm":        rr_bpm,
        "hr_bpm":        hr_bpm,
    }


def load_live_session_csv(filepath: str) -> Dict[str, np.ndarray]:
    """
    Load a *vital_signs_live_session.csv* from allframes.py.

    Returns the same dict structure as load_pipeline_csv.
    """
    df = pd.read_csv(filepath)
    df.columns = [c.strip() for c in df.columns]

    timestamps = df["time_sec"].astype(float).values

    def _col(name):
        if name in df.columns:
            return pd.to_numeric(df[name], errors="coerce").fillna(0).values
        return np.zeros(len(df))

    chest_disp  = _col("chest_displacement")
    breath_wave = _col("breathing_wave")
    heart_wave  = _col("heart_wave")
    phase       = _col("phase")

    # combined signal approximation
    combined = 0.5 * chest_disp + 0.3 * breath_wave + 0.2 * heart_wave

    range_m = np.zeros(len(df))  # not available in live format

    motion_raw = np.abs(np.diff(chest_disp, prepend=chest_disp[0]))
    mx = np.percentile(motion_raw, 99) if len(motion_raw) > 1 else 1.0
    motion_scores = np.clip(motion_raw / max(mx, 1e-8), 0, 1)

    return {
        "timestamps":    timestamps,
        "chest_disp":    chest_disp,
        "breath_wave":   breath_wave,
        "heart_wave":    heart_wave,
        "combined":      combined,
        "range_m":       range_m,
        "motion_scores": motion_scores,
        "rr_bpm":        np.zeros(len(df)),
        "hr_bpm":        np.zeros(len(df)),
    }


# ────────────────────────────────────────────────────────────────────
#  OUTPUT WRITERS
# ────────────────────────────────────────────────────────────────────

def save_posture_motion_report(
    context_result: Dict,
    motion_result: Dict,
    posture_records: List[Dict],
    output_dir: str,
    prefix: str = "motion_posture_report",
    save_csv: bool = True,
    save_json: bool = True,
) -> Dict[str, str]:
    """
    Persist motion & posture context results to CSV and JSON.

    Returns dict mapping format → file path.
    """
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    paths: Dict[str, str] = {}

    if save_csv:
        csv_path = os.path.join(output_dir, f"{prefix}_{ts}.csv")
        _write_combined_csv(context_result["combined_timeline"], csv_path)
        paths["csv"] = csv_path

    if save_json:
        json_path = os.path.join(output_dir, f"{prefix}_{ts}.json")
        payload = {
            "generated_at": datetime.datetime.now().isoformat(),
            "session_stats": context_result["session_stats"],
            "event_annotations": context_result["event_annotations"],
            "combined_timeline": context_result["combined_timeline"],
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        paths["json"] = json_path

    return paths


def _write_combined_csv(records: List[Dict], path: str) -> None:
    """Write combined timeline to CSV."""
    if not records:
        return
    fieldnames = list(records[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
