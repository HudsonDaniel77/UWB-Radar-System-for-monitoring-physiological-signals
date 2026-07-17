"""
field_testing/run_field_testing.py
──────────────────────────────────
CLI entry-point for the field-testing & deployment evaluation pipeline.

Usage
─────
# Quick demo with synthetic data
python -m field_testing.run_field_testing --demo

# Number of subjects / placements / environments
python -m field_testing.run_field_testing --demo --subjects 20 --placements 6

# Custom output directory
python -m field_testing.run_field_testing --demo --output field_out

# Skip plots
python -m field_testing.run_field_testing --demo --no-plots

# Minimal epochs for fast testing
python -m field_testing.run_field_testing --demo --epochs 120
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
from .test_config import generate_test_configs, save_configs
from .synthetic_data import generate_batch
from .field_runner import run_field_tests
from .metrics import evaluate_field_results
from .robustness import aggregate_robustness
from .visualize import plot_field_performance
from .reports import report_deployment_recommendations, write_report

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Field Testing & Deployment Evaluation for Radarix",
    )
    p.add_argument("--demo", action="store_true",
                   help="Use synthetic data for a quick demo run")
    p.add_argument("--input", default=None,
                   help="Path to a JSON file with pre-recorded field data")
    p.add_argument("--configs", default=None,
                   help="Path to a test-configs JSON file")
    p.add_argument("--output", default=os.path.join(MODULE_DIR, "output"),
                   help="Output directory")
    p.add_argument("--subjects", type=int,
                   default=CFG.SYNTHETIC_N_SUBJECTS,
                   help="Number of synthetic subjects")
    p.add_argument("--placements", type=int,
                   default=CFG.SYNTHETIC_N_PLACEMENTS,
                   help="Number of placement types to test")
    p.add_argument("--epochs", type=int, default=None,
                   help="Epochs per recording (None → full night)")
    p.add_argument("--no-plots", action="store_true",
                   help="Skip plot generation")
    p.add_argument("--no-report", action="store_true",
                   help="Skip report generation")
    p.add_argument("--seed", type=int, default=CFG.RANDOM_SEED)
    return p.parse_args(argv)


def run_field_testing(args: argparse.Namespace) -> Dict:
    """Run the full field-testing pipeline and return results."""
    t0 = time.time()
    os.makedirs(args.output, exist_ok=True)

    print(f"[field_testing] output → {args.output}")

    # ── 1. Generate or load test configs ──────────────────────────
    if args.configs:
        from .test_config import load_configs
        configs = load_configs(args.configs)
        print(f"[field_testing] loaded {len(configs)} configs from {args.configs}")
    else:
        n_pl = min(args.placements, len(CFG.PLACEMENT_TYPES))
        placements = CFG.PLACEMENT_TYPES[:n_pl]
        configs = generate_test_configs(
            n_subjects=args.subjects,
            placements=placements,
            seed=args.seed,
        )
        print(f"[field_testing] generated {len(configs)} test configs "
              f"({args.subjects} subjects × {n_pl} placements)")

    # Save configs
    cfg_path = save_configs(configs, args.output)
    print(f"[field_testing] configs saved → {cfg_path}")

    # ── 2. Generate or load recordings ────────────────────────────
    if args.input:
        with open(args.input) as f:
            recordings = json.load(f)
        print(f"[field_testing] loaded {len(recordings)} recordings")
    elif args.demo:
        print("[field_testing] generating synthetic recordings …")
        recordings = generate_batch(
            configs, seed=args.seed, n_epochs=args.epochs,
        )
        print(f"[field_testing] {len(recordings)} recordings generated")
    else:
        print("[field_testing] no --input / --demo; using synthetic data")
        recordings = generate_batch(
            configs, seed=args.seed, n_epochs=args.epochs,
        )

    # ── 3. Run field tests ────────────────────────────────────────
    print("[field_testing] running field tests …")
    test_results = run_field_tests(recordings)
    print(f"[field_testing] {len(test_results)} tests completed")

    # ── 4. Evaluate metrics ───────────────────────────────────────
    print("[field_testing] evaluating metrics …")
    field_eval = evaluate_field_results(test_results)

    # ── 5. Robustness scoring ─────────────────────────────────────
    print("[field_testing] computing robustness scores …")
    robustness = aggregate_robustness(field_eval)

    overall = robustness.get("overall_score", 0)
    tier = robustness.get("overall_tier", "?")
    print(f"\n[field_testing] ── Overall Score: {overall:.2f} ({tier}) ──")
    print(f"  Best placement   : {robustness.get('best_placement', 'N/A')}")
    print(f"  Worst placement  : {robustness.get('worst_placement', 'N/A')}")
    print(f"  Best environment : {robustness.get('best_environment', 'N/A')}")
    print(f"  Worst environment: {robustness.get('worst_environment', 'N/A')}")
    print()

    # ── 6. Plots ──────────────────────────────────────────────────
    plot_paths: Dict = {}
    if not args.no_plots:
        print("[field_testing] generating plots …")
        plot_paths = plot_field_performance(
            test_results, field_eval, robustness,
            output_dir=args.output,
        )
        print(f"[field_testing] {len(plot_paths)} plots saved")

    # ── 7. Report ─────────────────────────────────────────────────
    report_path = ""
    if not args.no_report:
        print("[field_testing] generating deployment report …")
        report_text = report_deployment_recommendations(
            robustness, field_eval,
        )
        report_path = write_report(
            report_text,
            os.path.join(args.output, "deployment_report.txt"),
        )
        print(f"[field_testing] report → {report_path}")

    # ── 8. Summary JSON ──────────────────────────────────────────
    summary = {
        "n_configs":         len(configs),
        "n_recordings":      len(recordings),
        "n_tests":           len(test_results),
        "overall_score":     robustness.get("overall_score", 0),
        "overall_tier":      robustness.get("overall_tier", ""),
        "best_placement":    robustness.get("best_placement"),
        "worst_placement":   robustness.get("worst_placement"),
        "best_environment":  robustness.get("best_environment"),
        "worst_environment": robustness.get("worst_environment"),
        "robustness":        _safe_serialise(robustness),
        "field_eval_overall": _safe_serialise(field_eval.get("overall", {})),
        "plot_paths":        plot_paths,
        "report_path":       report_path,
        "elapsed_sec":       round(time.time() - t0, 2),
    }

    summary_path = os.path.join(args.output, "field_testing_summary.json")
    with open(summary_path, "w") as f:
        json.dump(_safe_serialise(summary), f, indent=2)
    print(f"[field_testing] summary → {summary_path}")

    # ── Structured output block (for API parsing) ─────────────────
    print("\nFIELD_TESTING_RESULT_BEGIN")
    print(json.dumps(_safe_serialise(summary), indent=2))
    print("FIELD_TESTING_RESULT_END")

    return summary


# ────────────────────────────────────────────────────────────────────
#  HELPERS
# ────────────────────────────────────────────────────────────────────

def _safe_serialise(obj):
    """Recursively make dict JSON-serialisable."""
    if isinstance(obj, dict):
        return {k: _safe_serialise(v) for k, v in obj.items()}
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
    run_field_testing(args)


if __name__ == "__main__":
    main()
