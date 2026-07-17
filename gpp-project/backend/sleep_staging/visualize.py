"""
sleep_staging/visualize.py
──────────────────────────
Visualisation utilities for sleep‑stage classification.

Plots:
    • Hypnogram (sleep stage timeline)
    • Feature trends with stage overlays
    • ROC curves for multi‑class classification
    • Training history (for deep models)
"""

from __future__ import annotations
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from typing import Dict, List, Optional

from . import config as CFG


# ── Dark theme matching Radarix UI ─────────────────────────────────
_BG   = "#0f172a"
_FG   = "#e2e8f0"
_GRID = "#334155"

STAGE_COLORS = {
    "Wake":  "#ef4444",
    "REM":   "#f59e0b",
    "Light": "#3b82f6",
    "Deep":  "#8b5cf6",
    "N1":    "#60a5fa",
    "N2":    "#3b82f6",
    "N3":    "#8b5cf6",
}

STAGE_Y_POS = {
    "Wake": 4, "REM": 3, "Light": 2, "Deep": 1,
    "N1": 3.5, "N2": 2.5, "N3": 1.5,
}


def _apply_dark_theme(ax: plt.Axes) -> None:
    ax.set_facecolor(_BG)
    ax.tick_params(colors=_FG)
    ax.xaxis.label.set_color(_FG)
    ax.yaxis.label.set_color(_FG)
    ax.title.set_color(_FG)
    for spine in ax.spines.values():
        spine.set_color(_GRID)
    ax.grid(True, color=_GRID, alpha=0.3, linestyle="--")


# ────────────────────────────────────────────────────────────────────
#  HYPNOGRAM
# ────────────────────────────────────────────────────────────────────

def plot_hypnogram(
    epoch_centers: np.ndarray,
    labels: List[str],
    epoch_duration_sec: float = CFG.EPOCH_DURATION_SEC,
    title: str = "Sleep Hypnogram",
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot classic stepped hypnogram (sleep stage vs time).

    Parameters
    ──────────
    epoch_centers : 1‑D array of epoch centre times (seconds)
    labels        : list of stage labels per epoch
    """
    fig, ax = plt.subplots(figsize=(14, 4))
    fig.patch.set_facecolor(_BG)
    _apply_dark_theme(ax)

    used_stages = sorted(set(labels), key=lambda s: STAGE_Y_POS.get(s, 0))

    # convert times to minutes
    t_min = epoch_centers / 60.0

    y_vals = [STAGE_Y_POS.get(l, 0) for l in labels]
    colors = [STAGE_COLORS.get(l, "#94a3b8") for l in labels]

    # step plot
    for i in range(len(t_min) - 1):
        ax.fill_betweenx(
            [y_vals[i] - 0.4, y_vals[i] + 0.4],
            t_min[i], t_min[i + 1],
            color=colors[i], alpha=0.7,
        )

    ax.set_xlabel("Time (minutes)")
    ax.set_ylabel("Sleep Stage")
    ax.set_title(title, fontsize=13, fontweight="bold")

    # y‑ticks = stage names
    ytick_vals = sorted(set(STAGE_Y_POS[s] for s in used_stages))
    ytick_names = [s for s in used_stages]
    ax.set_yticks([STAGE_Y_POS[s] for s in used_stages])
    ax.set_yticklabels(used_stages)
    ax.invert_yaxis()

    # legend
    patches = [Patch(facecolor=STAGE_COLORS.get(s, "#94a3b8"), label=s)
               for s in used_stages]
    ax.legend(handles=patches, loc="upper right", fontsize=8,
              facecolor=_BG, edgecolor=_GRID, labelcolor=_FG)

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, facecolor=_BG)
    plt.close(fig)
    return fig


# ────────────────────────────────────────────────────────────────────
#  FEATURE TRENDS WITH STAGE OVERLAY
# ────────────────────────────────────────────────────────────────────

def plot_feature_trends(
    epoch_centers: np.ndarray,
    labels: List[str],
    rr_bpm: np.ndarray,
    hr_bpm: np.ndarray,
    motion_index: np.ndarray,
    epoch_duration_sec: float = CFG.EPOCH_DURATION_SEC,
    title: str = "Feature Trends & Sleep Stages",
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    3‑panel plot: RR / HR / Motion with coloured sleep‑stage background.
    """
    fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True)
    fig.patch.set_facecolor(_BG)
    t_min = epoch_centers / 60.0

    signals = [
        (rr_bpm, "Respiration Rate (BPM)", "#22d3ee"),
        (hr_bpm, "Heart Rate (BPM)", "#f472b6"),
        (motion_index, "Motion Index", "#a3e635"),
    ]

    for ax, (sig, ylabel, line_color) in zip(axes, signals):
        _apply_dark_theme(ax)

        # draw coloured background per epoch
        for i in range(len(t_min) - 1):
            ax.axvspan(t_min[i], t_min[i + 1],
                       color=STAGE_COLORS.get(labels[i], "#1e293b"),
                       alpha=0.15)

        ax.plot(t_min[:len(sig)], sig[:len(t_min)], color=line_color, linewidth=1)
        ax.set_ylabel(ylabel, fontsize=9)

    axes[-1].set_xlabel("Time (minutes)")
    axes[0].set_title(title, fontsize=13, fontweight="bold")

    # shared legend
    used = sorted(set(labels), key=lambda s: STAGE_Y_POS.get(s, 0))
    patches = [Patch(facecolor=STAGE_COLORS.get(s, "#94a3b8"), label=s, alpha=0.5)
               for s in used]
    axes[0].legend(handles=patches, loc="upper right", fontsize=7,
                   facecolor=_BG, edgecolor=_GRID, labelcolor=_FG)

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, facecolor=_BG)
    plt.close(fig)
    return fig


