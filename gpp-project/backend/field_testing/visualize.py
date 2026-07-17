"""
field_testing/visualize.py
──────────────────────────
Dark-themed (Radarix) field-testing performance plots.

Public API
──────────
plot_placement_accuracy(placement_metrics, metric, output_path)
plot_error_boxplots(test_results, output_path)
plot_robustness_radar(robustness, output_path)
plot_timeline_overlay(recording, output_path)
plot_environment_heatmap(env_scores, output_path)
plot_field_performance(test_results, robustness, output_dir)  → Dict[str,str]
"""

from __future__ import annotations
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from typing import Any, Dict, List, Optional

from . import config as CFG


# ────────────────────────────────────────────────────────────────────
#  THEME HELPERS
# ────────────────────────────────────────────────────────────────────

def _apply_dark_theme(ax, fig=None):
    if fig is not None:
        fig.patch.set_facecolor(CFG.DARK_BG)
    ax.set_facecolor(CFG.DARK_CARD)
    ax.tick_params(colors=CFG.DARK_TEXT)
    ax.xaxis.label.set_color(CFG.DARK_TEXT)
    ax.yaxis.label.set_color(CFG.DARK_TEXT)
    ax.title.set_color(CFG.DARK_TEXT)
    for spine in ax.spines.values():
        spine.set_color(CFG.DARK_TEXT)


def _save_fig(fig, path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)


# ────────────────────────────────────────────────────────────────────
#  PLACEMENT VS ACCURACY SCATTER
# ────────────────────────────────────────────────────────────────────

def plot_placement_accuracy(
    placement_metrics: Dict[str, Dict],
    metric: str = "rr_mae",
    title: str = "Placement vs RR MAE",
    output_path: Optional[str] = None,
) -> str:
    """
    Scatter plot of a chosen metric across radar placements.

    Returns output path.
    """
    placements = list(placement_metrics.keys())
    means = []
    stds = []
    for pl in placements:
        m = placement_metrics[pl].get(metric, {})
        means.append(m.get("mean", 0) if isinstance(m, dict) else 0)
        stds.append(m.get("std", 0)   if isinstance(m, dict) else 0)

    if output_path is None:
        output_path = f"placement_{metric}.png"

    fig, ax = plt.subplots(figsize=(10, 5))
    _apply_dark_theme(ax, fig)

    x = np.arange(len(placements))
    colors = [CFG.ACCENT_COLORS[i % len(CFG.ACCENT_COLORS)]
              for i in range(len(placements))]
    ax.bar(x, means, yerr=stds, color=colors, alpha=0.85,
           edgecolor=CFG.DARK_TEXT, linewidth=0.5, capsize=4)
    ax.set_xticks(x)
    ax.set_xticklabels(placements, rotation=35, ha="right", fontsize=8)
    ax.set_ylabel(metric)
    ax.set_title(title, fontsize=13, fontweight="bold")

    _save_fig(fig, output_path)
    return output_path


# ────────────────────────────────────────────────────────────────────
#  ERROR DISTRIBUTION BOX PLOTS
# ────────────────────────────────────────────────────────────────────

def plot_error_boxplots(
    test_results: List[Dict[str, Any]],
    title: str = "RR & HR Error Distributions",
    output_path: Optional[str] = None,
) -> str:
    """
    Side-by-side box plots of RR and HR absolute errors across all
    test sessions.
    """
    rr_abs_all, hr_abs_all = [], []
    for r in test_results:
        rr_err = np.asarray(r.get("rr_errors", []), dtype=float)
        hr_err = np.asarray(r.get("hr_errors", []), dtype=float)
        rr_abs_all.append(np.abs(rr_err[~np.isnan(rr_err)]))
        hr_abs_all.append(np.abs(hr_err[~np.isnan(hr_err)]))

    if output_path is None:
        output_path = "error_boxplots.png"

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    _apply_dark_theme(axes[0], fig)
    _apply_dark_theme(axes[1])

    # RR
    bp1 = axes[0].boxplot(
        rr_abs_all, patch_artist=True, notch=True,
        medianprops=dict(color=CFG.ACCENT_BAD, linewidth=2),
    )
    for patch, c in zip(bp1["boxes"],
                         [CFG.ACCENT_COLORS[i % len(CFG.ACCENT_COLORS)]
                          for i in range(len(rr_abs_all))]):
        patch.set_facecolor(c)
        patch.set_alpha(0.7)
    axes[0].set_title("RR Absolute Error (breaths/min)", fontsize=11,
                       fontweight="bold")
    axes[0].set_xlabel("Session")
    axes[0].set_ylabel("|Error|")

    # HR
    bp2 = axes[1].boxplot(
        hr_abs_all, patch_artist=True, notch=True,
        medianprops=dict(color=CFG.ACCENT_BAD, linewidth=2),
    )
    for patch, c in zip(bp2["boxes"],
                         [CFG.ACCENT_COLORS[i % len(CFG.ACCENT_COLORS)]
                          for i in range(len(hr_abs_all))]):
        patch.set_facecolor(c)
        patch.set_alpha(0.7)
    axes[1].set_title("HR Absolute Error (bpm)", fontsize=11,
                       fontweight="bold")
    axes[1].set_xlabel("Session")
    axes[1].set_ylabel("|Error|")

    fig.suptitle(title, fontsize=14, fontweight="bold",
                  color=CFG.DARK_TEXT, y=1.02)
    fig.tight_layout()
    _save_fig(fig, output_path)
    return output_path


