"""
sleep_staging/run_sleep_staging.py
──────────────────────────────────
CLI entry point for the sleep‑stage classification pipeline.

Usage
─────
    # Predict sleep stages on radar CSV
    python -m backend.sleep_staging.run_sleep_staging \\
        --input backend/vital_signs_data_new.csv \\
        --output backend/sleep_staging/output

    # Train model first, then predict
    python -m backend.sleep_staging.run_sleep_staging \\
        --input backend/vital_signs_data_new.csv \\
        --train-model --model-type random_forest

    # Compare two classical models
    python -m backend.sleep_staging.run_sleep_staging \\
        --input backend/vital_signs_data_new.csv \\
        --compare rf,xgboost

    # Use live‑session format
    python -m backend.sleep_staging.run_sleep_staging \\
        --input vital_signs_data/vital_signs_live_session.csv \\
        --format live

    # Include sleep events & posture context
    python -m backend.sleep_staging.run_sleep_staging \\
        --input backend/vital_signs_data_new.csv \\
        --sleep-json backend/sleep_detection/output/sleep_report.json \\
        --posture-json backend/motion_posture/output/motion_posture_report.json
"""

from __future__ import annotations
import argparse, io, json, os, sys, traceback
import numpy as np

# Ensure UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ── Ensure project root is importable ──────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.sleep_staging import config as CFG
from backend.sleep_staging.io_utils import (
    load_pipeline_csv,
    load_live_session_csv,
    load_sleep_events_json,
    load_posture_json,
    save_staging_report,
)
from backend.sleep_staging.features import extract_all_features, FEATURE_DIM
from backend.sleep_staging.training import train_classical, train_deep, generate_synthetic_sleep_data
from backend.sleep_staging.predict import run_prediction
from backend.sleep_staging.evaluate import compute_metrics
from backend.sleep_staging.visualize import save_all_plots


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sleep Stage Classification Pipeline",
    )
    parser.add_argument("--input", type=str, default="",
                        help="Path to vital‑signs CSV.")
    parser.add_argument("--output", type=str, default="backend/sleep_staging/output",
                        help="Output directory for reports & plots.")
    parser.add_argument("--format", type=str, default="pipeline",
                        choices=["pipeline", "live"],
                        help="Input CSV format.")
    parser.add_argument("--user", type=str, default="",
                        help="Filter by user email.")
    parser.add_argument("--model-type", type=str, default=CFG.DEFAULT_MODEL_TYPE,
                        help="Model type: random_forest | svm | xgboost | lstm | cnn_lstm | tcn")
    parser.add_argument("--train-model", action="store_true",
                        help="Train the model before prediction.")
    parser.add_argument("--compare", type=str, default="",
                        help="Comma‑separated model types to train & compare (e.g. random_forest,xgboost).")
    parser.add_argument("--full-stages", action="store_true",
                        help="Use full PSG stages (Wake,N1,N2,N3,REM) instead of reduced set.")
    parser.add_argument("--sleep-json", type=str, default="",
                        help="Path to sleep‑event detection JSON for context features.")
    parser.add_argument("--posture-json", type=str, default="",
                        help="Path to motion/posture report JSON for context features.")
    parser.add_argument("--epoch", type=float, default=CFG.EPOCH_DURATION_SEC,
                        help="Epoch duration in seconds.")
    parser.add_argument("--sampling-rate", type=float, default=CFG.SAMPLING_RATE,
                        help="Sampling rate in Hz.")
    parser.add_argument("--no-plots", action="store_true",
                        help="Skip plot generation.")

    args = parser.parse_args()

    try:
        _run(args)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


