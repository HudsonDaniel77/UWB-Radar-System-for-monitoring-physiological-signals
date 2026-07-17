"""
sleep_detection/io_utils.py
───────────────────────────
Input loading  – read pipeline CSVs (vital_signs_data_new*.csv or
                 vital_signs_live_session.csv) and produce the
                 numpy arrays expected by core.detect_sleep_events().

Output writing – save event CSV / JSON and summary reports.
"""

from __future__ import annotations
import csv, json, os, datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ────────────────────────────────────────────────────────────────────
#  INPUT LOADERS
# ────────────────────────────────────────────────────────────────────

def load_pipeline_csv(filepath: str,
                      user_email: Optional[str] = None,
                      ) -> Dict[str, np.ndarray]:
    """
    Load a *vital_signs_data_new*.csv produced by the existing
    vitalsigns.py pipeline.

    Columns expected (case‐insensitive):
        Timestamp, User, Configuration, SessionTime,
        HeartRate_BPM, RespirationRate_BPM, Range_m,
        HeartWaveform, BreathWaveform, HeartRate_FFT,
        BreathRate_FFT, ChestDisplacement, CombinedSignal

    Returns dict with keys:
        "timestamps"     – seconds since session start
        "rr_amplitude"   – absolute breath‐waveform amplitude
        "rr_bpm"         – respiration rate in BPM
        "hr_bpm"         – heart rate in BPM
        "motion_scores"  – synthesised motion indicator (0–1)
        "chest_disp"     – chest displacement signal
    """
    df = pd.read_csv(filepath, on_bad_lines="skip")

    # Normalise column names
    df.columns = [c.strip() for c in df.columns]

    # Optional user filter
    if user_email and "User" in df.columns:
        df = df[df["User"].str.strip().str.lower() == user_email.lower()]

    if df.empty:
        if user_email:
            raise ValueError(
                f"No rows found in '{os.path.basename(filepath)}' for user '{user_email}'. "
                "Try analysis without user filtering."
            )
        raise ValueError(f"Input file '{os.path.basename(filepath)}' has no usable rows.")

    df = df.sort_values("SessionTime").reset_index(drop=True)

    timestamps = pd.to_numeric(df["SessionTime"], errors="coerce").values
    # If SessionTime has NaNs or resets, rebuild a monotonic index
    if np.any(np.isnan(timestamps)) or (len(timestamps) > 1 and np.any(np.diff(timestamps) < 0)):
        timestamps = np.arange(len(df)) / 20.0  # fallback: 20 fps

    # Breath waveform → amplitude proxy
    breath = df["BreathWaveform"].astype(float).values if "BreathWaveform" in df.columns else np.zeros(len(df))
    rr_amplitude = np.abs(breath)

    rr_bpm = df["RespirationRate_BPM"].astype(float).values if "RespirationRate_BPM" in df.columns else np.zeros(len(df))
    hr_bpm = df["HeartRate_BPM"].astype(float).values if "HeartRate_BPM" in df.columns else np.zeros(len(df))

    chest_disp = df["ChestDisplacement"].astype(float).values if "ChestDisplacement" in df.columns else np.zeros(len(df))

    # ── Fallback: synthesise rr_amplitude from RR BPM ───────────────
    # BreathWaveform can be all-zero during short live sessions when the
    # radar phase signal hasn't stabilised.  Use normalised RR BPM as a
    # proxy so the detection engine still gets a meaningful signal.
    if len(rr_amplitude) == 0 or np.max(np.abs(rr_amplitude)) < 0.001:
        valid_rr = rr_bpm[rr_bpm > 0]
        if len(valid_rr) > 0:
            rr_norm = rr_bpm / float(np.percentile(valid_rr, 95))
            rr_amplitude = np.clip(rr_norm, 0.0, 1.0)
        else:
            # Both waveform and BPM are zero — use a flat baseline so the
            # pipeline can at least report a "Normal" session rather than
            # crashing or showing blank output.
            rr_amplitude = np.full(len(df), 0.5)

    # ── Synthesise motion score ─────────────────────────────────────
    # Gross body motion is better captured by rapid *changes* in the
    # displacement slope (acceleration-like), while normal respiration
    # mostly appears as smooth periodic drift. Using 2nd-order changes
    # reduces false "Motion" labels during regular breathing.
    if len(chest_disp) == 0:
        motion_scores = np.zeros(0)
    else:
        vel = np.diff(chest_disp, prepend=chest_disp[0])
        motion_raw = np.abs(np.diff(vel, prepend=vel[0]))
        mx = np.percentile(motion_raw, 99.5) if len(motion_raw) > 1 else 1.0
        motion_scores = np.clip(motion_raw / max(mx, 1e-8), 0, 1)

    return {
        "timestamps": timestamps,
        "rr_amplitude": rr_amplitude,
        "rr_bpm": rr_bpm,
        "hr_bpm": hr_bpm,
        "motion_scores": motion_scores,
        "chest_disp": chest_disp,
    }


