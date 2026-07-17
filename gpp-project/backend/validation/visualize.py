"""
validation/visualize.py
───────────────────────
Visualisation tools for validation & benchmarking results.

All plots use a dark Radarix-style theme for consistency with the
existing pipeline visualisations.

Produces:
    • Bland–Altman plot
    • AHI scatter plot with regression line
    • AHI error histogram
    • Confusion matrix heatmap
    • ROC curve
    • Time-aligned event comparison
    • Threshold optimisation curve
"""

from __future__ import annotations
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from typing import Dict, List, Optional

from . import config as CFG


# ── Theme ───────────────────────────────────────────────────────────

def _apply_dark_theme(ax: plt.Axes, fig: plt.Figure) -> None:
    fig.patch.set_facecolor(CFG.DARK_BG)
    ax.set_facecolor(CFG.DARK_CARD)
    ax.tick_params(colors=CFG.DARK_TEXT)
    ax.xaxis.label.set_color(CFG.DARK_TEXT)
    ax.yaxis.label.set_color(CFG.DARK_TEXT)
    ax.title.set_color(CFG.DARK_TEXT)
    for spine in ax.spines.values():
        spine.set_color("#334155")


# ────────────────────────────────────────────────────────────────────
#  BLAND–ALTMAN PLOT
# ────────────────────────────────────────────────────────────────────

def plot_bland_altman(
    ba_result: Dict,
    title: str = "Bland–Altman: System vs. PSG AHI",
    xlabel: str = "Mean of System & PSG AHI",
    ylabel: str = "Difference (System − PSG)",
    save_path: Optional[str] = None,
) -> Optional[str]:
    """
    Generate a Bland–Altman plot from pre-computed analysis.

    Parameters
    ──────────
    ba_result : dict returned by agreement.bland_altman()
    """
    fig, ax = plt.subplots(figsize=(9, 6))
    _apply_dark_theme(ax, fig)

    means = np.array(ba_result["means"])
    diffs = np.array(ba_result["diffs"])
    md    = ba_result["mean_diff"]
    upper = ba_result["upper_loa"]
    lower = ba_result["lower_loa"]

    ax.scatter(means, diffs, color=CFG.ACCENT_PRIMARY, alpha=0.7, s=50,
              edgecolors="white", linewidths=0.3, zorder=3)

    # Mean line
    ax.axhline(md, color=CFG.ACCENT_WARN, linestyle="--", linewidth=1.5,
               label=f"Bias = {md:.2f}")
    # Upper / lower limits
    ax.axhline(upper, color=CFG.ACCENT_BAD, linestyle=":", linewidth=1.2,
               label=f"+1.96 SD = {upper:.2f}")
    ax.axhline(lower, color=CFG.ACCENT_BAD, linestyle=":", linewidth=1.2,
               label=f"−1.96 SD = {lower:.2f}")
    ax.axhline(0, color="#475569", linestyle="-", linewidth=0.5)

    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.legend(facecolor=CFG.DARK_CARD, edgecolor="#334155",
              labelcolor=CFG.DARK_TEXT, fontsize=9)

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, facecolor=CFG.DARK_BG)
        plt.close(fig)
        return save_path
    plt.close(fig)
    return None


# ────────────────────────────────────────────────────────────────────
#  AHI SCATTER PLOT
# ────────────────────────────────────────────────────────────────────