def _run(args: argparse.Namespace) -> None:
    use_full = args.full_stages
    label_names = CFG.STAGE_LABELS_FULL if use_full else CFG.STAGE_LABELS_REDUCED

    # ── Load optional context ───────────────────────────────────────
    sleep_events = None
    posture_map = None

    if args.sleep_json and os.path.isfile(args.sleep_json):
        sleep_events = load_sleep_events_json(args.sleep_json)
        print(f"Loaded {len(sleep_events)} sleep events from {args.sleep_json}")

    if args.posture_json and os.path.isfile(args.posture_json):
        posture_map = load_posture_json(args.posture_json)
        print(f"Loaded posture map ({len(posture_map)} epochs) from {args.posture_json}")

    # ── Model comparison mode ───────────────────────────────────────
    if args.compare:
        model_types = [m.strip() for m in args.compare.split(",")]
        _compare_models(model_types, use_full, args)
        return

    # ── Training ────────────────────────────────────────────────────
    trained_model = None
    training_metrics = None

    if args.train_model:
        model_type = args.model_type
        is_deep = model_type in ("lstm", "cnn_lstm", "tcn")
        print(f"Training {model_type} classifier on synthetic data...")

        if is_deep:
            result = train_deep(model_type=model_type, use_full_stages=use_full)
            if result.get("error"):
                print(f"  Warning: {result['error']}")
                print("  Falling back to Random Forest...")
                result = train_classical(model_type="random_forest", use_full_stages=use_full)
                trained_model = result["model"]
                args.model_type = "random_forest"
            else:
                trained_model = result["model"]
        else:
            result = train_classical(model_type=model_type, use_full_stages=use_full)
            trained_model = result["model"]

        training_metrics = result.get("metrics", {})
        cv = result.get("cv_scores", {})
        acc = training_metrics.get("accuracy", 0)
        kappa = training_metrics.get("cohens_kappa", 0)
        print(f"  Accuracy: {acc:.3f}  |  Kappa: {kappa:.3f}")
        if cv:
            print(f"  CV mean accuracy: {cv.get('mean_accuracy', 0):.3f} "
                  f"± {cv.get('std_accuracy', 0):.3f}")
        print(f"  Model saved: {result.get('model_path', 'N/A')}")

    # ── Load data & predict ─────────────────────────────────────────
    if not args.input:
        if args.train_model:
            # training‑only mode
            _output_training_result(training_metrics, args, label_names)
            return
        print("No input file specified.  Use --input or --train-model.")
        sys.exit(1)

    input_path = os.path.abspath(args.input)
    print(f"Loading {'live' if args.format == 'live' else 'pipeline'} CSV: {input_path}")

    if args.format == "live":
        data = load_live_session_csv(input_path)
    else:
        data = load_pipeline_csv(input_path, user_email=args.user or None)

    n = len(data["timestamps"])
    dur = data["timestamps"][-1] - data["timestamps"][0] if n > 1 else 0
    print(f"  Samples: {n}  |  Duration: {dur:.1f}s  |  SR: {args.sampling_rate} fps")

    # ── Detect actual sampling rate from data ─────────────────────────
    actual_sr = n / dur if dur > 0 else args.sampling_rate
    if abs(actual_sr - args.sampling_rate) > 1.0:
        print(f"  ⚠ Actual SR: {actual_sr:.2f} fps (vs configured {args.sampling_rate} fps)")
    
    # ── Use actual sampling rate for processing ───────────────────────
    sampling_rate_to_use = actual_sr

    # Predict
    print("Predicting sleep stages...")
    prediction = run_prediction(
        data,
        model=trained_model,
        model_type=args.model_type,
        use_full_stages=use_full,
        sleep_events=sleep_events,
        posture_epoch_map=posture_map,
        sampling_rate=sampling_rate_to_use,
        epoch_duration_sec=args.epoch,
    )

    labels = prediction["labels"]
    structure = prediction["sleep_structure"]
    n_epochs = len(labels)
    print(f"  Epochs: {n_epochs}")
    print(f"  Stage distribution: {structure.get('pct_per_stage', {})}")
    print(f"  Sleep efficiency: {structure.get('sleep_efficiency_pct', 0):.1f}% "
          f"({structure.get('efficiency_rating', 'N/A')})")
    if structure.get("rem_episodes", 0):
        print(f"  REM episodes: {structure['rem_episodes']}")

    # ── Save outputs ────────────────────────────────────────────────
    os.makedirs(args.output, exist_ok=True)

    paths = save_staging_report(prediction, training_metrics, args.output)
    for fmt, p in paths.items():
        print(f"  Saved {fmt}: {p}")

    if not args.no_plots:
        plot_paths = save_all_plots(
            prediction,
            metrics_result=training_metrics,
            data=data,
            output_dir=args.output,
            label_names=label_names,
        )
        for name, p in plot_paths.items():
            print(f"  Saved plot [{name}]: {p}")

    # ── Structured output for API parsing ───────────────────────────
    _output_result(prediction, training_metrics, paths, args)


