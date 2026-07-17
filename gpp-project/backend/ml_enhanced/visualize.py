"""
ml_enhanced/visualize.py
────────────────────────
Publication-ready dark-themed visualisations for the enhanced ML
pipeline.

All plots use the Radarix dark theme defined in config.py.
"""

from __future__ import annotations
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from typing import Any, Dict, List, Optional, Tuple

from . import config as CFG


# ────────────────────────────────────────────────────────────────────
#  THEME HELPERS
# ────────────────────────────────────────────────────────────────────

def _apply_dark_theme(ax, fig=None):
    """Apply Radarix dark theme to axes and figure."""
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
    fig.savefig(path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)


# ────────────────────────────────────────────────────────────────────
#  CONFUSION MATRIX
# ────────────────────────────────────────────────────────────────────

def plot_confusion_matrix(
    cm: list | np.ndarray,
    label_names: List[str],
    title: str = "Confusion Matrix",
    output_path: Optional[str] = None,
) -> str:
    """
    Plot a confusion matrix heatmap with dark theme.

    Returns output path.
    """
    cm = np.array(cm)
    n = len(label_names)

    fig, ax = plt.subplots(figsize=(max(6, n * 1.2), max(5, n)))
    _apply_dark_theme(ax, fig)

    cmap = LinearSegmentedColormap.from_list(
        "radarix", [CFG.DARK_CARD, CFG.ACCENT_PRIMARY], N=256,
    )
    im = ax.imshow(cm, interpolation="nearest", cmap=cmap)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.yaxis.set_tick_params(color=CFG.DARK_TEXT)
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color=CFG.DARK_TEXT)

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(label_names, rotation=45, ha="right", fontsize=9)
    ax.set_yticklabels(label_names, fontsize=9)

    # Annotate cells
    thresh = cm.max() / 2
    for i in range(n):
        for j in range(n):
            color = CFG.DARK_BG if cm[i, j] > thresh else CFG.DARK_TEXT
            ax.text(j, i, str(int(cm[i, j])), ha="center", va="center",
                    color=color, fontsize=10, fontweight="bold")

    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(title, fontsize=13, fontweight="bold")

    if output_path is None:
        output_path = "confusion_matrix.png"
    _save_fig(fig, output_path)
    return output_path


# ────────────────────────────────────────────────────────────────────
#  ROC CURVE
# ────────────────────────────────────────────────────────────────────

def plot_roc_curve(
    roc_data: Dict,
    title: str = "ROC Curve",
    output_path: Optional[str] = None,
) -> str:
    """
    Plot ROC curve from {fpr, tpr} data.
    """
    fig, ax = plt.subplots(figsize=(7, 6))
    _apply_dark_theme(ax, fig)

    fpr = roc_data["fpr"]
    tpr = roc_data["tpr"]
    ax.plot(fpr, tpr, color=CFG.ACCENT_PRIMARY, linewidth=2, label="Model")
    ax.plot([0, 1], [0, 1], color=CFG.ACCENT_BAD, linestyle="--",
            linewidth=1, alpha=0.6, label="Chance")
    ax.fill_between(fpr, tpr, alpha=0.15, color=CFG.ACCENT_PRIMARY)

    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.legend(loc="lower right", facecolor=CFG.DARK_CARD,
              edgecolor=CFG.DARK_TEXT, labelcolor=CFG.DARK_TEXT)

    if output_path is None:
        output_path = "roc_curve.png"
    _save_fig(fig, output_path)
    return output_path


# ────────────────────────────────────────────────────────────────────
#  MODEL COMPARISON BAR CHART
# ────────────────────────────────────────────────────────────────────

def plot_model_comparison(
    comparison_table: List[Dict],
    metric: str = "f1",
    title: str = "Model Comparison",
    output_path: Optional[str] = None,
) -> str:
    """
    Horizontal bar chart comparing models on a given metric.
    """
    models = [r["model"] for r in comparison_table if "error" not in r]
    scores = [r.get(metric, 0) for r in comparison_table if "error" not in r]

    fig, ax = plt.subplots(figsize=(9, max(4, len(models) * 0.6)))
    _apply_dark_theme(ax, fig)

    colors = CFG.ACCENT_COLORS[:len(models)]
    bars = ax.barh(models, scores, color=colors, edgecolor=CFG.DARK_TEXT,
                   linewidth=0.5, height=0.55)

    for bar, score in zip(bars, scores):
        ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height() / 2,
                f"{score:.3f}", va="center", color=CFG.DARK_TEXT, fontsize=10)

    ax.set_xlabel(metric.upper())
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlim(0, max(scores) * 1.15 if scores else 1)
    ax.invert_yaxis()

    if output_path is None:
        output_path = "model_comparison.png"
    _save_fig(fig, output_path)
    return output_path


# ────────────────────────────────────────────────────────────────────
#  FEATURE IMPORTANCE
# ────────────────────────────────────────────────────────────────────