# ────────────────────────────────────────────────────────────────────
#  ROBUSTNESS RADAR / SPIDER CHART
# ────────────────────────────────────────────────────────────────────

def plot_robustness_radar(
    robustness: Dict[str, Any],
    title: str = "Robustness Breakdown",
    output_path: Optional[str] = None,
) -> str:
    """
    Spider chart of the five robustness dimensions.
    """
    detail = robustness.get("overall_detail", robustness)

    categories = ["RR", "HR", "Events", "Staging", "Motion"]
    keys       = ["rr_score", "hr_score", "event_score",
                  "stage_score", "motion_score"]
    values = [detail.get(k, 0) for k in keys]
    values.append(values[0])  # close polygon

    angles = np.linspace(0, 2 * np.pi, len(categories),
                          endpoint=False).tolist()
    angles.append(angles[0])

    if output_path is None:
        output_path = "robustness_radar.png"

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor(CFG.DARK_BG)
    ax.set_facecolor(CFG.DARK_CARD)

    ax.plot(angles, values, color=CFG.ACCENT_PRIMARY, linewidth=2)
    ax.fill(angles, values, color=CFG.ACCENT_PRIMARY, alpha=0.25)

    ax.set_thetagrids(np.degrees(angles[:-1]), categories,
                       color=CFG.DARK_TEXT, fontsize=10)
    ax.set_ylim(0, 1.05)
    ax.set_rticks([0.25, 0.5, 0.75, 1.0])
    ax.tick_params(colors=CFG.DARK_TEXT)
    ax.yaxis.set_tick_params(labelcolor=CFG.DARK_TEXT)
    ax.grid(color=CFG.DARK_TEXT, alpha=0.2)

    agg = detail.get("aggregate", 0)
    tier = detail.get("tier", "")
    ax.set_title(f"{title}\nScore: {agg:.2f} ({tier})",
                  fontsize=13, fontweight="bold", color=CFG.DARK_TEXT,
                  pad=20)

    _save_fig(fig, output_path)
    return output_path


# ────────────────────────────────────────────────────────────────────
#  TIMELINE OVERLAY (radar vs ground truth)
# ────────────────────────────────────────────────────────────────────

def plot_timeline_overlay(
    recording: Dict[str, Any],
    title: str = "Radar vs Ground Truth",
    output_path: Optional[str] = None,
) -> str:
    """
    Dual-axis overlay of RR and HR (radar vs truth) over time.
    """
    rr_radar = np.asarray(recording["rr_radar"], dtype=float)
    rr_truth = np.asarray(recording["rr_truth"], dtype=float)
    hr_radar = np.asarray(recording["hr_radar"], dtype=float)
    hr_truth = np.asarray(recording["hr_truth"], dtype=float)

    n = len(rr_radar)
    t_min = np.arange(n) * CFG.EPOCH_DURATION_SEC / 60.0

    if output_path is None:
        output_path = "timeline_overlay.png"

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
    _apply_dark_theme(ax1, fig)
    _apply_dark_theme(ax2)

    # RR
    ax1.plot(t_min, rr_truth, color=CFG.ACCENT_GOOD, linewidth=1,
             alpha=0.8, label="Ground Truth")
    ax1.plot(t_min, rr_radar, color=CFG.ACCENT_PRIMARY, linewidth=1,
             alpha=0.6, label="Radar")
    ax1.set_ylabel("RR (breaths/min)")
    ax1.set_title(title + " – Respiration Rate", fontsize=12,
                   fontweight="bold")
    ax1.legend(loc="upper right", facecolor=CFG.DARK_CARD,
               edgecolor=CFG.DARK_TEXT, labelcolor=CFG.DARK_TEXT)

    # HR
    ax2.plot(t_min, hr_truth, color=CFG.ACCENT_GOOD, linewidth=1,
             alpha=0.8, label="Ground Truth")
    ax2.plot(t_min, hr_radar, color=CFG.ACCENT_PRIMARY, linewidth=1,
             alpha=0.6, label="Radar")
    ax2.set_ylabel("HR (bpm)")
    ax2.set_xlabel("Time (min)")
    ax2.set_title(title + " – Heart Rate", fontsize=12,
                   fontweight="bold")
    ax2.legend(loc="upper right", facecolor=CFG.DARK_CARD,
               edgecolor=CFG.DARK_TEXT, labelcolor=CFG.DARK_TEXT)

    fig.tight_layout()
    _save_fig(fig, output_path)
    return output_path