# ────────────────────────────────────────────────────────────────────
#  ROC CURVES
# ────────────────────────────────────────────────────────────────────

def plot_roc_curves(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    label_names: List[str],
    title: str = "ROC Curves (One‑vs‑Rest)",
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot multi‑class ROC curves (one‑vs‑rest).
    """
    from sklearn.metrics import roc_curve, auc

    fig, ax = plt.subplots(figsize=(8, 8))
    fig.patch.set_facecolor(_BG)
    _apply_dark_theme(ax)

    present = sorted(set(y_true))
    line_colors = ["#ef4444", "#f59e0b", "#3b82f6", "#8b5cf6", "#10b981"]

    for i, cls_id in enumerate(present):
        name = label_names[cls_id] if cls_id < len(label_names) else str(cls_id)
        binary = (y_true == cls_id).astype(int)
        if y_proba.shape[1] > cls_id:
            fpr, tpr, _ = roc_curve(binary, y_proba[:, cls_id])
            roc_auc = auc(fpr, tpr)
            color = line_colors[i % len(line_colors)]
            ax.plot(fpr, tpr, color=color, lw=2,
                    label=f"{name} (AUC = {roc_auc:.3f})")

    ax.plot([0, 1], [0, 1], "--", color=_GRID, lw=1)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.legend(loc="lower right", fontsize=9,
              facecolor=_BG, edgecolor=_GRID, labelcolor=_FG)

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, facecolor=_BG)
    plt.close(fig)
    return fig


# ────────────────────────────────────────────────────────────────────
#  CONFUSION MATRIX HEATMAP
# ────────────────────────────────────────────────────────────────────

def plot_confusion_matrix(
    cm: np.ndarray,
    label_names: List[str],
    title: str = "Confusion Matrix",
    save_path: Optional[str] = None,
) -> plt.Figure:
    """Plot confusion matrix as a heatmap."""
    fig, ax = plt.subplots(figsize=(7, 6))
    fig.patch.set_facecolor(_BG)
    _apply_dark_theme(ax)

    n = cm.shape[0]
    im = ax.imshow(cm, interpolation="nearest", cmap="Blues")

    # annotate cells
    for i in range(n):
        for j in range(n):
            color = "white" if cm[i, j] > cm.max() / 2 else _FG
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    color=color, fontsize=11)

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    tick_labels = label_names[:n]
    ax.set_xticklabels(tick_labels, rotation=45, ha="right")
    ax.set_yticklabels(tick_labels)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(title, fontsize=13, fontweight="bold")

    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, facecolor=_BG)
    plt.close(fig)
    return fig


# ────────────────────────────────────────────────────────────────────
#  SLEEP STRUCTURE PIE CHART
# ────────────────────────────────────────────────────────────────────

def plot_sleep_structure(
    structure: Dict,
    label_names: Optional[List[str]] = None,
    title: str = "Sleep Architecture",
    save_path: Optional[str] = None,
) -> plt.Figure:
    """Pie chart of sleep stage proportions."""
    if label_names is None:
        label_names = CFG.STAGE_LABELS_REDUCED

    fig, ax = plt.subplots(figsize=(7, 7))
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)

    pct = structure.get("pct_per_stage", {})
    sizes = [pct.get(s, 0) for s in label_names]
    colors = [STAGE_COLORS.get(s, "#94a3b8") for s in label_names]

    # filter out zero-size slices
    filtered = [(s, sz, c) for s, sz, c in zip(label_names, sizes, colors) if sz > 0]
    if not filtered:
        plt.close(fig)
        return fig

    names, sizes, colors = zip(*filtered)

    wedges, texts, autotexts = ax.pie(
        sizes, labels=names, colors=colors, autopct="%1.1f%%",
        startangle=90, textprops={"color": _FG, "fontsize": 10},
    )
    for at in autotexts:
        at.set_fontsize(9)
        at.set_color("white")

    eff = structure.get("sleep_efficiency_pct", 0)
    rating = structure.get("efficiency_rating", "N/A")
    ax.set_title(f"{title}\nEfficiency: {eff:.1f}% ({rating})",
                 fontsize=13, fontweight="bold", color=_FG)

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, facecolor=_BG)
    plt.close(fig)
    return fig


# ────────────────────────────────────────────────────────────────────
#  SAVE ALL PLOTS
# ────────────────────────────────────────────────────────────────────

def save_all_plots(
    prediction_result: Dict,
    metrics_result: Optional[Dict] = None,
    data: Optional[Dict[str, np.ndarray]] = None,
    output_dir: str = ".",
    prefix: str = "sleep_staging",
    label_names: Optional[List[str]] = None,
) -> Dict[str, str]:
    """
    Generate and save all visualisation plots.

    Returns dict mapping plot name → file path.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths: Dict[str, str] = {}

    if label_names is None:
        label_names = CFG.STAGE_LABELS_REDUCED

    ec = prediction_result.get("epoch_centers", np.array([]))
    labels = prediction_result.get("labels", [])

    if len(ec) > 0 and len(labels) > 0:
        # Hypnogram
        p = os.path.join(output_dir, f"{prefix}_hypnogram.png")
        plot_hypnogram(ec, labels, save_path=p)
        paths["hypnogram"] = p

        # Sleep structure pie
        structure = prediction_result.get("sleep_structure", {})
        if structure:
            p = os.path.join(output_dir, f"{prefix}_sleep_structure.png")
            plot_sleep_structure(structure, label_names, save_path=p)
            paths["sleep_structure"] = p

        # Feature trends
        if data is not None:
            # aggregate per-epoch means for plotting
            from .features import epoch_indices as _ei
            n = len(data["timestamps"])
            epoch_len = int(CFG.EPOCH_DURATION_SEC * CFG.SAMPLING_RATE)
            idx = _ei(n, epoch_len, 0)
            rr_means = np.array([np.mean(data["rr_bpm"][s:e]) for s, e in idx])
            hr_means = np.array([np.mean(data["hr_bpm"][s:e]) for s, e in idx])
            mot_means = np.array([np.mean(data["motion_scores"][s:e]) for s, e in idx])

            min_len = min(len(ec), len(rr_means), len(labels))
            p = os.path.join(output_dir, f"{prefix}_feature_trends.png")
            plot_feature_trends(ec[:min_len], labels[:min_len],
                                rr_means[:min_len], hr_means[:min_len],
                                mot_means[:min_len], save_path=p)
            paths["feature_trends"] = p

    # Metrics plots
    if metrics_result:
        cm = metrics_result.get("confusion_matrix")
        if cm is not None:
            p = os.path.join(output_dir, f"{prefix}_confusion_matrix.png")
            plot_confusion_matrix(np.array(cm), label_names, save_path=p)
            paths["confusion_matrix"] = p

    return paths
