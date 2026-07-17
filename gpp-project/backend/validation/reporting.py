"""
validation/reporting.py
───────────────────────
Structured report generation for validation results.

Produces:
    • JSON report (machine-readable)
    • CSV per-subject table
    • Markdown summary report (human-readable, publication-ready)
"""

from __future__ import annotations
import os, json, csv, datetime
import numpy as np
from typing import Any, Dict, List, Optional

from . import config as CFG


# ────────────────────────────────────────────────────────────────────
#  FULL VALIDATION REPORT
# ────────────────────────────────────────────────────────────────────

def report_validation_results(
    results: Dict,
    output_dir: str,
    prefix: str = "validation_report",
) -> Dict[str, str]:
    """
    Generate all report files from consolidated validation results.

    Parameters
    ──────────
    results    : dict containing all validation outputs (event_metrics,
                 ahi_comparison, bland_altman, staging, roc, etc.)
    output_dir : directory to write reports
    prefix     : filename prefix

    Returns
    ───────
    paths : dict mapping format → absolute file path
    """
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    paths: Dict[str, str] = {}

    # ── JSON ────────────────────────────────────────────────────────
    json_path = os.path.join(output_dir, f"{prefix}_{ts}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=_json_default)
    paths["json"] = json_path

    # ── Per-subject CSV ─────────────────────────────────────────────
    per_subj = results.get("ahi_comparison", {}).get("per_subject", [])
    if per_subj:
        csv_path = os.path.join(output_dir, f"{prefix}_per_subject_{ts}.csv")
        _write_csv(per_subj, csv_path)
        paths["csv"] = csv_path

    # ── Markdown ────────────────────────────────────────────────────
    md_path = os.path.join(output_dir, f"{prefix}_{ts}.md")
    md_text = _build_markdown(results, ts)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_text)
    paths["markdown"] = md_path

    return paths


# ────────────────────────────────────────────────────────────────────
#  MARKDOWN BUILDER
# ────────────────────────────────────────────────────────────────────

