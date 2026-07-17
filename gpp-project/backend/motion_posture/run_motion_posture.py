"""
motion_posture/run_motion_posture.py
────────────────────────────────────
Standalone CLI entry‑point for the motion & posture context pipeline.

Usage
─────
    python -m backend.motion_posture.run_motion_posture \
        --input  backend/vital_signs_data_new.csv \
        --output backend/motion_posture/output \
        --user   kevin2310172@ssn.edu.in

    # with a live‑session CSV
    python -m backend.motion_posture.run_motion_posture \
        --input  vital_signs_data/vital_signs_live_session.csv \
        --format live \
        --output backend/motion_posture/output

    # with sleep‑event JSON for context fusion
    python -m backend.motion_posture.run_motion_posture \
        --input  backend/vital_signs_data_new.csv \
        --sleep-json backend/sleep_detection/output/sleep_report_*.json

All output artefacts (CSV, JSON, PNG) are written to --output.
"""

from __future__ import annotations
import argparse, io, json, os, sys, glob

# Ensure UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import numpy as np

# ── Ensure project root is importable ──────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.motion_posture.io_utils import (
    load_pipeline_csv,
    load_live_session_csv,
    save_posture_motion_report,
)
from backend.motion_posture.features import extract_all_features
from backend.motion_posture.motion import classify_motion_segments
from backend.motion_posture.posture import predict_posture, train_posture_classifier
from backend.motion_posture.context import align_context_with_events
from backend.motion_posture.visualize import save_all_plots


