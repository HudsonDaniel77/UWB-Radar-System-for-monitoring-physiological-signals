"""
motion_posture/visualize.py
───────────────────────────
Matplotlib plots for motion & posture context analysis.

Functions
─────────
    plot_motion_timeline      – motion type vs time
    plot_posture_timeline     – posture label vs time
    plot_combined_context     – combined motion + posture + sleep events
    plot_session_summary      – aggregate bar/pie charts
    save_all_plots            – convenience saver
"""

from __future__ import annotations
import os
from typing import Dict, List, Optional

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from . import config as CFG


# ── Colour palettes ─────────────────────────────────────────────────
MOTION_COLORS = {
    "Still":           "#4ade80",
    "Minor Movement":  "#facc15",
    "Major Movement":  "#f97316",
    "Turning":         "#ef4444",
}

POSTURE_COLORS = {
    "Supine":        "#60a5fa",
    "Left Lateral":  "#a78bfa",
    "Right Lateral": "#f472b6",
    "Prone":         "#fb923c",
    "Unknown":       "#6b7280",
}

EVENT_COLORS = {
    "Normal":    "#4ade80",
    "Irregular": "#facc15",
    "Apnea":     "#ef4444",
    "Motion":    "#60a5fa",
}


# ────────────────────────────────────────────────────────────────────
#  MOTION TIMELINE
# ────────────────────────────────────────────────────────────────────

def plot_motion_timeline(
    motion_records: List[Dict],
    title: str = "Motion Type Timeline",
    figsize: tuple = (16, 3.5),
) -> plt.Figure:
    """Horizontal band plot of motion type over time."""
    fig, ax = _dark_axes(figsize)

    label_to_y = {l: i for i, l in enumerate(CFG.MOTION_LABELS)}

    for r in motion_records:
        t0, t1 = r["timestamp_start"], r["timestamp_end"]
        lab = r["motion_type"]
        y = label_to_y.get(lab, 0)
        colour = MOTION_COLORS.get(lab, "#888")
        ax.barh(y, t1 - t0, left=t0, height=0.7, color=colour,
                edgecolor="#333", linewidth=0.5, alpha=0.85)

    ax.set_yticks(range(len(CFG.MOTION_LABELS)))
    ax.set_yticklabels(CFG.MOTION_LABELS, color="white", fontsize=10)
    ax.set_xlabel("Time (s)", color="white", fontsize=11)
    ax.set_title(title, color="white", fontsize=13, fontweight="bold", pad=10)
    ax.tick_params(axis="x", colors="white")
    ax.invert_yaxis()

    _add_legend(ax, MOTION_COLORS)
    fig.tight_layout()
    return fig


# ────────────────────────────────────────────────────────────────────
#  POSTURE TIMELINE
# ────────────────────────────────────────────────────────────────────

def plot_posture_timeline(
    posture_records: List[Dict],
    title: str = "Sleep Posture Timeline",
    figsize: tuple = (16, 3.5),
) -> plt.Figure:
    """Horizontal band plot of posture label over time."""
    fig, ax = _dark_axes(figsize)

    label_to_y = {l: i for i, l in enumerate(CFG.POSTURE_LABELS)}

    for r in posture_records:
        t0, t1 = r["timestamp_start"], r["timestamp_end"]
        lab = r.get("posture_label", "Unknown")
        y = label_to_y.get(lab, 4)
        colour = POSTURE_COLORS.get(lab, "#888")
        ax.barh(y, t1 - t0, left=t0, height=0.7, color=colour,
                edgecolor="#333", linewidth=0.5, alpha=0.85)

    ax.set_yticks(range(len(CFG.POSTURE_LABELS)))
    ax.set_yticklabels(CFG.POSTURE_LABELS, color="white", fontsize=10)
    ax.set_xlabel("Time (s)", color="white", fontsize=11)
    ax.set_title(title, color="white", fontsize=13, fontweight="bold", pad=10)
    ax.tick_params(axis="x", colors="white")
    ax.invert_yaxis()

    _add_legend(ax, POSTURE_COLORS)
    fig.tight_layout()
    return fig


# ────────────────────────────────────────────────────────────────────
#  COMBINED CONTEXT PLOT
# ────────────────────────────────────────────────────────────────────