def _build_markdown(results: Dict, ts: str) -> str:
    """Build a publication-ready Markdown summary."""
    lines: List[str] = []
    lines.append("# Validation & Benchmarking Report")
    lines.append(f"\n*Generated: {ts}*\n")

    # ── Event Detection ─────────────────────────────────────────────
    em = results.get("event_metrics")
    if em:
        lines.append("## Event Detection Performance\n")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| True Positives | {em.get('tp', 0)} |")
        lines.append(f"| False Positives | {em.get('fp', 0)} |")
        lines.append(f"| False Negatives | {em.get('fn', 0)} |")
        lines.append(f"| Precision | {em.get('precision', 0):.4f} |")
        lines.append(f"| Recall (Sensitivity) | {em.get('recall', 0):.4f} |")
        lines.append(f"| F1-score | {em.get('f1', 0):.4f} |")
        lines.append("")

        dur = em.get("duration_errors", {})
        if dur.get("n", 0) > 0:
            lines.append("### Duration Error\n")
            lines.append(f"| Metric | Value |")
            lines.append(f"|--------|-------|")
            lines.append(f"| MAE (s) | {dur.get('mae', 0):.2f} |")
            lines.append(f"| RMSE (s) | {dur.get('rmse', 0):.2f} |")
            lines.append(f"| Bias (s) | {dur.get('bias', 0):.2f} |")
            lines.append(f"| N matched | {dur.get('n', 0)} |")
            lines.append("")

        # Per-type table
        pt = em.get("per_type", {})
        if pt:
            lines.append("### Per Event Type\n")
            lines.append("| Type | TP | FP | FN | Precision | Recall | F1 |")
            lines.append("|------|----|----|-----|-----------|--------|----|")
            for etype, m in pt.items():
                lines.append(
                    f"| {etype} | {m['tp']} | {m['fp']} | {m['fn']} "
                    f"| {m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} |"
                )
            lines.append("")

    # ── AHI Comparison ──────────────────────────────────────────────
    ahi = results.get("ahi_comparison")
    if ahi:
        lines.append("## AHI Comparison\n")
        agg = ahi.get("aggregate", {})
        lines.append(f"- **N subjects:** {agg.get('n_subjects', 0)}")
        lines.append(f"- **Mean System AHI:** {agg.get('mean_system_ahi', 0):.2f}")
        lines.append(f"- **Mean PSG AHI:** {agg.get('mean_psg_ahi', 0):.2f}")
        lines.append("")

        err = ahi.get("ahi_errors", {})
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| MAE | {err.get('mae', 0):.3f} |")
        lines.append(f"| RMSE | {err.get('rmse', 0):.3f} |")
        lines.append(f"| Bias | {err.get('bias', 0):.3f} |")
        lines.append("")

        corr = ahi.get("correlation", {})
        if corr.get("pearson_r") is not None:
            lines.append(f"- **Pearson r:** {corr['pearson_r']:.4f} "
                          f"(p = {corr.get('pearson_p', 0):.6f})")
            lines.append(f"- **Spearman ρ:** {corr.get('spearman_rho', 0):.4f} "
                          f"(p = {corr.get('spearman_p', 0):.6f})")
            lines.append("")

        sa = ahi.get("severity_agreement", {})
        if sa:
            lines.append(f"- **Severity agreement:** "
                          f"{sa.get('exact_match_count', 0)}/{sa.get('n_subjects', 0)} "
                          f"({sa.get('exact_match_pct', 0):.1f}%)")
            lines.append("")

        # Per-subject table
        ps = ahi.get("per_subject", [])
        if ps:
            lines.append("### Per-Subject\n")
            lines.append("| Subject | System AHI | PSG AHI | Error | System Sev. | PSG Sev. | Match |")
            lines.append("|---------|-----------|---------|-------|-------------|----------|-------|")
            for s in ps:
                match_sym = "✓" if s.get("severity_match") else "✗"
                lines.append(
                    f"| {s['subject_id']} | {s['system_ahi']:.2f} "
                    f"| {s['psg_ahi']:.2f} | {s['ahi_error']:.2f} "
                    f"| {s['system_severity']} | {s['psg_severity']} | {match_sym} |"
                )
            lines.append("")

    # ── Bland–Altman ────────────────────────────────────────────────
    ba = results.get("bland_altman")
    if ba:
        lines.append("## Bland–Altman Analysis\n")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Bias (mean diff) | {ba.get('mean_diff', 0):.4f} |")
        lines.append(f"| SD of differences | {ba.get('std_diff', 0):.4f} |")
        lines.append(f"| Upper LoA | {ba.get('upper_loa', 0):.4f} |")
        lines.append(f"| Lower LoA | {ba.get('lower_loa', 0):.4f} |")
        lines.append(f"| % within LoA | {ba.get('pct_within_loa', 0):.1f}% |")
        lines.append(f"| N | {ba.get('n', 0)} |")
        lines.append("")

    # ── ICC ─────────────────────────────────────────────────────────
    icc = results.get("icc")
    if icc and icc.get("icc") is not None:
        lines.append("## Intra-Class Correlation\n")
        lines.append(f"- **ICC ({icc.get('model', 'ICC(2,1)')}):** {icc['icc']:.4f}")
        lines.append(f"- **N:** {icc.get('n', 0)}")
        lines.append("")

    # ── Screening ───────────────────────────────────────────────────
    scr = results.get("screening")
    if scr:
        if isinstance(scr, list):
            lines.append("## Screening Performance\n")
            lines.append("| Cutoff | Sens | Spec | PPV | NPV | TP | TN | FP | FN |")
            lines.append("|--------|------|------|-----|-----|----|----|----|----|")
            for s in scr:
                lines.append(
                    f"| AHI ≥ {s['cutoff']} | {s['sensitivity']:.4f} "
                    f"| {s['specificity']:.4f} | {s['ppv']:.4f} | {s['npv']:.4f} "
                    f"| {s['tp']} | {s['tn']} | {s['fp']} | {s['fn']} |"
                )
            lines.append("")

    # ── ROC ─────────────────────────────────────────────────────────
    roc = results.get("roc_curve")
    if roc and roc.get("auc"):
        lines.append("## ROC Analysis\n")
        lines.append(f"- **AUC:** {roc['auc']:.4f}")
        lines.append(f"- **Optimal threshold:** {roc.get('best_threshold', 0):.2f}")
        lines.append(f"- **Sensitivity at optimal:** {roc.get('best_sensitivity', 0):.4f}")
        lines.append(f"- **Specificity at optimal:** {roc.get('best_specificity', 0):.4f}")
        lines.append(f"- **Youden's J:** {roc.get('youdens_j', 0):.4f}")
        lines.append("")

    # ── Sleep Staging ───────────────────────────────────────────────
    stg = results.get("staging_validation")
    if stg:
        lines.append("## Sleep Stage Validation\n")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Accuracy | {stg.get('accuracy', 0):.4f} |")
        lines.append(f"| Cohen's κ | {stg.get('cohens_kappa', 0):.4f} |")
        lines.append(f"| Precision (macro) | {stg.get('precision_macro', 0):.4f} |")
        lines.append(f"| Recall (macro) | {stg.get('recall_macro', 0):.4f} |")
        lines.append(f"| F1 (macro) | {stg.get('f1_macro', 0):.4f} |")
        lines.append(f"| N epochs | {stg.get('n_epochs', 0)} |")
        lines.append("")

        pc = stg.get("per_class", {})
        if pc:
            lines.append("### Per Stage\n")
            lines.append("| Stage | Precision | Recall | F1 | Support |")
            lines.append("|-------|-----------|--------|----|---------|")
            for stage, m in pc.items():
                lines.append(
                    f"| {stage} | {m['precision']:.4f} | {m['recall']:.4f} "
                    f"| {m['f1']:.4f} | {m['support']} |"
                )
            lines.append("")

    lines.append("---\n*Report generated by Radarix Validation Pipeline*\n")
    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────
#  HELPERS
# ────────────────────────────────────────────────────────────────────

def _write_csv(rows: List[Dict], path: str) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)