def main(args=None):
    parser = argparse.ArgumentParser(
        description="Motion & posture context detection pipeline"
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Path to input CSV file")
    parser.add_argument("--output", "-o", default=None,
                        help="Output directory (default: <input_dir>/motion_posture_output)")
    parser.add_argument("--user", "-u", default=None,
                        help="Filter by user email (pipeline CSVs only)")
    parser.add_argument("--format", "-f", default="pipeline",
                        choices=["pipeline", "live"],
                        help="CSV format: 'pipeline' or 'live'")
    parser.add_argument("--sleep-json", default=None,
                        help="Path to sleep detection JSON report (for context fusion)")
    parser.add_argument("--epoch", type=float, default=15.0,
                        help="Epoch window in seconds (default: 15)")
    parser.add_argument("--overlap", type=float, default=0.5,
                        help="Epoch overlap fraction (default: 0.5)")
    parser.add_argument("--sampling-rate", type=float, default=20.0,
                        help="Sampling rate (default: 20 fps)")
    parser.add_argument("--train-model", action="store_true",
                        help="Force re-training the posture model on synthetic data")
    parser.add_argument("--no-plots", action="store_true",
                        help="Skip plot generation")

    opts = parser.parse_args(args)

    input_path = os.path.abspath(opts.input)
    if not os.path.isfile(input_path):
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = opts.output or os.path.join(os.path.dirname(input_path),
                                              "motion_posture_output")
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
    if abs(actual_sr - opts.sampling_rate) > 1.0:
        print(f"  ⚠ Actual SR: {actual_sr:.2f} fps (vs configured {opts.sampling_rate} fps)")
    
    # ── Use actual sampling rate for processing ───────────────────────
    sampling_rate_to_use = actual_sr

    # ── Train posture model (if needed or forced) ───────────────────
    if opts.train_model:
        print("Training posture classifier on synthetic data...")
        train_result = train_posture_classifier()
        print(f"  Accuracy: {train_result['accuracy']:.3f}")
        print(f"  Model saved: {train_result['model_path']}")

    # ── Motion classification ───────────────────────────────────────
    print("Classifying motion segments...")
    motion_result = classify_motion_segments(
        motion_scores=data["motion_scores"],
        chest_disp=data["chest_disp"],
        timestamps=data["timestamps"],
        sampling_rate=sampling_rate_to_use,
        epoch_duration_sec=opts.epoch,
        epoch_overlap_frac=opts.overlap,
    )
    n_epochs = len(motion_result["epoch_labels"])
    print(f"  Motion epochs: {n_epochs}")

    # ── Feature extraction for posture ──────────────────────────────
    print("Extracting posture features...")
    X_features, feat_indices = extract_all_features(
        data,
        epoch_duration_sec=opts.epoch,
        epoch_overlap_frac=opts.overlap,
        sampling_rate=sampling_rate_to_use,
    )
    print(f"  Feature matrix: {X_features.shape}")

    # ── Posture prediction ──────────────────────────────────────────
    posture_records = []
    if X_features.shape[0] == 0:
        print("  Warning: no feature epochs extracted — skipping posture prediction.")
    else:
        print("Predicting postures...")
        posture_labels, confidences = predict_posture(X_features)

        for k, (s, e) in enumerate(feat_indices):
            ts_start = float(data["timestamps"][s])
            ts_end = float(data["timestamps"][min(e - 1, n - 1)])
            posture_records.append({
                "epoch_index": k,
                "timestamp_start": round(ts_start, 3),
                "timestamp_end": round(ts_end, 3),
                "posture_label": posture_labels[k],
                "posture_confidence": round(float(confidences[k]), 3),
            })

        print(f"  Posture epochs: {len(posture_records)}")
        from collections import Counter
        posture_dist = Counter(posture_labels)
        print(f"  Distribution: {dict(posture_dist)}")

    # ── Load sleep events (if provided) ─────────────────────────────
    sleep_events = None
    if opts.sleep_json:
        sleep_path = opts.sleep_json
        # Support glob patterns
        matches = glob.glob(sleep_path)
        if matches:
            sleep_path = sorted(matches)[-1]  # latest
        if os.path.isfile(sleep_path):
            print(f"Loading sleep events: {sleep_path}")
            with open(sleep_path) as f:
                sleep_data = json.load(f)
            sleep_events = sleep_data.get("events", [])
            print(f"  Sleep events loaded: {len(sleep_events)}")
        else:
            print(f"  Warning: Sleep JSON not found: {sleep_path}")

    # ── Context fusion ──────────────────────────────────────────────
    print("Fusing motion + posture + sleep context...")
    context_result = align_context_with_events(
        motion_records=motion_result["epoch_records"],
        posture_records=posture_records,
        sleep_events=sleep_events,
    )

    # ── Save reports ────────────────────────────────────────────────
    paths = save_posture_motion_report(
        context_result, motion_result, posture_records, output_dir,
    )
    for fmt, p in paths.items():
        print(f"  Saved {fmt}: {p}")

    # ── Save plots ──────────────────────────────────────────────────
    if not opts.no_plots:
        rr_amp = np.abs(data.get("breath_wave", np.zeros(n)))
        plot_paths = save_all_plots(
            motion_records=motion_result["epoch_records"],
            posture_records=posture_records,
            context_result=context_result,
            rr_amplitude=rr_amp,
            timestamps=data["timestamps"],
            sleep_events=sleep_events,
            output_dir=output_dir,
        )
        for name, p in plot_paths.items():
            print(f"  Saved plot [{name}]: {p}")

    # ── Print summary ───────────────────────────────────────────────
    stats = context_result["session_stats"]
    print("\n" + "=" * 55)
    print("MOTION & POSTURE CONTEXT SUMMARY")
    print("=" * 55)
    print(f"  Total epochs        : {n_epochs}")
    print(f"  Posture distribution: {json.dumps(stats.get('posture_distribution_pct', {}))}")
    print(f"  Motion distribution : {json.dumps(stats.get('motion_epoch_counts', {}))}")
    print(f"  Event annotations   : {stats.get('total_annotations', 0)}")
    if stats.get("event_posture_correlation"):
        print(f"  Event<->Posture      : {json.dumps(stats['event_posture_correlation'])}")
    print("=" * 55)

    # ── Machine‑readable output ─────────────────────────────────────
    print("\nMOTION_POSTURE_RESULT_BEGIN")
    output_payload = {
        "session_stats": stats,
        "output_dir": output_dir,
        "posture_records": posture_records,
        "motion_records": motion_result["epoch_records"],
        "event_annotations": context_result["event_annotations"],
    }
    print(json.dumps(output_payload, default=str))
    print("MOTION_POSTURE_RESULT_END")


if __name__ == "__main__":
    main()