def plot_ahi_scatter(
    subjects: List[Dict],
    save_path: Optional[str] = None,
) -> Optional[str]:
    """
    Scatter plot of system AHI vs. PSG AHI with regression line
    and correlation annotation.
    """
    sys_ahi = np.array([s["system_ahi"] for s in subjects], dtype=float)
    psg_ahi = np.array([s["psg_ahi"]    for s in subjects], dtype=float)

    fig, ax = plt.subplots(figsize=(8, 7))
    _apply_dark_theme(ax, fig)

    ax.scatter(psg_ahi, sys_ahi, color=CFG.ACCENT_PRIMARY, alpha=0.7,
               s=60, edgecolors="white", linewidths=0.3, zorder=3)

    # Reference line (y=x)
    lim_max = max(np.max(psg_ahi), np.max(sys_ahi)) * 1.1 + 1
    ax.plot([0, lim_max], [0, lim_max], "--", color="#475569",
            linewidth=1, label="y = x")

    # Regression line
    if len(psg_ahi) >= 3:
        coeffs = np.polyfit(psg_ahi, sys_ahi, 1)
        x_line = np.linspace(0, lim_max, 100)
        ax.plot(x_line, np.polyval(coeffs, x_line), "-",
                color=CFG.ACCENT_WARN, linewidth=1.5,
                label=f"Fit: y = {coeffs[0]:.2f}x + {coeffs[1]:.2f}")

        from scipy.stats import pearsonr
        r, p = pearsonr(psg_ahi, sys_ahi)
        ax.annotate(f"r = {r:.3f}  (p = {p:.4f})",
                    xy=(0.05, 0.92), xycoords="axes fraction",
                    color=CFG.DARK_TEXT, fontsize=10,
                    bbox=dict(boxstyle="round,pad=0.3", fc=CFG.DARK_CARD,
                              ec="#334155", alpha=0.9))

    ax.set_xlabel("PSG AHI", fontsize=11)
    ax.set_ylabel("System AHI", fontsize=11)
    ax.set_title("AHI Comparison: System vs. PSG", fontsize=13,
                 fontweight="bold")
    ax.set_xlim(0, lim_max)
    ax.set_ylim(0, lim_max)
    ax.legend(facecolor=CFG.DARK_CARD, edgecolor="#334155",
              labelcolor=CFG.DARK_TEXT, fontsize=9)

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, facecolor=CFG.DARK_BG)
        plt.close(fig)
        return save_path
    plt.close(fig)
    return None


# ────────────────────────────────────────────────────────────────────
#  AHI ERROR HISTOGRAM
# ────────────────────────────────────────────────────────────────────

def plot_ahi_error_histogram(
    errors: List[float],
    save_path: Optional[str] = None,
) -> Optional[str]:
    """Histogram of AHI errors (system − PSG)."""
    fig, ax = plt.subplots(figsize=(8, 5))
    _apply_dark_theme(ax, fig)

    errors_arr = np.array(errors)
    ax.hist(errors_arr, bins="auto", color=CFG.ACCENT_PRIMARY, alpha=0.8,
            edgecolor="#1e293b")
    ax.axvline(0, color=CFG.ACCENT_WARN, linestyle="--", linewidth=1.5)
    ax.axvline(np.mean(errors_arr), color=CFG.ACCENT_BAD, linestyle=":",
               linewidth=1.5, label=f"Mean = {np.mean(errors_arr):.2f}")

    ax.set_xlabel("AHI Error (System − PSG)", fontsize=11)
    ax.set_ylabel("Count", fontsize=11)
    ax.set_title("Distribution of AHI Errors", fontsize=13, fontweight="bold")
    ax.legend(facecolor=CFG.DARK_CARD, edgecolor="#334155",
              labelcolor=CFG.DARK_TEXT, fontsize=9)

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, facecolor=CFG.DARK_BG)
        plt.close(fig)
        return save_path
    plt.close(fig)
    return None


# ────────────────────────────────────────────────────────────────────
#  CONFUSION MATRIX HEATMAP
# ────────────────────────────────────────────────────────────────────

def plot_confusion_matrix(
    cm_result: Dict,
    title: str = "Confusion Matrix",
    save_path: Optional[str] = None,
) -> Optional[str]:
    """
    Annotated heatmap from a confusion matrix dict.

    Parameters
    ──────────
    cm_result : dict with "matrix" (list of lists) and "labels"
    """
    matrix = np.array(cm_result["matrix"])
    labels = cm_result["labels"]

    fig, ax = plt.subplots(figsize=(7, 6))
    _apply_dark_theme(ax, fig)

    im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    # Annotations
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            val = matrix[i, j]
            colour = "white" if val > matrix.max() * 0.5 else CFG.DARK_TEXT
            ax.text(j, i, str(val), ha="center", va="center",
                    fontsize=11, color=colour, fontweight="bold")

    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlabel("Predicted", fontsize=11)
    ax.set_ylabel("Reference (PSG)", fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold")

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, facecolor=CFG.DARK_BG)
        plt.close(fig)
        return save_path
    plt.close(fig)
    return None


# ────────────────────────────────────────────────────────────────────
#  ROC CURVE
# ────────────────────────────────────────────────────────────────────