# ────────────────────────────────────────────────────────────────────
#  ENVIRONMENT HEATMAP
# ────────────────────────────────────────────────────────────────────

def plot_environment_heatmap(
    env_scores: Dict[str, Dict],
    title: str = "Environment Robustness Heatmap",
    output_path: Optional[str] = None,
) -> str:
    """
    Heatmap of robustness score dimensions across environments.
    """
    envs  = list(env_scores.keys())
    dims  = ["rr_score", "hr_score", "event_score",
             "stage_score", "motion_score", "aggregate"]
    labels = ["RR", "HR", "Events", "Staging", "Motion", "Overall"]

    matrix = np.zeros((len(envs), len(dims)))
    for i, env in enumerate(envs):
        for j, d in enumerate(dims):
            matrix[i, j] = env_scores[env].get(d, 0)

    if output_path is None:
        output_path = "environment_heatmap.png"

    fig, ax = plt.subplots(figsize=(max(8, len(dims) * 1.4),
                                     max(4, len(envs) * 0.6)))
    _apply_dark_theme(ax, fig)

    cmap = LinearSegmentedColormap.from_list(
        "radarix", [CFG.ACCENT_BAD, CFG.ACCENT_WARN, CFG.ACCENT_GOOD], N=256,
    )
    im = ax.imshow(matrix, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.04)
    cbar.ax.yaxis.set_tick_params(color=CFG.DARK_TEXT)
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color=CFG.DARK_TEXT)

    ax.set_xticks(range(len(dims)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_yticks(range(len(envs)))
    ax.set_yticklabels(envs, fontsize=8)

    # Annotate
    for i in range(len(envs)):
        for j in range(len(dims)):
            v = matrix[i, j]
            color = CFG.DARK_BG if v > 0.6 else CFG.DARK_TEXT
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    fontsize=8, color=color)

    ax.set_title(title, fontsize=13, fontweight="bold")
    fig.tight_layout()
    _save_fig(fig, output_path)
    return output_path


# ────────────────────────────────────────────────────────────────────
#  MASTER PLOT GENERATOR
# ────────────────────────────────────────────────────────────────────

def plot_field_performance(
    test_results: List[Dict[str, Any]],
    field_evaluation: Dict[str, Any],
    robustness: Dict[str, Any],
    output_dir: str = "field_testing_output",
    prefix: str = "field",
) -> Dict[str, str]:
    """
    Generate all field-testing plots and return a dict of paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths: Dict[str, str] = {}

    # 1. Placement accuracy (RR)
    try:
        p = plot_placement_accuracy(
            field_evaluation.get("per_placement", {}),
            metric="rr_mae",
            title="RR MAE by Placement",
            output_path=os.path.join(output_dir,
                                      f"{prefix}_placement_rr.png"),
        )
        paths["placement_rr"] = p
    except Exception:
        pass

    # 2. Placement accuracy (HR)
    try:
        p = plot_placement_accuracy(
            field_evaluation.get("per_placement", {}),
            metric="hr_mae",
            title="HR MAE by Placement",
            output_path=os.path.join(output_dir,
                                      f"{prefix}_placement_hr.png"),
        )
        paths["placement_hr"] = p
    except Exception:
        pass

    # 3. Error box plots
    try:
        p = plot_error_boxplots(
            test_results,
            output_path=os.path.join(output_dir,
                                      f"{prefix}_error_boxplots.png"),
        )
        paths["error_boxplots"] = p
    except Exception:
        pass

    # 4. Robustness radar
    try:
        p = plot_robustness_radar(
            robustness,
            output_path=os.path.join(output_dir,
                                      f"{prefix}_robustness_radar.png"),
        )
        paths["robustness_radar"] = p
    except Exception:
        pass

    # 5. Environment heatmap
    try:
        env_scores = robustness.get("per_environment", {})
        if env_scores:
            p = plot_environment_heatmap(
                env_scores,
                output_path=os.path.join(output_dir,
                                          f"{prefix}_env_heatmap.png"),
            )
            paths["env_heatmap"] = p
    except Exception:
        pass

    # 6. Timeline overlay for first recording with arrays
    if test_results:
        first = test_results[0]
        # Need the original recording for timeline — use the result
        # which also has rr_errors etc.  Build a pseudo-recording.
        # (real runs pass recordings separately; here we skip if keys missing)

    return paths
