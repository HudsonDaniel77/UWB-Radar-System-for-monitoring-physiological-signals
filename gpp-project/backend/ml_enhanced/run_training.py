"""
ml_enhanced/run_training.py
───────────────────────────
CLI entry-point for the enhanced ML / DL training pipeline.

Usage
─────
# Train all models on synthetic event data (demo)
python -m ml_enhanced.run_training --task event --demo

# Train specific models
python -m ml_enhanced.run_training --task stage --models random_forest xgboost

# Hyperparameter tuning
python -m ml_enhanced.run_training --task event --tune --tune-model random_forest

# Skip deep models
python -m ml_enhanced.run_training --task event --demo --skip-deep

# Custom output directory
python -m ml_enhanced.run_training --task event --demo --output ml_enhanced/output
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import time
from typing import Dict, List, Optional

import numpy as np

from . import config as CFG
from .training import train_ml_models, ALL_MODEL_NAMES
from .evaluation import build_comparison_table
from .hyperparameter_tuning import tune_model
from .inference import save_trained_model
from .visualize import save_all_plots
from .feature_engineering import feature_importance_from_model

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ML-Enhanced training pipeline for radar sleep diagnostics",
    )
    p.add_argument("--task", default="event",
                   choices=["event", "stage", "ahi"],
                   help="Classification task (default: event)")
    p.add_argument("--demo", action="store_true",
                   help="Use synthetic demo data")
    p.add_argument("--input", default=None,
                   help="Path to feature CSV (columns = features + 'label')")
    p.add_argument("--output", default=os.path.join(MODULE_DIR, "output"),
                   help="Output directory for models / plots / reports")
    p.add_argument("--models", nargs="+", default=None,
                   help=f"Model types to train (choices: {ALL_MODEL_NAMES})")
    p.add_argument("--skip-deep", action="store_true",
                   help="Skip deep-learning models")
    p.add_argument("--full-stages", action="store_true",
                   help="Use 5-class stage labels (Wake/N1/N2/N3/REM)")
    p.add_argument("--no-plots", action="store_true",
                   help="Skip plot generation")
    p.add_argument("--tune", action="store_true",
                   help="Run hyperparameter tuning")
    p.add_argument("--tune-model", default="random_forest",
                   help="Model to tune (default: random_forest)")
    p.add_argument("--tune-method", default="grid",
                   choices=["grid", "bayesian"],
                   help="Tuning method")
    p.add_argument("--seed", type=int, default=CFG.RANDOM_SEED)
    return p.parse_args(argv)


def run_training(args: argparse.Namespace) -> Dict:
    """Run the full training pipeline and return structured results."""
    t0 = time.time()
    os.makedirs(args.output, exist_ok=True)

    print(f"[ml_enhanced] task={args.task}  output={args.output}")

    # ── Load or generate data ──────────────────────────────────────
    X, y = None, None
    if args.input:
        from .dataset import load_features_csv
        X, y, _ = load_features_csv(args.input)
        print(f"[ml_enhanced] loaded {len(y)} samples from {args.input}")
    elif args.demo:
        print("[ml_enhanced] using synthetic demo data")
    else:
        print("[ml_enhanced] no --input / --demo flag; using synthetic data")

    # ── Hyperparameter tuning (optional) ───────────────────────────
    tuning_result = None
    if args.tune:
        print(f"[ml_enhanced] tuning {args.tune_model} ({args.tune_method}) …")
        from .dataset import (generate_synthetic_event_data,
                              generate_synthetic_stage_data,
                              generate_synthetic_ahi_data)
        if X is None or y is None:
            if args.task == "event":
                X_t, y_t = generate_synthetic_event_data(seed=args.seed)
            elif args.task == "stage":
                X_t, y_t = generate_synthetic_stage_data(
                    use_full_stages=args.full_stages, seed=args.seed)
            else:
                X_t, y_t = generate_synthetic_ahi_data(seed=args.seed)
                from .training import _ahi_to_class
                y_t = _ahi_to_class(y_t)
        else:
            X_t, y_t = X, y

        n_classes = len(set(y_t))
        tuning_result = tune_model(
            args.tune_model, X_t, y_t,
            method=args.tune_method,
            n_classes=n_classes,
            seed=args.seed,
        )
        print(f"[ml_enhanced] best score = {tuning_result.get('best_score', 0):.4f}")
        print(f"[ml_enhanced] best params = {tuning_result.get('best_params', {})}")

    # ── Train models ───────────────────────────────────────────────
    print("[ml_enhanced] training models …")
    results = train_ml_models(
        task=args.task,
        X=X, y=y,
        model_types=args.models,
        use_full_stages=args.full_stages,
        skip_deep=args.skip_deep,
        seed=args.seed,
    )

    # ── Build comparison table ─────────────────────────────────────
    comparison = build_comparison_table(results)
    print("\n[ml_enhanced] ── Model Comparison ──")
    print(f"{'Model':<18} {'F1':>8} {'Acc':>8} {'Prec':>8} {'Rec':>8} {'AUC':>8} {'Time':>8}")
    print("─" * 78)
    for row in comparison:
        if "error" in row:
            print(f"{row['model']:<18} ERROR: {row['error']}")
            continue
        auc_str = f"{row['roc_auc']:.4f}" if row.get("roc_auc") is not None else "N/A"
        print(f"{row['model']:<18} {row['f1']:>8.4f} {row['accuracy']:>8.4f} "
              f"{row['precision']:>8.4f} {row['recall']:>8.4f} {auc_str:>8} "
              f"{row['elapsed_sec']:>7.1f}s")
    print()

    # ── Save best model ───────────────────────────────────────────
    best_model_type = comparison[0]["model"] if comparison and "error" not in comparison[0] else None
    saved_paths: Dict = {}
    if best_model_type and best_model_type in results:
        best = results[best_model_type]
        model_obj = best.get("model")
        if model_obj is not None:
            meta = {
                "task":         args.task,
                "model_type":   best_model_type,
                "val_metrics":  best.get("val_metrics", {}),
                "label_names":  best.get("label_names", []),
                "is_deep":      best.get("is_deep", False),
            }
            saved_paths = save_trained_model(
                model_obj, args.task, best_model_type,
                output_dir=args.output,
                scaler=best.get("scaler"),
                metadata=meta,
            )
            print(f"[ml_enhanced] best model ({best_model_type}) saved → {saved_paths.get('model', '')}")

    # ── Plots ──────────────────────────────────────────────────────
    plot_paths: Dict = {}
    if not args.no_plots:
        print("[ml_enhanced] generating plots …")
        plot_paths = save_all_plots(
            training_results=results,
            comparison_table=comparison,
            output_dir=args.output,
        )
        print(f"[ml_enhanced] {len(plot_paths)} plots saved")

    # ── Summary JSON ───────────────────────────────────────────────
    summary = {
        "task":             args.task,
        "comparison_table": comparison,
        "best_model":       best_model_type,
        "saved_paths":      saved_paths,
        "plot_paths":       plot_paths,
        "tuning":           _safe_serialise(tuning_result) if tuning_result else None,
        "elapsed_sec":      round(time.time() - t0, 2),
    }

    summary_path = os.path.join(args.output, "training_summary.json")
    with open(summary_path, "w") as f:
        json.dump(_safe_serialise(summary), f, indent=2)
    print(f"[ml_enhanced] summary → {summary_path}")

    # ── Structured output block (for API parsing) ──────────────────
    print("\nML_ENHANCED_RESULT_BEGIN")
    print(json.dumps(_safe_serialise(summary), indent=2))
    print("ML_ENHANCED_RESULT_END")

    return summary


# ────────────────────────────────────────────────────────────────────
#  HELPERS
# ────────────────────────────────────────────────────────────────────

def _safe_serialise(obj):
    """Recursively make dict JSON-serialisable."""
    if isinstance(obj, dict):
        return {k: _safe_serialise(v) for k, v in obj.items()
                if k not in ("model", "scaler", "best_model_obj",
                              "best_model", "cv_results")}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialise(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


# ────────────────────────────────────────────────────────────────────
#  ENTRY-POINT
# ────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    run_training(args)


if __name__ == "__main__":
    main()