def plot_feature_importance(
    importances: Dict[str, float],
    top_k: int = 15,
    title: str = "Feature Importance",
    output_path: Optional[str] = None,
) -> str:
    """
    Horizontal bar chart of top-k features.
    """
    ranked = sorted(importances.items(), key=lambda x: x[1], reverse=True)
    ranked = ranked[:top_k]

    names  = [r[0] for r in ranked]
    values = [r[1] for r in ranked]

    fig, ax = plt.subplots(figsize=(9, max(4, len(names) * 0.45)))
    _apply_dark_theme(ax, fig)

    ax.barh(names, values, color=CFG.ACCENT_PRIMARY, edgecolor=CFG.DARK_TEXT,
            linewidth=0.5, height=0.55)
    ax.set_xlabel("Importance")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.invert_yaxis()

    if output_path is None:
        output_path = "feature_importance.png"
    _save_fig(fig, output_path)
    return output_path


# ────────────────────────────────────────────────────────────────────
#  TRAINING HISTORY (loss / accuracy curves)
# ────────────────────────────────────────────────────────────────────

def plot_training_history(
    history: Dict[str, List[float]],
    title: str = "Training History",
    output_path: Optional[str] = None,
) -> str:
    """
    Plot loss and accuracy curves from TF/Keras training history.
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for ax in axes:
        _apply_dark_theme(ax, fig)

    # Loss
    ax0 = axes[0]
    if "loss" in history:
        ax0.plot(history["loss"], color=CFG.ACCENT_PRIMARY, label="Train")
    if "val_loss" in history:
        ax0.plot(history["val_loss"], color=CFG.ACCENT_WARN, label="Val")
    ax0.set_xlabel("Epoch")
    ax0.set_ylabel("Loss")
    ax0.set_title("Loss", fontweight="bold")
    ax0.legend(facecolor=CFG.DARK_CARD, edgecolor=CFG.DARK_TEXT,
               labelcolor=CFG.DARK_TEXT)

    # Accuracy
    ax1 = axes[1]
    if "accuracy" in history:
        ax1.plot(history["accuracy"], color=CFG.ACCENT_GOOD, label="Train")
    if "val_accuracy" in history:
        ax1.plot(history["val_accuracy"], color=CFG.ACCENT_WARN, label="Val")
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Accuracy")
    ax1.set_title("Accuracy", fontweight="bold")
    ax1.legend(facecolor=CFG.DARK_CARD, edgecolor=CFG.DARK_TEXT,
               labelcolor=CFG.DARK_TEXT)

    fig.suptitle(title, color=CFG.DARK_TEXT, fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.93])

    if output_path is None:
        output_path = "training_history.png"
    _save_fig(fig, output_path)
    return output_path


# ────────────────────────────────────────────────────────────────────
#  SAVE ALL PLOTS
# ────────────────────────────────────────────────────────────────────

def save_all_plots(
    training_results: Dict[str, Dict],
    comparison_table: List[Dict],
    output_dir: str,
    prefix: str = "ml_enhanced",
) -> Dict[str, str]:
    """
    Generate all available plots from training results.

    Parameters
    ──────────
    training_results : dict returned by train_ml_models()
    comparison_table : list returned by build_comparison_table()
    output_dir       : directory to write plots
    prefix           : filename prefix

    Returns dict mapping plot name → file path.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths: Dict[str, str] = {}

    # Model comparison
    try:
        p = plot_model_comparison(
            comparison_table, metric="f1",
            title=f"{prefix} – Model Comparison (F1)",
            output_path=os.path.join(output_dir, f"{prefix}_comparison_f1.png"),
        )
        paths["comparison_f1"] = p
    except Exception:
        pass

    try:
        p = plot_model_comparison(
            comparison_table, metric="accuracy",
            title=f"{prefix} – Model Comparison (Accuracy)",
            output_path=os.path.join(output_dir, f"{prefix}_comparison_acc.png"),
        )
        paths["comparison_acc"] = p
    except Exception:
        pass

    # Per-model plots
    for model_type, res in training_results.items():
        if "error" in res or res.get("model") is None:
            continue

        # Confusion matrix
        vm = res.get("val_metrics", {})
        cm = vm.get("confusion_matrix")
        labels = res.get("label_names", [])
        if cm is not None and labels:
            try:
                p = plot_confusion_matrix(
                    cm, labels,
                    title=f"{model_type} – Confusion Matrix",
                    output_path=os.path.join(
                        output_dir, f"{prefix}_{model_type}_cm.png"),
                )
                paths[f"{model_type}_cm"] = p
            except Exception:
                pass

        # Feature importance (classical only)
        model = res.get("model")
        if not res.get("is_deep", False) and model is not None:
            try:
                from .feature_engineering import feature_importance_from_model
                imp = feature_importance_from_model(model)
                if imp:
                    p = plot_feature_importance(
                        imp, top_k=15,
                        title=f"{model_type} – Feature Importance",
                        output_path=os.path.join(
                            output_dir, f"{prefix}_{model_type}_fi.png"),
                    )
                    paths[f"{model_type}_fi"] = p
            except Exception:
                pass

        # Training history (deep only)
        train_info = res.get("train_info", {})
        history = train_info.get("history", {})
        if history and "loss" in history:
            try:
                p = plot_training_history(
                    history,
                    title=f"{model_type} – Training History",
                    output_path=os.path.join(
                        output_dir, f"{prefix}_{model_type}_history.png"),
                )
                paths[f"{model_type}_history"] = p
            except Exception:
                pass

    return paths
