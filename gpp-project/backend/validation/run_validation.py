#!/usr/bin/env python
"""
run_validation.py
─────────────────
CLI entry-point for the Validation & Benchmarking pipeline.

Usage
─────
  python run_validation.py \
      --system-events  path/to/system_events.json \
      --psg-events     path/to/psg_events.csv \
      --system-stages  path/to/system_stages.json \
      --psg-stages     path/to/psg_stages.csv \
      --psg-ahi        path/to/psg_ahi.csv \
      --output         path/to/output_dir \
      --no-plots

  python run_validation.py --demo --output path/to/output_dir

All flags are optional.  At minimum provide --system-events + --psg-events
OR use --demo to run with synthetic data.

The script prints a summary to stdout and emits a JSON block between
VALIDATION_RESULT_BEGIN / VALIDATION_RESULT_END markers that the Flask
pipeline can capture.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import datetime
import numpy as np

# Ensure package is importable when running from the backend/ dir
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

from validation import config as CFG
from validation.io_utils import (
    load_psg_events_csv,
    load_system_events_json,
    load_psg_stages_csv,
    load_system_stages_json,
    load_psg_ahi_csv,
)
from validation.event_metrics import compute_event_metrics, compute_epoch_metrics
from validation.ahi import compute_ahi, compare_ahi, screening_performance
from validation.agreement import bland_altman, compute_icc
from validation.staging_validation import validate_stages
from validation.threshold_optimization import ahi_roc_curve, multi_cutoff_screening
from validation.visualize import save_all_plots
from validation.reporting import report_validation_results


# ────────────────────────────────────────────────────────────────────
#  SYNTHETIC DEMO DATA
# ────────────────────────────────────────────────────────────────────

def _make_demo_data() -> dict:
    """Return synthetic data for demonstration / testing."""
    np.random.seed(42)
    n_subjects = 8
    n_epochs = 60  # per subject, ~30 min at 30-s epochs

    # ── Events (per subject) ────────────────────────────────
    psg_events_all = []
    sys_events_all = []
    for _ in range(n_subjects):
        n_psg = np.random.randint(5, 20)
        starts = sorted(np.random.uniform(0, 1800, n_psg))
        psg_ev = []
        sys_ev = []
        for s in starts:
            dur = np.random.uniform(10, 40)
            etype = np.random.choice(["Apnea", "Hypopnea", "Irregular"],
                                     p=[0.4, 0.3, 0.3])
            psg_ev.append({
                "timestamp_start": float(s),
                "timestamp_end": float(s + dur),
                "event_type": etype,
            })
            # system detects ~80 % of events, with slight timing jitter
            if np.random.rand() < 0.80:
                jitter_s = np.random.normal(0, 3)
                jitter_e = np.random.normal(0, 3)
                conf = float(np.clip(np.random.normal(0.75, 0.15), 0.1, 1.0))
                sys_ev.append({
                    "timestamp_start": float(s + jitter_s),
                    "timestamp_end": float(s + dur + jitter_e),
                    "event_type": etype,
                    "confidence": conf,
                })
        # system also has ~15 % false positive rate
        n_fp = max(1, int(0.15 * n_psg))
        for _ in range(n_fp):
            fp_s = float(np.random.uniform(0, 1800))
            fp_dur = float(np.random.uniform(10, 25))
            sys_ev.append({
                "timestamp_start": fp_s,
                "timestamp_end": fp_s + fp_dur,
                "event_type": np.random.choice(["Apnea", "Hypopnea"]),
                "confidence": float(np.clip(np.random.normal(0.45, 0.15), 0.1, 0.9)),
            })
        psg_events_all.append(psg_ev)
        sys_events_all.append(sys_ev)

    # ── Build per-subject AHI dicts ─────────────────────────
    total_hours = n_epochs * 30 / 3600  # 0.5 h
    subjects = []
    for i in range(n_subjects):
        sid = f"subj_{i+1:03d}"
        psg_cnt = len([e for e in psg_events_all[i]
                       if e["event_type"] in ("Apnea", "Hypopnea", "Irregular")])
        sys_cnt = len([e for e in sys_events_all[i]
                       if e["event_type"] in ("Apnea", "Hypopnea", "Irregular")])
        subjects.append({
            "subject_id": sid,
            "psg_ahi": psg_cnt / total_hours,
            "system_ahi": sys_cnt / total_hours,
        })

    # ── Sleep stages ────────────────────────────────────────
    stage_labels = ["Wake", "Light", "Deep", "REM"]
    psg_stages = np.random.choice(stage_labels, n_epochs).tolist()
    # system agrees ~70 %
    sys_stages = []
    for s in psg_stages:
        if np.random.rand() < 0.70:
            sys_stages.append(s)
        else:
            sys_stages.append(np.random.choice(stage_labels))

    return {
        "psg_events": psg_events_all[0],   # single-subject event demo
        "sys_events": sys_events_all[0],
        "subjects": subjects,
        "psg_stages": psg_stages,
        "sys_stages": sys_stages,
    }


# ────────────────────────────────────────────────────────────────────
#  MAIN RUNNER
# ────────────────────────────────────────────────────────────────────

def run_validation(args: argparse.Namespace) -> dict:
    """
    Execute the full validation pipeline and return consolidated results.
    """
    results: dict = {"timestamp": datetime.datetime.now().isoformat()}
    demo = args.demo

    # ================================================================
    #  LOAD DATA
    # ================================================================
    if demo:
        data = _make_demo_data()
        psg_events = data["psg_events"]
        sys_events = data["sys_events"]
        subjects = data["subjects"]
        psg_stages = data["psg_stages"]
        sys_stages = data["sys_stages"]
    else:
        psg_events = []
        sys_events = []
        subjects = []
        psg_stages = []
        sys_stages = []

        if args.psg_events:
            psg_events = load_psg_events_csv(args.psg_events)
        if args.system_events:
            sys_events = load_system_events_json(args.system_events)
        if args.psg_stages:
            psg_stage_records = load_psg_stages_csv(args.psg_stages)
            psg_stages = [r["stage"] for r in psg_stage_records]
        if args.system_stages:
            sys_stage_records = load_system_stages_json(args.system_stages)
            sys_stages = [r["stage"] for r in sys_stage_records]
        if args.psg_ahi:
            ahi_rows = load_psg_ahi_csv(args.psg_ahi)
            # Build subjects list (system AHI would need to come from events)
            for row in ahi_rows:
                subjects.append({
                    "subject_id": row["subject_id"],
                    "psg_ahi": row["ahi"],
                    "system_ahi": 0.0,  # placeholder
                })

    # ================================================================
    #  EVENT-LEVEL METRICS
    # ================================================================
    if psg_events and sys_events:
        print("[validation] computing event-level metrics …")
        em = compute_event_metrics(psg_events, sys_events)
        results["event_metrics"] = em

        # Epoch-level (30-s grid) — build label arrays from events
        ep_max = max(
            max(e.get("timestamp_end", 0) for e in psg_events),
            max(e.get("timestamp_end", 0) for e in sys_events),
        )
        n_ep = max(1, int(np.ceil(ep_max / 30)))

        def _events_to_epoch_labels(events, n_epochs):
            labels = ["Normal"] * n_epochs
            for e in events:
                start_ep = int(e.get("timestamp_start", 0) // 30)
                end_ep = int(np.ceil(e.get("timestamp_end", 0) / 30))
                etype = e.get("event_type", "Normal")
                for ep in range(max(0, start_ep), min(n_epochs, end_ep)):
                    if etype in ("Apnea", "Hypopnea", "Irregular"):
                        labels[ep] = etype
            return labels

        ref_ep_labels = _events_to_epoch_labels(psg_events, n_ep)
        sys_ep_labels = _events_to_epoch_labels(sys_events, n_ep)
        ep = compute_epoch_metrics(ref_ep_labels, sys_ep_labels)
        results["epoch_metrics"] = ep

    # ================================================================
    #  AHI COMPARISON
    # ================================================================
    if subjects:
        print("[validation] computing AHI comparison …")
        ahi_cmp = compare_ahi(subjects)
        results["ahi_comparison"] = ahi_cmp

        # Bland-Altman on AHI
        sys_ahis = np.array([s["system_ahi"] for s in subjects])
        psg_ahis = np.array([s["psg_ahi"] for s in subjects])
        ba = bland_altman(sys_ahis, psg_ahis)
        results["bland_altman"] = ba

        # ICC
        if len(subjects) >= 3:
            icc = compute_icc(sys_ahis, psg_ahis)
            results["icc"] = icc

        # Screening
        scr_multi = multi_cutoff_screening(subjects)
        results["screening"] = scr_multi

        # ROC
        roc = ahi_roc_curve(
            subjects,
            psg_cutoff=CFG.DEFAULT_SCREENING_CUTOFF,
        )
        results["roc_curve"] = roc

    # ================================================================
    #  SLEEP STAGING VALIDATION
    # ================================================================
    if psg_stages and sys_stages:
        print("[validation] validating sleep stages …")
        n_min = min(len(psg_stages), len(sys_stages))
        stg = validate_stages(
            ref_stages=psg_stages[:n_min],
            pred_stages=sys_stages[:n_min],
        )
        results["staging_validation"] = stg

    # ================================================================
    #  VISUALISATIONS
    # ================================================================
    if not args.no_plots:
        print("[validation] generating plots …")
        # Attach events so visualize can build the timeline plot
        if psg_events:
            results["ref_events"] = psg_events
        if sys_events:
            results["pred_events"] = sys_events
        plot_paths = save_all_plots(
            validation_results=results,
            output_dir=args.output,
        )
        results["plot_paths"] = plot_paths

    # ================================================================
    #  REPORTS
    # ================================================================
    print("[validation] writing reports …")
    report_paths = report_validation_results(results, args.output)
    results["report_paths"] = report_paths

    return results


# ────────────────────────────────────────────────────────────────────
#  CLI
# ────────────────────────────────────────────────────────────────────

def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Radarix Validation & Benchmarking Pipeline",
    )
    p.add_argument("--system-events", type=str, default=None,
                   help="Path to system event detections (JSON)")
    p.add_argument("--psg-events", type=str, default=None,
                   help="Path to PSG reference events (CSV)")
    p.add_argument("--system-stages", type=str, default=None,
                   help="Path to system sleep-stage predictions (JSON)")
    p.add_argument("--psg-stages", type=str, default=None,
                   help="Path to PSG reference stages (CSV)")
    p.add_argument("--psg-ahi", type=str, default=None,
                   help="Path to PSG AHI scores per subject (CSV)")
    p.add_argument("--output", type=str,
                   default=os.path.join(SCRIPT_DIR, "output"),
                   help="Output directory for reports & plots")
    p.add_argument("--no-plots", action="store_true",
                   help="Skip plot generation")
    p.add_argument("--demo", action="store_true",
                   help="Run with synthetic demo data")
    return p.parse_args(argv)


def _json_default(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)


def main(argv=None) -> None:
    args = _parse_args(argv)
    print("=" * 60)
    print("  Radarix Validation & Benchmarking Pipeline")
    print("=" * 60)

    results = run_validation(args)

    # Summary
    em = results.get("event_metrics", {})
    ahi = results.get("ahi_comparison", {})
    stg = results.get("staging_validation", {})

    print("\n── Summary ──────────────────────────────────────")
    if em:
        print(f"  Events  :  P={em.get('precision',0):.3f}  "
              f"R={em.get('recall',0):.3f}  F1={em.get('f1',0):.3f}  "
              f"(TP={em.get('tp',0)} FP={em.get('fp',0)} FN={em.get('fn',0)})")
    if ahi:
        ae = ahi.get("ahi_errors", {})
        print(f"  AHI     :  MAE={ae.get('mae',0):.2f}  RMSE={ae.get('rmse',0):.2f}")
    if stg:
        print(f"  Staging :  Acc={stg.get('accuracy',0):.3f}  "
              f"κ={stg.get('cohens_kappa',0):.3f}  F1={stg.get('f1_macro',0):.3f}")

    ba = results.get("bland_altman", {})
    if ba:
        print(f"  B-A     :  Bias={ba.get('mean_diff',0):.3f}  "
              f"LoA=[{ba.get('lower_loa',0):.3f}, {ba.get('upper_loa',0):.3f}]")

    rp = results.get("report_paths", {})
    if rp:
        print(f"\n  Reports → {rp.get('json', '')}")
        print(f"            {rp.get('markdown', '')}")

    print("=" * 60)

    # Emit machine-readable block for pipeline.py
    output_block = {k: v for k, v in results.items()}
    output_block.pop("plot_paths", None)
    print("\nVALIDATION_RESULT_BEGIN")
    print(json.dumps(output_block, indent=2, default=_json_default))
    print("VALIDATION_RESULT_END")


if __name__ == "__main__":
    main()
