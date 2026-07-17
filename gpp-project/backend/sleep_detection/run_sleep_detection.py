"""
sleep_detection/run_sleep_detection.py
──────────────────────────────────────
Standalone entry‑point that runs the full sleep‑detection pipeline on
a CSV file produced by the existing vitalsigns.py pipeline (or the
live‑session CSV from allframes.py).

Usage
─────
    python -m backend.sleep_detection.run_sleep_detection \
        --input  backend/vital_signs_data_new.csv \
        --output backend/sleep_detection/output \
        --user   kevin2310172@ssn.edu.in

    # or with a live‑session CSV
    python -m backend.sleep_detection.run_sleep_detection \
        --input  vital_signs_data/vital_signs_live_session.csv \
        --format live

All output artefacts (CSV, JSON, PNG plots) are written to --output.
"""

from __future__ import annotations
import argparse, io, json, os, sys

import numpy as np

# Ensure UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ── Ensure project root is importable ──────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.sleep_detection.core import detect_sleep_events
from backend.sleep_detection.io_utils import (
    load_pipeline_csv,
    load_live_session_csv,
    save_sleep_report,
)
from backend.sleep_detection.visualize import save_all_plots


def main(args=None):
    parser = argparse.ArgumentParser(
        description="Sleep breathing‑event detection pipeline"
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Path to input CSV file")
    parser.add_argument("--output", "-o", default=None,
                        help="Output directory (default: <input_dir>/sleep_output)")
    parser.add_argument("--user", "-u", default=None,
                        help="Filter by user email (pipeline CSVs only)")
    parser.add_argument("--format", "-f", default="pipeline",
                        choices=["pipeline", "live"],
                        help="CSV format: 'pipeline' or 'live'")
    parser.add_argument("--epoch", type=float, default=30.0,
                        help="Epoch window in seconds (default: 30)")
    parser.add_argument("--overlap", type=float, default=0.5,
                        help="Epoch overlap fraction (default: 0.5)")
    parser.add_argument("--drop-threshold", type=float, default=0.30,
                        help="Amplitude drop threshold for abnormal (default: 0.30)")
    parser.add_argument("--apnea-min", type=int, default=3,
                        help="Min consecutive abnormal epochs for apnea (default: 3)")
    parser.add_argument("--sampling-rate", type=float, default=20.0,
                        help="Sampling rate (default: 20 fps)")
    parser.add_argument("--no-plots", action="store_true",
                        help="Skip plot generation")

    opts = parser.parse_args(args)

    input_path = os.path.abspath(opts.input)
    if not os.path.isfile(input_path):
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = opts.output or os.path.join(os.path.dirname(input_path), "sleep_output")
    os.makedirs(output_dir, exist_ok=True)

    # ── Load data ───────────────────────────────────────────────────
    print(f"Loading {opts.format} CSV: {input_path}")
    if opts.format == "live":
        data = load_live_session_csv(input_path)
    else:
        data = load_pipeline_csv(input_path, user_email=opts.user)

    n = len(data["timestamps"])
    duration = data["timestamps"][-1] - data["timestamps"][0] if n > 1 else 0
    print(f"  Samples: {n}  |  Duration: {duration:.1f}s  |  SR: {opts.sampling_rate} fps")

    # ── Detect actual sampling rate from data ─────────────────────────
    actual_sr = n / duration if duration > 0 else opts.sampling_rate
    print(f"  Actual SR: {actual_sr:.2f} fps (vs configured {opts.sampling_rate} fps)")
    
    # ── Auto-adjust epoch duration for short recordings ──────────────
    epoch_duration = opts.epoch
    epoch_overlap = opts.overlap
    sampling_rate_to_use = actual_sr  # Use actual SR to handle varying data rates
    
    # Calculate required samples for at least 1 full epoch
    epoch_samples_needed = int(epoch_duration * sampling_rate_to_use)
    
    # If we don't have enough samples for a full epoch, reduce epoch duration
    if n < epoch_samples_needed:
        # Use adaptive epoch duration based on available data
        # Target: create at least 1-2 epochs
        if duration > 0:
            # Use up to 60% of total duration for epoch length, minimum 5 seconds
            target_epoch_sec = min(duration * 0.6, epoch_duration)
            target_epoch_sec = max(target_epoch_sec, 5.0)
            
            # Check if this works with actual SR
            test_samples = int(target_epoch_sec * sampling_rate_to_use)
            if n < test_samples:
                # Use entire duration minus a small buffer
                epoch_duration = max(duration * 0.9, 3.0)
                epoch_overlap = 0.0  # No overlap for short recordings
                print(f"  ⚠ Short recording: using full duration as single epoch ({epoch_duration:.1f}s)")
            else:
                epoch_duration = target_epoch_sec
                print(f"  ⚠ Short recording: adjusting epoch duration to {epoch_duration:.1f}s")

    # ── Detect events ───────────────────────────────────────────────
    result = detect_sleep_events(
        rr_amplitude=data["rr_amplitude"],
        timestamps=data["timestamps"],
        motion_scores=data["motion_scores"],
        hr_values=data["hr_bpm"] if np.any(data["hr_bpm"]) else None,
        sampling_rate=sampling_rate_to_use,  # Use actual measured SR instead of configured
        epoch_duration_sec=epoch_duration,
        epoch_overlap_frac=epoch_overlap,
        amplitude_drop_threshold=opts.drop_threshold,
        apnea_min_consecutive=opts.apnea_min,
    )

    # ── Save reports ────────────────────────────────────────────────
    paths = save_sleep_report(result, output_dir)
    for fmt, p in paths.items():
        print(f"  Saved {fmt}: {p}")

    # ── Save plots ──────────────────────────────────────────────────
    if not opts.no_plots:
        plot_paths = save_all_plots(
            data["rr_amplitude"],
            data["timestamps"],
            result,
            motion_scores=data["motion_scores"],
            output_dir=output_dir,
        )
        for name, p in plot_paths.items():
            print(f"  Saved plot [{name}]: {p}")

    # ── Print summary to stdout ─────────────────────────────────────
    summary = result["summary"]
    print("\n" + "=" * 50)
    print("SLEEP DETECTION SUMMARY")
    print("=" * 50)
    print(f"  Duration           : {summary['total_duration_sec']:.0f}s")
    print(f"  Total epochs       : {summary['total_epochs']}")
    print(f"  Baseline amplitude : {summary['baseline_amplitude']:.4f}")
    print(f"  Threshold          : {summary['amplitude_threshold']:.4f}")
    print(f"  Event counts       : {json.dumps(summary['event_counts'])}")
    print(f"  AHI                : {summary['apnea_events_per_hour']:.2f} events/hr")
    print(f"  Severity           : {summary['severity']}")
    print("=" * 50)

    # ── Machine‑readable output for pipeline integration ────────────
    print("\nSLEEP_RESULT_BEGIN")
    print(json.dumps({"summary": summary, "output_dir": output_dir}))
    print("SLEEP_RESULT_END")


if __name__ == "__main__":
    main()