def _compare_models(
    model_types: list,
    use_full: bool,
    args: argparse.Namespace,
) -> None:
    """Train and compare multiple models, print side‑by‑side metrics."""
    label_names = CFG.STAGE_LABELS_FULL if use_full else CFG.STAGE_LABELS_REDUCED
    results = {}

    for mt in model_types:
        print(f"\n── Training {mt} ──")
        is_deep = mt in ("lstm", "cnn_lstm", "tcn")
        if is_deep:
            res = train_deep(model_type=mt, use_full_stages=use_full)
            if res.get("error"):
                print(f"  Skipped: {res['error']}")
                continue
        else:
            res = train_classical(model_type=mt, use_full_stages=use_full)

        m = res.get("metrics", {})
        cv = res.get("cv_scores", {})
        print(f"  Accuracy={m.get('accuracy', 0):.3f}  "
              f"Kappa={m.get('cohens_kappa', 0):.3f}  "
              f"F1={m.get('f1_macro', 0):.3f}")
        if cv:
            print(f"  CV: {cv.get('mean_accuracy', 0):.3f}±{cv.get('std_accuracy', 0):.3f}")
        results[mt] = m

    # Summary table
    print("\n╔══════════════════╦══════════╦════════╦══════╦═══════╗")
    print("║      Model       ║ Accuracy ║ Kappa  ║  F1  ║  AUC  ║")
    print("╠══════════════════╬══════════╬════════╬══════╬═══════╣")
    for mt, m in results.items():
        acc = m.get("accuracy", 0)
        kap = m.get("cohens_kappa", 0)
        f1 = m.get("f1_macro", 0)
        auc = m.get("roc_auc_macro", None)
        auc_s = f"{auc:.3f}" if auc is not None else "  N/A"
        print(f"║ {mt:16s} ║  {acc:.4f}  ║ {kap:.4f} ║{f1:.4f}║{auc_s:>6s} ║")
    print("╚══════════════════╩══════════╩════════╩══════╩═══════╝")


def _output_result(
    prediction: Dict,
    metrics: dict | None,
    paths: dict,
    args: argparse.Namespace,
) -> None:
    """Print structured JSON block for pipeline.py subprocess parsing."""
    structure = prediction.get("sleep_structure", {})
    records = prediction.get("epoch_records", [])

    result = {
        "sleep_structure": structure,
        "metrics": _sanitise_metrics(metrics) if metrics else {},
        "output_dir": args.output,
        "model_type": args.model_type,
        "epoch_records": records,
        "saved_files": paths,
    }

    print("\nSLEEP_STAGING_RESULT_BEGIN")
    print(json.dumps(result, default=str))
    print("SLEEP_STAGING_RESULT_END")


def _output_training_result(
    metrics: dict | None,
    args: argparse.Namespace,
    label_names: list,
) -> None:
    """Output training‑only result."""
    result = {
        "sleep_structure": {},
        "metrics": _sanitise_metrics(metrics) if metrics else {},
        "output_dir": args.output,
        "model_type": args.model_type,
        "epoch_records": [],
        "saved_files": {},
    }
    print("\nSLEEP_STAGING_RESULT_BEGIN")
    print(json.dumps(result, default=str))
    print("SLEEP_STAGING_RESULT_END")


def _sanitise_metrics(m: dict) -> dict:
    """Remove non‑serialisable items from metrics."""
    out = {}
    for k, v in m.items():
        if k == "classification_report":
            continue  # large nested dict already serialisable but skip for brevity
        if isinstance(v, np.ndarray):
            out[k] = v.tolist()
        elif isinstance(v, (dict, list, int, float, str, bool, type(None))):
            out[k] = v
        else:
            out[k] = str(v)
    return out


if __name__ == "__main__":
    main()