def load_live_session_csv(filepath: str) -> Dict[str, np.ndarray]:
    """
    Load a *vital_signs_live_session.csv* produced by allframes.py.

    Columns: time_sec, phase, chest_displacement, breathing_wave, heart_wave

    Returns the same dict structure as ``load_pipeline_csv``.
    """
    df = pd.read_csv(filepath)
    df.columns = [c.strip() for c in df.columns]

    if df.empty:
        raise ValueError(f"Input file '{os.path.basename(filepath)}' has no usable rows.")

    timestamps = df["time_sec"].astype(float).values
    breath = df["breathing_wave"].astype(float).values if "breathing_wave" in df.columns else np.zeros(len(df))
    rr_amplitude = np.abs(breath)

    heart = df["heart_wave"].astype(float).values if "heart_wave" in df.columns else np.zeros(len(df))
    chest_disp = df["chest_displacement"].astype(float).values if "chest_displacement" in df.columns else np.zeros(len(df))

    if len(chest_disp) == 0:
        motion_scores = np.zeros(0)
    else:
        vel = np.diff(chest_disp, prepend=chest_disp[0])
        motion_raw = np.abs(np.diff(vel, prepend=vel[0]))
        mx = np.percentile(motion_raw, 99.5) if len(motion_raw) > 1 else 1.0
        motion_scores = np.clip(motion_raw / max(mx, 1e-8), 0, 1)

    return {
        "timestamps": timestamps,
        "rr_amplitude": rr_amplitude,
        "rr_bpm": np.zeros(len(df)),   # not directly available
        "hr_bpm": np.zeros(len(df)),   # not directly available
        "motion_scores": motion_scores,
        "chest_disp": chest_disp,
    }


# ────────────────────────────────────────────────────────────────────
#  OUTPUT WRITERS
# ────────────────────────────────────────────────────────────────────

def save_sleep_report(
    result: Dict,
    output_dir: str,
    prefix: str = "sleep_report",
    save_csv: bool = True,
    save_json: bool = True,
) -> Dict[str, str]:
    """
    Persist sleep‐event detection results.

    Parameters
    ──────────
    result     : dict returned by ``detect_sleep_events()``.
    output_dir : directory to write output files.
    prefix     : filename prefix.
    save_csv   : write a CSV file of per‐epoch events.
    save_json  : write a JSON file with events + summary.

    Returns
    ───────
    paths : dict mapping "csv" / "json" to their absolute file paths.
    """
    os.makedirs(output_dir, exist_ok=True)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    paths: Dict[str, str] = {}

    if save_csv:
        csv_path = os.path.join(output_dir, f"{prefix}_{ts}.csv")
        _write_events_csv(result["events"], csv_path)
        paths["csv"] = csv_path

    if save_json:
        json_path = os.path.join(output_dir, f"{prefix}_{ts}.json")
        payload = {
            "generated_at": datetime.datetime.now().isoformat(),
            "summary": result["summary"],
            "events": result["events"],
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        paths["json"] = json_path

    return paths


def _write_events_csv(events: List[Dict], path: str) -> None:
    """Write per‐epoch events to a CSV file."""
    if not events:
        return

    fieldnames = list(events[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(events)
