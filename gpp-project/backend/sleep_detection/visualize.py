"""
sleep_detection/visualize.py
────────────────────────────
Matplotlib‑based plots for sleep‐event detection results.

Functions
─────────
    plot_sleep_events    – Respiration amplitude timeline colour‑coded
                           by event label, with motion overlay.
    plot_summary_report  – Bar chart / pie chart of event distribution.
    save_all_plots       – Convenience wrapper that saves both plots
                           as PNG files.
"""

from __future__ import annotations
import os
from typing import Dict, Optional

import numpy as np
import matplotlib
matplotlib.use("Agg")             # headless backend for server use
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


# ── Colour palette ──────────────────────────────────────────────────
EVENT_COLORS = {
    "Normal":    "#4ade80",   # green
    "Irregular": "#facc15",   # yellow
    "Apnea":     "#ef4444",   # red
    "Motion":    "#60a5fa",   # blue
}


# ────────────────────────────────────────────────────────────────────
#  RESPIRATION TIMELINE
# ────────────────────────────────────────────────────────────────────

def plot_sleep_events(
    rr_amplitude: np.ndarray,
    timestamps: np.ndarray,
    result: Dict,
    motion_scores: Optional[np.ndarray] = None,
    title: str = "Sleep Breathing Event Detection",
    figsize: tuple = (16, 7),
) -> plt.Figure:
    """
    Create a multi‐layer timeline plot.

    Layers (from back to front):
        1. Shaded epoch bands coloured by event label.
        2. Respiration amplitude curve.
        3. Baseline & threshold horizontal lines.
        4. Motion score overlay (secondary y‐axis).

    Returns the matplotlib Figure object.
    """
    fig, ax1 = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("#0f0f0f")
    ax1.set_facecolor("#1a1a1a")

    events = result["events"]
    baseline = result["baseline_amplitude"]
    threshold = result["summary"]["amplitude_threshold"]

    # ── Epoch background bands ──────────────────────────────────────
    for ev in events:
        t0, t1 = ev["timestamp_start"], ev["timestamp_end"]
        colour = EVENT_COLORS.get(ev["event_type"], "#555")
        ax1.axvspan(t0, t1, alpha=0.18, color=colour, lw=0)

    # ── Respiration amplitude ───────────────────────────────────────
    ax1.plot(timestamps, np.abs(rr_amplitude), color="#22d3ee",
             linewidth=0.8, alpha=0.85, label="Respiration Amplitude")

    # ── Baseline & threshold ────────────────────────────────────────
    ax1.axhline(baseline, color="#4ade80", linestyle="--", linewidth=1.2,
                label=f"Baseline ({baseline:.3f})")
    ax1.axhline(threshold, color="#ef4444", linestyle="--", linewidth=1.2,
                label=f"Threshold ({threshold:.3f})")

    ax1.set_xlabel("Time (s)", color="white", fontsize=12)
    ax1.set_ylabel("Amplitude", color="white", fontsize=12)
    ax1.tick_params(colors="white")

    # ── Motion overlay ──────────────────────────────────────────────
    if motion_scores is not None:
        ax2 = ax1.twinx()
        ax2.fill_between(timestamps, 0, motion_scores,
                         color="#60a5fa", alpha=0.15, label="Motion Score")
        ax2.set_ylabel("Motion Score", color="#60a5fa", fontsize=11)
        ax2.set_ylim(0, 1.5)
        ax2.tick_params(axis="y", colors="#60a5fa")

    # ── Legend ──────────────────────────────────────────────────────
    patches = [mpatches.Patch(color=c, label=l, alpha=0.5)
               for l, c in EVENT_COLORS.items()]
    ax1.legend(handles=patches + ax1.get_legend_handles_labels()[0],
               loc="upper right", fontsize=9, framealpha=0.7,
               facecolor="#1a1a1a", edgecolor="#555", labelcolor="white")

    ax1.set_title(title, color="white", fontsize=15, fontweight="bold", pad=14)
    fig.tight_layout()
    return fig


# ────────────────────────────────────────────────────────────────────
#  SUMMARY BAR CHART
# ────────────────────────────────────────────────────────────────────

def plot_summary_report(
    result: Dict,
    title: str = "Sleep Event Summary",
    figsize: tuple = (10, 5),
) -> plt.Figure:
    """
    Bar chart of event counts + time proportion pie chart.
    """
    summary = result["summary"]
    counts = summary["event_counts"]
    times = summary["event_time_sec"]

    fig, (ax_bar, ax_pie) = plt.subplots(1, 2, figsize=figsize)
    fig.patch.set_facecolor("#0f0f0f")

    # ── Bar chart: event counts ─────────────────────────────────────
    labels = list(counts.keys())
    vals = [counts[l] for l in labels]
    colours = [EVENT_COLORS.get(l, "#888") for l in labels]

    ax_bar.set_facecolor("#1a1a1a")
    bars = ax_bar.bar(labels, vals, color=colours, edgecolor="#333", linewidth=0.8)
    ax_bar.set_ylabel("Epoch Count", color="white", fontsize=11)
    ax_bar.set_title("Events per Category", color="white", fontsize=13, pad=10)
    ax_bar.tick_params(colors="white")
    for bar, v in zip(bars, vals):
        ax_bar.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                    str(v), ha="center", va="bottom", color="white", fontsize=11)

    # ── Pie chart: time proportion ──────────────────────────────────
    pie_vals = [times[l] for l in labels]
    # avoid all-zero
    if sum(pie_vals) == 0:
        pie_vals = [1] * len(pie_vals)

    ax_pie.set_facecolor("#0f0f0f")
    wedges, texts, autotexts = ax_pie.pie(
        pie_vals, labels=labels, colors=colours, autopct="%1.0f%%",
        startangle=140, textprops={"color": "white", "fontsize": 10},
    )
    for at in autotexts:
        at.set_fontsize(9)
    ax_pie.set_title("Time Distribution", color="white", fontsize=13, pad=10)

    # ── Severity annotation ─────────────────────────────────────────
    sev = summary.get("severity", "N/A")
    ahi = summary.get("apnea_events_per_hour", 0)
    fig.text(0.5, 0.01,
             f"AHI (Apnea–Hypopnea Index): {ahi:.1f} events/hr  •  Severity: {sev}",
             ha="center", color="#facc15", fontsize=12, fontweight="bold")

    fig.tight_layout(rect=[0, 0.05, 1, 1])
    return fig


# ────────────────────────────────────────────────────────────────────
#  CONVENIENCE SAVER
# ────────────────────────────────────────────────────────────────────

def save_all_plots(
    rr_amplitude: np.ndarray,
    timestamps: np.ndarray,
    result: Dict,
    motion_scores: Optional[np.ndarray] = None,
    output_dir: str = ".",
    prefix: str = "sleep",
    dpi: int = 150,
) -> Dict[str, str]:
    """
    Generate and save both plots as PNG files.

    Returns dict mapping plot name → file path.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths = {}

    fig1 = plot_sleep_events(rr_amplitude, timestamps, result, motion_scores)
    p1 = os.path.join(output_dir, f"{prefix}_events_timeline.png")
    fig1.savefig(p1, dpi=dpi, bbox_inches="tight", facecolor=fig1.get_facecolor())
    plt.close(fig1)
    paths["timeline"] = p1

    fig2 = plot_summary_report(result)
    p2 = os.path.join(output_dir, f"{prefix}_summary_report.png")
    fig2.savefig(p2, dpi=dpi, bbox_inches="tight", facecolor=fig2.get_facecolor())
    plt.close(fig2)
    paths["summary"] = p2

    return paths