def plot_roc_curve(
    roc_result: Dict,
    save_path: Optional[str] = None,
) -> Optional[str]:
    """
    ROC curve from ahi_roc_curve() result.
    """
    tpr = np.array(roc_result.get("tpr", []))
    fpr = np.array(roc_result.get("fpr", []))
    auc = roc_result.get("auc", 0)

    if len(tpr) == 0:
        return None

    fig, ax = plt.subplots(figsize=(7, 6))
    _apply_dark_theme(ax, fig)

    ax.plot(fpr, tpr, color=CFG.ACCENT_PRIMARY, linewidth=2,
            label=f"AUC = {auc:.3f}")
    ax.plot([0, 1], [0, 1], "--", color="#475569", linewidth=1,
            label="Chance")

    # Mark optimal point
    best_t = roc_result.get("best_threshold")
    best_sens = roc_result.get("best_sensitivity", 0)
    best_spec = roc_result.get("best_specificity", 0)
    if best_t is not None:
        ax.scatter([1 - best_spec], [best_sens], color=CFG.ACCENT_WARN,
                   s=100, zorder=5, edgecolors="white", linewidths=1.5)
        ax.annotate(f"Threshold = {best_t}\nSens = {best_sens:.2f}\n"
                    f"Spec = {best_spec:.2f}",
                    xy=(1 - best_spec, best_sens),
                    xytext=(1 - best_spec + 0.05, best_sens - 0.1),
                    color=CFG.DARK_TEXT, fontsize=9,
                    arrowprops=dict(arrowstyle="->", color=CFG.ACCENT_WARN))

    ax.set_xlabel("False Positive Rate (1 − Specificity)", fontsize=11)
    ax.set_ylabel("True Positive Rate (Sensitivity)", fontsize=11)
    ax.set_title("ROC Curve — AHI Screening", fontsize=13, fontweight="bold")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.legend(facecolor=CFG.DARK_CARD, edgecolor="#334155",
              labelcolor=CFG.DARK_TEXT, fontsize=10)

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, facecolor=CFG.DARK_BG)
        plt.close(fig)
        return save_path
    plt.close(fig)
    return None


# ────────────────────────────────────────────────────────────────────
#  TIME-ALIGNED EVENT COMPARISON
# ────────────────────────────────────────────────────────────────────

EVENT_COLORS = {
    "Normal":    "#4ade80",
    "Irregular": "#f59e0b",
    "Apnea":     "#ef4444",
    "Hypopnea":  "#fb923c",
    "Motion":    "#94a3b8",
}


def plot_event_comparison(
    ref_events: List[Dict],
    pred_events: List[Dict],
    title: str = "Event Timeline: System vs. PSG",
    save_path: Optional[str] = None,
) -> Optional[str]:
    """
    Side-by-side timeline comparing reference and predicted events.
    """
    fig, axes = plt.subplots(2, 1, figsize=(14, 5), sharex=True)
    for ax in axes:
        _apply_dark_theme(ax, fig)

    for ax, events, label in [
        (axes[0], ref_events, "PSG Reference"),
        (axes[1], pred_events, "System Prediction"),
    ]:
        for evt in events:
            t0 = evt.get("timestamp_start", 0)
            t1 = evt.get("timestamp_end", t0 + 1)
            etype = evt.get("event_type", "Normal")
            color = EVENT_COLORS.get(etype, "#64748b")
            ax.barh(0, t1 - t0, left=t0, height=0.6, color=color, alpha=0.8)
        ax.set_ylabel(label, fontsize=10, color=CFG.DARK_TEXT)
        ax.set_yticks([])

    axes[1].set_xlabel("Time (s)", fontsize=11)
    axes[0].set_title(title, fontsize=13, fontweight="bold")

    # Legend
    patches = [mpatches.Patch(color=c, label=l) for l, c in EVENT_COLORS.items()]
    axes[0].legend(handles=patches, loc="upper right", fontsize=8,
                   facecolor=CFG.DARK_CARD, edgecolor="#334155",
                   labelcolor=CFG.DARK_TEXT)

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, facecolor=CFG.DARK_BG)
        plt.close(fig)
        return save_path
    plt.close(fig)
    return None


# ────────────────────────────────────────────────────────────────────
#  THRESHOLD OPTIMISATION CURVE
# ────────────────────────────────────────────────────────────────────