def plot_combined_context(
    motion_records: List[Dict],
    posture_records: List[Dict],
    sleep_events: Optional[List[Dict]] = None,
    rr_amplitude: Optional[np.ndarray] = None,
    timestamps: Optional[np.ndarray] = None,
    title: str = "Combined Motion / Posture / Sleep Events",
    figsize: tuple = (16, 9),
) -> plt.Figure:
    """
    Three‑panel stacked plot:
        Top    – respiration amplitude with sleep event bands
        Middle – posture timeline
        Bottom – motion timeline
    """
    n_panels = 3 if rr_amplitude is not None else 2
    fig, axes = plt.subplots(n_panels, 1, figsize=figsize, sharex=True)
    fig.patch.set_facecolor("#0f0f0f")

    panel_idx = 0

    # ── Respiration + sleep events ──────────────────────────────────
    if rr_amplitude is not None and timestamps is not None:
        ax = axes[panel_idx]
        ax.set_facecolor("#1a1a1a")
        ax.plot(timestamps, np.abs(rr_amplitude), color="#22d3ee",
                linewidth=0.7, alpha=0.8)

        if sleep_events:
            for ev in sleep_events:
                if ev.get("event_type", "Normal") == "Normal":
                    continue
                t0, t1 = ev["timestamp_start"], ev["timestamp_end"]
                colour = EVENT_COLORS.get(ev["event_type"], "#888")
                ax.axvspan(t0, t1, alpha=0.25, color=colour, lw=0)

        ax.set_ylabel("RR Amplitude", color="white", fontsize=10)
        ax.set_title("Respiration & Sleep Events", color="white",
                     fontsize=12, fontweight="bold", pad=8)
        ax.tick_params(colors="white")
        _add_legend(ax, EVENT_COLORS, loc="upper left")
        panel_idx += 1

    # ── Posture ─────────────────────────────────────────────────────
    ax_p = axes[panel_idx]
    ax_p.set_facecolor("#1a1a1a")
    label_to_y = {l: i for i, l in enumerate(CFG.POSTURE_LABELS)}

    for r in posture_records:
        t0, t1 = r["timestamp_start"], r["timestamp_end"]
        lab = r.get("posture_label", "Unknown")
        y = label_to_y.get(lab, 4)
        colour = POSTURE_COLORS.get(lab, "#888")
        ax_p.barh(y, t1 - t0, left=t0, height=0.6, color=colour,
                  edgecolor="#333", linewidth=0.4, alpha=0.85)

    ax_p.set_yticks(range(len(CFG.POSTURE_LABELS)))
    ax_p.set_yticklabels(CFG.POSTURE_LABELS, color="white", fontsize=9)
    ax_p.set_title("Posture", color="white", fontsize=12,
                   fontweight="bold", pad=8)
    ax_p.tick_params(colors="white")
    ax_p.invert_yaxis()
    panel_idx += 1

    # ── Motion ──────────────────────────────────────────────────────
    ax_m = axes[panel_idx]
    ax_m.set_facecolor("#1a1a1a")
    m_label_to_y = {l: i for i, l in enumerate(CFG.MOTION_LABELS)}

    for r in motion_records:
        t0, t1 = r["timestamp_start"], r["timestamp_end"]
        lab = r["motion_type"]
        y = m_label_to_y.get(lab, 0)
        colour = MOTION_COLORS.get(lab, "#888")
        ax_m.barh(y, t1 - t0, left=t0, height=0.6, color=colour,
                  edgecolor="#333", linewidth=0.4, alpha=0.85)

    ax_m.set_yticks(range(len(CFG.MOTION_LABELS)))
    ax_m.set_yticklabels(CFG.MOTION_LABELS, color="white", fontsize=9)
    ax_m.set_xlabel("Time (s)", color="white", fontsize=11)
    ax_m.set_title("Motion", color="white", fontsize=12,
                   fontweight="bold", pad=8)
    ax_m.tick_params(colors="white")
    ax_m.invert_yaxis()

    fig.suptitle(title, color="white", fontsize=14, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    return fig


# ────────────────────────────────────────────────────────────────────
#  SESSION SUMMARY
# ────────────────────────────────────────────────────────────────────

def plot_session_summary(
    session_stats: Dict,
    title: str = "Session Summary",
    figsize: tuple = (12, 5),
) -> plt.Figure:
    """Bar chart of posture + motion epoch counts."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
    fig.patch.set_facecolor("#0f0f0f")

    # ── Posture distribution ────────────────────────────────────────
    ax1.set_facecolor("#1a1a1a")
    posture_data = session_stats.get("posture_epoch_counts", {})
    if posture_data:
        labs = list(posture_data.keys())
        vals = [posture_data[l] for l in labs]
        colours = [POSTURE_COLORS.get(l, "#888") for l in labs]
        bars = ax1.bar(labs, vals, color=colours, edgecolor="#333", linewidth=0.6)
        for bar, v in zip(bars, vals):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                     str(v), ha="center", va="bottom", color="white", fontsize=10)
    ax1.set_ylabel("Epochs", color="white", fontsize=11)
    ax1.set_title("Posture Distribution", color="white", fontsize=12, pad=8)
    ax1.tick_params(colors="white")
    plt.setp(ax1.get_xticklabels(), rotation=25, ha="right")

    # ── Motion distribution ─────────────────────────────────────────
    ax2.set_facecolor("#1a1a1a")
    motion_data = session_stats.get("motion_epoch_counts", {})
    if motion_data:
        labs = list(motion_data.keys())
        vals = [motion_data[l] for l in labs]
        colours = [MOTION_COLORS.get(l, "#888") for l in labs]
        bars = ax2.bar(labs, vals, color=colours, edgecolor="#333", linewidth=0.6)
        for bar, v in zip(bars, vals):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                     str(v), ha="center", va="bottom", color="white", fontsize=10)
    ax2.set_ylabel("Epochs", color="white", fontsize=11)
    ax2.set_title("Motion Distribution", color="white", fontsize=12, pad=8)
    ax2.tick_params(colors="white")
    plt.setp(ax2.get_xticklabels(), rotation=25, ha="right")

    fig.suptitle(title, color="white", fontsize=14, fontweight="bold", y=0.99)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    return fig


# ────────────────────────────────────────────────────────────────────
#  SAVE ALL
# ────────────────────────────────────────────────────────────────────

def save_all_plots(
    motion_records: List[Dict],
    posture_records: List[Dict],
    context_result: Dict,
    rr_amplitude: Optional[np.ndarray] = None,
    timestamps: Optional[np.ndarray] = None,
    sleep_events: Optional[List[Dict]] = None,
    output_dir: str = ".",
    prefix: str = "motion_posture",
    dpi: int = 150,
) -> Dict[str, str]:
    """Generate and save all plots as PNGs.  Returns name→path dict."""
    os.makedirs(output_dir, exist_ok=True)
    paths = {}

    fig1 = plot_motion_timeline(motion_records)
    p1 = os.path.join(output_dir, f"{prefix}_motion_timeline.png")
    fig1.savefig(p1, dpi=dpi, bbox_inches="tight", facecolor=fig1.get_facecolor())
    plt.close(fig1)
    paths["motion_timeline"] = p1

    fig2 = plot_posture_timeline(posture_records)
    p2 = os.path.join(output_dir, f"{prefix}_posture_timeline.png")
    fig2.savefig(p2, dpi=dpi, bbox_inches="tight", facecolor=fig2.get_facecolor())
    plt.close(fig2)
    paths["posture_timeline"] = p2

    fig3 = plot_combined_context(
        motion_records, posture_records, sleep_events,
        rr_amplitude, timestamps,
    )
    p3 = os.path.join(output_dir, f"{prefix}_combined_context.png")
    fig3.savefig(p3, dpi=dpi, bbox_inches="tight", facecolor=fig3.get_facecolor())
    plt.close(fig3)
    paths["combined_context"] = p3

    fig4 = plot_session_summary(context_result["session_stats"])
    p4 = os.path.join(output_dir, f"{prefix}_session_summary.png")
    fig4.savefig(p4, dpi=dpi, bbox_inches="tight", facecolor=fig4.get_facecolor())
    plt.close(fig4)
    paths["session_summary"] = p4

    return paths


# ────────────────────────────────────────────────────────────────────
#  HELPERS
# ────────────────────────────────────────────────────────────────────

def _dark_axes(figsize):
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("#0f0f0f")
    ax.set_facecolor("#1a1a1a")
    return fig, ax


def _add_legend(ax, color_map, loc="upper right"):
    patches = [mpatches.Patch(color=c, label=l, alpha=0.7)
               for l, c in color_map.items()]
    ax.legend(handles=patches, loc=loc, fontsize=8, framealpha=0.6,
              facecolor="#1a1a1a", edgecolor="#555", labelcolor="white")
