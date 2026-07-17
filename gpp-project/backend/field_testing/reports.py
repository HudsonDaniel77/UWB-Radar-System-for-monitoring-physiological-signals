"""
field_testing/reports.py
────────────────────────
Generate human-readable deployment recommendation reports.

Public API
──────────
report_deployment_recommendations(robustness, field_eval)  → str
write_report(text, output_path)                            → str
"""

from __future__ import annotations
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from . import config as CFG
from .robustness import classify_tier


# ────────────────────────────────────────────────────────────────────
#  MAIN REPORT GENERATOR
# ────────────────────────────────────────────────────────────────────

def report_deployment_recommendations(
    robustness: Dict[str, Any],
    field_eval: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Produce a multi-section plain-text report with:

    1. Executive summary
    2. Overall robustness
    3. Per-placement analysis  (best / worst)
    4. Per-environment analysis
    5. Deployment recommendations
    6. Worst-case mitigations
    7. Suggested configuration defaults
    """
    lines: List[str] = []

    lines.append("=" * 72)
    lines.append("  RADARIX  –  FIELD TESTING & DEPLOYMENT RECOMMENDATION REPORT")
    lines.append("=" * 72)
    lines.append(f"  Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    lines.append(f"  Tests evaluated: {robustness.get('n_tests', '?')}")
    lines.append("")

    # ── 1. Executive Summary ──────────────────────────────────────
    lines.append("─" * 72)
    lines.append("1. EXECUTIVE SUMMARY")
    lines.append("─" * 72)
    overall = robustness.get("overall_score", 0)
    tier    = robustness.get("overall_tier", "Unknown")
    lines.append(f"  Overall Deployment Readiness Score : {overall:.2f} / 1.00")
    lines.append(f"  Tier                              : {tier}")
    lines.append(f"  Best Placement                    : {robustness.get('best_placement', 'N/A')}")
    lines.append(f"  Worst Placement                   : {robustness.get('worst_placement', 'N/A')}")
    lines.append(f"  Best Environment                  : {robustness.get('best_environment', 'N/A')}")
    lines.append(f"  Worst Environment                 : {robustness.get('worst_environment', 'N/A')}")
    lines.append("")

    # ── 2. Overall Robustness Detail ──────────────────────────────
    lines.append("─" * 72)
    lines.append("2. OVERALL ROBUSTNESS BREAKDOWN")
    lines.append("─" * 72)
    detail = robustness.get("overall_detail", {})
    _append_score_table(lines, detail)
    lines.append("")

    # ── 3. Per-Placement Analysis ─────────────────────────────────
    lines.append("─" * 72)
    lines.append("3. PER-PLACEMENT ANALYSIS")
    lines.append("─" * 72)
    pl_scores = robustness.get("per_placement", {})
    if pl_scores:
        lines.append(f"  {'Placement':<22} {'RR':>6} {'HR':>6} "
                      f"{'Event':>6} {'Stage':>6} {'Motion':>6} "
                      f"{'Agg':>6} {'Tier':<12} {'N':>4}")
        lines.append("  " + "-" * 80)
        for pl in sorted(pl_scores, key=lambda k: pl_scores[k].get("aggregate", 0),
                          reverse=True):
            s = pl_scores[pl]
            lines.append(
                f"  {pl:<22} "
                f"{s.get('rr_score', 0):>6.2f} "
                f"{s.get('hr_score', 0):>6.2f} "
                f"{s.get('event_score', 0):>6.2f} "
                f"{s.get('stage_score', 0):>6.2f} "
                f"{s.get('motion_score', 0):>6.2f} "
                f"{s.get('aggregate', 0):>6.2f} "
                f"{s.get('tier', '?'):<12} "
                f"{s.get('n_sessions', 0):>4}",
            )
    else:
        lines.append("  (no placement data)")
    lines.append("")

    # ── 4. Per-Environment Analysis ───────────────────────────────
    lines.append("─" * 72)
    lines.append("4. PER-ENVIRONMENT ANALYSIS")
    lines.append("─" * 72)
    env_scores = robustness.get("per_environment", {})
    if env_scores:
        lines.append(f"  {'Environment':<28} {'RR':>6} {'HR':>6} "
                      f"{'Event':>6} {'Stage':>6} {'Motion':>6} "
                      f"{'Agg':>6} {'Tier':<12}")
        lines.append("  " + "-" * 80)
        for ek in sorted(env_scores, key=lambda k: env_scores[k].get("aggregate", 0),
                          reverse=True):
            s = env_scores[ek]
            lines.append(
                f"  {ek:<28} "
                f"{s.get('rr_score', 0):>6.2f} "
                f"{s.get('hr_score', 0):>6.2f} "
                f"{s.get('event_score', 0):>6.2f} "
                f"{s.get('stage_score', 0):>6.2f} "
                f"{s.get('motion_score', 0):>6.2f} "
                f"{s.get('aggregate', 0):>6.2f} "
                f"{s.get('tier', '?'):<12}",
            )
    else:
        lines.append("  (no environment data)")
    lines.append("")

    # ── 5. Deployment Recommendations ─────────────────────────────
    lines.append("─" * 72)
    lines.append("5. DEPLOYMENT RECOMMENDATIONS")
    lines.append("─" * 72)
    recs = _generate_recommendations(robustness, field_eval)
    for i, rec in enumerate(recs, 1):
        lines.append(f"  {i}. {rec}")
    lines.append("")

    # ── 6. Worst-Case Mitigations ─────────────────────────────────
    lines.append("─" * 72)
    lines.append("6. WORST-CASE CONDITIONS & MITIGATIONS")
    lines.append("─" * 72)
    mits = _generate_mitigations(robustness, field_eval)
    for m in mits:
        lines.append(f"  • {m}")
    lines.append("")

    # ── 7. Suggested Defaults ─────────────────────────────────────
    lines.append("─" * 72)
    lines.append("7. SUGGESTED CONFIGURATION DEFAULTS FOR HOME DEPLOYMENT")
    lines.append("─" * 72)
    defaults = _suggest_defaults(robustness)
    for k, v in defaults.items():
        lines.append(f"  {k:<30} : {v}")
    lines.append("")

    lines.append("=" * 72)
    lines.append("  END OF REPORT")
    lines.append("=" * 72)
    lines.append("")

    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────
#  WRITE TO FILE
# ────────────────────────────────────────────────────────────────────

def write_report(
    text: str,
    output_path: str,
) -> str:
    """Write report string to file.  Returns path."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    return output_path


# ────────────────────────────────────────────────────────────────────
#  INTERNAL HELPERS
# ────────────────────────────────────────────────────────────────────

def _append_score_table(lines: List[str], detail: Dict):
    """Append a formatted score table to lines."""
    keys = [
        ("rr_score",     "Respiration Rate"),
        ("hr_score",     "Heart Rate"),
        ("event_score",  "Sleep Event Detection"),
        ("stage_score",  "Sleep Stage Classification"),
        ("motion_score", "Motion / Posture"),
    ]
    for key, label in keys:
        val = detail.get(key, 0)
        tier = classify_tier(val)
        bar = _bar(val)
        lines.append(f"  {label:<30} {val:>5.2f}  {bar}  {tier}")

    agg = detail.get("aggregate", 0)
    lines.append(f"  {'AGGREGATE':<30} {agg:>5.2f}  {_bar(agg)}  "
                  f"{classify_tier(agg)}")


def _bar(val: float, width: int = 20) -> str:
    """ASCII progress bar."""
    filled = int(round(val * width))
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def _generate_recommendations(
    robustness: Dict,
    field_eval: Optional[Dict],
) -> List[str]:
    """Generate actionable deployment recommendations."""
    recs = []
    best_pl = robustness.get("best_placement")
    worst_pl = robustness.get("worst_placement")
    overall = robustness.get("overall_score", 0)

    if best_pl:
        recs.append(
            f"PRIMARY PLACEMENT: Use '{best_pl}' for optimal "
            f"performance across all metrics.",
        )

    if worst_pl and worst_pl != best_pl:
        recs.append(
            f"AVOID: '{worst_pl}' showed the lowest robustness. "
            f"Use only as a fallback with additional calibration.",
        )

    detail = robustness.get("overall_detail", {})
    if detail.get("rr_score", 1) < 0.5:
        recs.append(
            "RR ACCURACY is below acceptable.  Consider reducing "
            "radar-to-subject distance or switching mattress type.",
        )
    if detail.get("hr_score", 1) < 0.5:
        recs.append(
            "HR ACCURACY is below acceptable.  Ensure radar is at "
            "torso height and minimise metallic obstructions.",
        )
    if detail.get("event_score", 1) < 0.5:
        recs.append(
            "SLEEP EVENT DETECTION needs improvement.  Retrain the "
            "event classifier with more real-world labelled data.",
        )
    if detail.get("stage_score", 1) < 0.5:
        recs.append(
            "SLEEP STAGING agreement is low.  Consider adding "
            "additional features or using a multi-sensor setup.",
        )
    if detail.get("motion_score", 1) < 0.5:
        recs.append(
            "MOTION/POSTURE detection is unreliable.  Adding an "
            "under-bed auxiliary radar can improve coverage.",
        )

    if overall >= 0.75:
        recs.append(
            "System is DEPLOYMENT-READY for home use with the "
            f"recommended placement ('{best_pl}').",
        )
    elif overall >= 0.50:
        recs.append(
            "System requires TARGETED IMPROVEMENTS before wide "
            "deployment.  Focus on the weakest sub-scores above.",
        )
    else:
        recs.append(
            "System is NOT READY for unsupervised deployment.  "
            "Conduct further lab testing and algorithm tuning.",
        )

    return recs


def _generate_mitigations(
    robustness: Dict,
    field_eval: Optional[Dict],
) -> List[str]:
    """Mitigation strategies for worst-case conditions."""
    mits = []

    worst_env = robustness.get("worst_environment", "")
    if worst_env:
        mits.append(
            f"Environment '{worst_env}' is the most challenging.  "
            "Use thinner bedding or reposition radar closer.",
        )

    env_scores = robustness.get("per_environment", {})
    for ek, sc in env_scores.items():
        if sc.get("aggregate", 1) < 0.4:
            mits.append(
                f"'{ek}' scores below 0.40 — "
                "consider environment-specific calibration.",
            )

    pl_scores = robustness.get("per_placement", {})
    for pl, sc in pl_scores.items():
        if sc.get("rr_score", 1) < 0.5 and sc.get("hr_score", 1) >= 0.5:
            mits.append(
                f"'{pl}' has good HR but poor RR — try adjusting "
                "radar tilt angle by ±5° towards the chest.",
            )

    if not mits:
        mits.append("No critical worst-case conditions identified.")

    return mits


def _suggest_defaults(robustness: Dict) -> Dict[str, str]:
    """Suggested configuration defaults for home deployment."""
    best_pl = robustness.get("best_placement", "bedside_right")
    coords = CFG.PLACEMENT_COORDS_DEFAULT.get(best_pl, (0.5, 0.0, 0.7))

    defaults = {
        "radar_placement":      best_pl,
        "radar_coords (m)":     f"({coords[0]:.2f}, {coords[1]:.2f}, {coords[2]:.2f})",
        "recommended_height":   f"{coords[2]:.2f} m (mattress-level)",
        "max_range":            "1.5 m",
        "epoch_duration":       f"{CFG.EPOCH_DURATION_SEC} s",
        "sampling_rate":        f"{CFG.SAMPLING_RATE_HZ} Hz",
        "preferred_bedding":    "thin_sheet or single_blanket",
        "avoid_occlusions":     "partner_present, pet_present",
        "min_recording_time":   f"{CFG.MIN_RECORDING_DURATION_SEC // 3600} hr",
    }
    return defaults