def plot_threshold_curve(
    opt_result: Dict,
    save_path: Optional[str] = None,
) -> Optional[str]:
    """
    Plot F1 / Precision / Recall vs. confidence threshold.
    """
    curve = opt_result.get("threshold_curve", [])
    if not curve:
        return None

    thresholds = [c["threshold"] for c in curve]
    f1s        = [c["f1"]        for c in curve]
    precs      = [c["precision"] for c in curve]
    recs       = [c["recall"]    for c in curve]

    fig, ax = plt.subplots(figsize=(9, 5))
    _apply_dark_theme(ax, fig)

    ax.plot(thresholds, f1s,   color=CFG.ACCENT_PRIMARY, linewidth=2, label="F1")
    ax.plot(thresholds, precs, color=CFG.ACCENT_GOOD,    linewidth=1.5, label="Precision")
    ax.plot(thresholds, recs,  color=CFG.ACCENT_WARN,    linewidth=1.5, label="Recall")

    best_t = opt_result.get("best_threshold", 0)
    best_f1 = opt_result.get("best_f1", 0)
    ax.axvline(best_t, color=CFG.ACCENT_BAD, linestyle=":", linewidth=1.5)
    ax.scatter([best_t], [best_f1], color=CFG.ACCENT_BAD, s=80, zorder=5,
               edgecolors="white", linewidths=1.5)
    ax.annotate(f"Best: t={best_t:.3f}, F1={best_f1:.3f}",
                xy=(best_t, best_f1), xytext=(best_t + 0.05, best_f1 - 0.05),
                color=CFG.DARK_TEXT, fontsize=9)

    ax.set_xlabel("Confidence Threshold", fontsize=11)
    ax.set_ylabel("Score", fontsize=11)
    ax.set_title("Threshold Optimisation Curve", fontsize=13, fontweight="bold")
    ax.legend(facecolor=CFG.DARK_CARD, edgecolor="#334155",
              labelcolor=CFG.DARK_TEXT, fontsize=10)

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, facecolor=CFG.DARK_BG)
        plt.close(fig)
        return save_path
    plt.close(fig)
    return None


# ────────────────────────────────────────────────────────────────────
#  SAVE ALL PLOTS
# ────────────────────────────────────────────────────────────────────

def save_all_plots(
    validation_results: Dict,
    output_dir: str,
    prefix: str = "validation",
) -> Dict[str, str]:
    """
    Generate all applicable validation plots and save to output_dir.

    Returns dict mapping plot name → file path.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths: Dict[str, str] = {}

    # Bland–Altman
    ba = validation_results.get("bland_altman")
    if ba:
        p = os.path.join(output_dir, f"{prefix}_bland_altman.png")
        plot_bland_altman(ba, save_path=p)
        paths["bland_altman"] = p

    # AHI scatter
    subjects = validation_results.get("ahi_comparison", {}).get("per_subject")
    if subjects:
        p = os.path.join(output_dir, f"{prefix}_ahi_scatter.png")
        plot_ahi_scatter(subjects, save_path=p)
        paths["ahi_scatter"] = p

        # Error histogram
        errors = [s["ahi_error"] for s in subjects]
        p = os.path.join(output_dir, f"{prefix}_ahi_error_hist.png")
        plot_ahi_error_histogram(errors, save_path=p)
        paths["ahi_error_hist"] = p

    # Confusion matrices
    for key in ("event_confusion", "stage_confusion", "severity_confusion"):
        cm = validation_results.get(key)
        if cm and "matrix" in cm:
            title_map = {
                "event_confusion":    "Event Detection Confusion Matrix",
                "stage_confusion":    "Sleep Stage Confusion Matrix",
                "severity_confusion": "AHI Severity Confusion Matrix",
            }
            p = os.path.join(output_dir, f"{prefix}_{key}.png")
            plot_confusion_matrix(cm, title=title_map.get(key, key), save_path=p)
            paths[key] = p

    # ROC curve
    roc = validation_results.get("roc_curve")
    if roc and roc.get("tpr"):
        p = os.path.join(output_dir, f"{prefix}_roc_curve.png")
        plot_roc_curve(roc, save_path=p)
        paths["roc_curve"] = p

    # Event timeline
    ref_evts  = validation_results.get("ref_events")
    pred_evts = validation_results.get("pred_events")
    if ref_evts and pred_evts:
        p = os.path.join(output_dir, f"{prefix}_event_timeline.png")
        plot_event_comparison(ref_evts, pred_evts, save_path=p)
        paths["event_timeline"] = p

    # Threshold curve
    thresh = validation_results.get("threshold_optimization")
    if thresh and thresh.get("threshold_curve"):
        p = os.path.join(output_dir, f"{prefix}_threshold_curve.png")
        plot_threshold_curve(thresh, save_path=p)
        paths["threshold_curve"] = p

    return paths
