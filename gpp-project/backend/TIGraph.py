#!/usr/bin/env python3
"""
ti_vitalsign_repl.py

Replacement utility that:
 - Loads new rows appended to your master CSV (vital_signs_data_new.csv)
 - Computes a combined waveform from 4 parameters:
      HeartWaveform, BreathWaveform, HeartRate_FFT, BreathRate_FFT
 - Displays the combined waveform and component traces in an interactive matplotlib window
 - Prints the ASCII session statistics (average HR/RR/range) and emits a JSON block
   between STATS_BEGIN and STATS_END so a Flask parent process can capture it.
 - Usage:
      python ti_vitalsign_repl.py <user_email> <config_type> [--csv path] [--duration secs]
"""

import sys
import os
import csv
import time
import json
import argparse
import statistics
from datetime import datetime
import math

# plotting
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.widgets import Button

# -----------------------------
# Defaults / paths
# -----------------------------
DEFAULT_BASE = os.path.join(os.path.dirname(__file__), "..") if "__file__" in globals() else os.getcwd()
DEFAULT_BACKEND = os.path.join(DEFAULT_BASE, "backend")
DEFAULT_CSV = os.path.join(DEFAULT_BACKEND, "vital_signs_data_new.csv")

# -----------------------------
# Argument parsing
# -----------------------------
parser = argparse.ArgumentParser(description="TI vitalsigns replacement display + combined waveform")
parser.add_argument("user_email", nargs="?", default="nikhil2310204@ssn.edu.in")
parser.add_argument("config", nargs="?", type=int, default=0)
parser.add_argument("--csv", "-c", default=DEFAULT_CSV, help="Path to master CSV")
parser.add_argument("--duration", "-d", type=float, default=30.0, help="Plot duration in seconds (for simulated realtime)")
parser.add_argument("--no-plot", action="store_true", help="Dont show GUI (just compute stats and print JSON)")
args = parser.parse_args()

CSV_PATH = os.path.abspath(args.csv)
USER_EMAIL = args.user_email
CONFIG_TYPE = args.config
DURATION = args.duration

# -----------------------------
# CSV format expected (columns)
# Timestamp, User, Configuration, SessionTime, HeartRate_BPM, RespirationRate_BPM, Range_m,
# HeartWaveform, BreathWaveform, HeartRate_FFT, BreathRate_FFT
# -----------------------------

def safe_float(x, default=0.0):
    try:
        return float(x)
    except:
        return default

def load_rows_for_user(csv_path, user_email, config_type=None):
    """Return all rows (list of dicts) matching the given user (and optional config)."""
    rows = []
    if not os.path.exists(csv_path):
        return rows
    with open(csv_path, "r", newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f, delimiter=",", quoting=csv.QUOTE_MINIMAL)
        header = next(reader, None)
        # quit if header doesn't look right; but support TSV-like or tab-separated saved files by splitting
        # Find column indices by names if header present
        if header:
            # normalize header names
            norm = [h.strip().lower() for h in header]
            # attempt to map common names
            idx_map = {}
            for i, h in enumerate(norm):
                if "timestamp" in h: idx_map["ts"] = i
                if h.startswith("user"): idx_map["user"] = i
                if "configuration" in h or "config" in h: idx_map["config"] = i
                if "session" in h and "time" in h: idx_map["session"] = i
                if "heartrate" in h and "bpm" in h: idx_map["hr"] = i
                if "respirationrate" in h or "breathrate" in h or "rr" in h: idx_map["rr"] = i
                if "range" in h and "m" in h: idx_map["range_m"] = i
                if "heartwaveform" in h: idx_map["heart_waveform"] = i
                if "breathwaveform" in h or "breath_waveform" in h: idx_map["breath_waveform"] = i
                if "heartrate_fft" in h or "heart_rate_fft" in h: idx_map["hr_fft"] = i
                if "breathrate_fft" in h or "breath_rate_fft" in h: idx_map["rr_fft"] = i
            # fallback positions if missing
            # We will try tolerant parsing per-row below using best-effort indices or by column count
        else:
            idx_map = {}

        # iterate rows
        for row in reader:
            if not row: continue
            # some files use tabs; try to join then split by tabs if single-column
            if len(row) == 1 and "\t" in row[0]:
                row = row[0].split("\t")
            # get user col
            user_col = None
            config_col = None
            if "user" in idx_map:
                user_col = idx_map["user"]
            else:
                # fallback: first column often email
                user_col = 1 if len(row) > 1 else 0
            if "config" in idx_map:
                config_col = idx_map["config"]
            else:
                config_col = 2 if len(row) > 2 else None
            try:
                row_user = row[user_col].strip()
            except:
                row_user = ""
            # match user (case-insensitive)
            if row_user.lower() != user_email.lower():
                continue
            # match config if provided
            if config_type is not None and config_col is not None:
                try:
                    if int(row[config_col]) != int(config_type):
                        continue
                except:
                    pass
            # parse numeric fields with best-effort indices
            def get_by_name(name, fallback_index):
                if name in idx_map:
                    i = idx_map[name]
                    return row[i] if i < len(row) else ""
                else:
                    return row[fallback_index] if fallback_index < len(row) else ""
            # estimate mappings (common CSV you provided: TS, user, config, SessionTime, HR, RR, Range, HeartWave, BreathWave, HR_FFT, BR_FFT)
            # So fallback indices:
            ts = get_by_name("ts", 0)
            session_time = get_by_name("session", 3)
            hr = safe_float(get_by_name("hr", 4))
            rr = safe_float(get_by_name("rr", 5))
            rng = safe_float(get_by_name("range_m", 6))
            heart_wf = safe_float(get_by_name("heart_waveform", 7))
            breath_wf = safe_float(get_by_name("breath_waveform", 8))
            hr_fft = safe_float(get_by_name("hr_fft", 9))
            rr_fft = safe_float(get_by_name("rr_fft", 10))

            rows.append({
                "timestamp": ts,
                "session_time": session_time,
                "hr": hr,
                "rr": rr,
                "range_m": rng,
                "heart_wf": heart_wf,
                "breath_wf": breath_wf,
                "hr_fft": hr_fft,
                "rr_fft": rr_fft
            })
    return rows

def normalize_series(arr):
    """Min-max normalize to [-1,1] if possible, else return zeros"""
    if not arr:
        return [0.0]*0
    amin = min(arr)
    amax = max(arr)
    if math.isclose(amax, amin):
        # constant series -> zeros
        return [0.0 for _ in arr]
    out = [((v - amin) / (amax - amin)) * 2.0 - 1.0 for v in arr]
    return out

def compute_combined_wave(heart_wf, breath_wf, hr_fft, rr_fft, weights=(0.4,0.4,0.1,0.1)):
    """Normalize each component to [-1,1] then weighted sum"""
    nh = normalize_series(heart_wf)
    nb = normalize_series(breath_wf)
    nhf = normalize_series(hr_fft)
    nrf = normalize_series(rr_fft)
    combined = []
    for i in range(len(nh)):
        h = nh[i]
        b = nb[i] if i < len(nb) else 0.0
        hf = nhf[i] if i < len(nhf) else 0.0
        rf = nrf[i] if i < len(nrf) else 0.0
        val = weights[0]*h + weights[1]*b + weights[2]*hf + weights[3]*rf
        combined.append(val)
    # optionally re-normalize combined to [-1,1]
    combined = normalize_series(combined)
    return combined

def produce_ascii_stats(hr_values, rr_values, range_values, packet_count, data_saved, data_skipped):
    duration = DURATION
    total = data_saved + data_skipped
    lines = []
    lines.append("\n" + "-"*60)
    lines.append("USER: {}".format(USER_EMAIL))
    lines.append("CONFIGURATION: {} ({})".format("front" if CONFIG_TYPE==0 else "back", CONFIG_TYPE))
    lines.append("\nSESSION SUMMARY")
    lines.append("-"*40)
    lines.append("Duration (sec)      : {:.1f}".format(duration))
    lines.append("Packets Received    : {}".format(packet_count))
    lines.append("Frames Saved        : {}".format(data_saved))
    lines.append("Frames Skipped      : {}".format(data_skipped))
    if total>0:
        lines.append("Save Ratio (%)      : {:.1f}%".format(data_saved/total*100.0))
    else:
        lines.append("Save Ratio (%)      : N/A")
    if hr_values:
        avg_hr = sum(hr_values)/len(hr_values)
        avg_rr = sum(rr_values)/len(rr_values)
        avg_range = sum(range_values)/len(range_values)
        lines.append("\nVITAL SIGNS SUMMARY")
        lines.append("-"*40)
        lines.append("Average Heart Rate  : {:.1f} bpm".format(avg_hr))
        lines.append("Average Resp Rate   : {:.1f} bpm".format(avg_rr))
        lines.append("Average Distance    : {:.3f} m ({:.0f} cm)".format(avg_range, avg_range*100.0))
        if len(range_values) > 1:
            range_std = statistics.stdev(range_values)
            lines.append("Distance Std Dev    : {:.3f} m ({:.0f} cm)".format(range_std, range_std*100.0))
    else:
        lines.append("\nNo valid HR/RR frames were saved.")
    return "\n".join(lines)

# -----------------------------
# Main: load CSV, filter by user/config, compute combined waveform, show plot, print stats JSON
# -----------------------------
rows = load_rows_for_user(CSV_PATH, USER_EMAIL, CONFIG_TYPE)

if not rows:
    # still print an explicit message for Flask capture
    msg = "No rows found for user {} in file {}".format(USER_EMAIL, CSV_PATH)
    print(json.dumps({"success": False, "error": msg}))
    sys.exit(0)

# extract arrays in chronological order (CSV likely already chronological)
hr_vals = [r["hr"] for r in rows]
rr_vals = [r["rr"] for r in rows]
range_vals = [r["range_m"] for r in rows]
heart_wf = [r["heart_wf"] for r in rows]
breath_wf = [r["breath_wf"] for r in rows]
hr_fft = [r["hr_fft"] for r in rows]
rr_fft = [r["rr_fft"] for r in rows]

packet_count = len(rows)
data_saved = len(rows)   # we assume all loaded rows are saved frames
data_skipped = 0

# compute combined waveform
combined = compute_combined_wave(heart_wf, breath_wf, hr_fft, rr_fft, weights=(0.45,0.35,0.1,0.1))

# ascii stats
ascii_stats = produce_ascii_stats(hr_vals, rr_vals, range_vals, packet_count, data_saved, data_skipped)

# prepare JSON stats for Flask capture
json_stats = {
    "user": USER_EMAIL,
    "configuration": CONFIG_TYPE,
    "packets_received": packet_count,
    "frames_saved": data_saved,
    "frames_skipped": data_skipped,
    "avg_hr": round(sum(hr_vals)/len(hr_vals), 2) if hr_vals else None,
    "avg_rr": round(sum(rr_vals)/len(rr_vals), 2) if rr_vals else None,
    "avg_range_m": round(sum(range_vals)/len(range_vals), 4) if range_vals else None
}

# Print ASCII stats (for terminal) and JSON block so Flask can parse it
print(ascii_stats)
print("\nCSV Loaded From: {}".format(CSV_PATH))
# emit JSON wrapped so parent Flask can parse between STATS_BEGIN / STATS_END
print("STATS_BEGIN")
print(json.dumps({"stats_text": ascii_stats, "stats": json_stats}))
print("STATS_END")

# Save a CSV of the combined waveform next to the master CSV (timestamped)
try:
    out_csv = os.path.splitext(CSV_PATH)[0] + "_combined_{}.csv".format(datetime.now().strftime("%Y%m%d_%H%M%S"))
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["index", "timestamp", "heart_wf", "breath_wf", "hr_fft", "rr_fft", "combined"])
        for i, r in enumerate(rows):
            w.writerow([i, r["timestamp"], r["heart_wf"], r["breath_wf"], r["hr_fft"], r["rr_fft"], combined[i] if i < len(combined) else ""])
    print("Combined waveform CSV saved to:", out_csv)
except Exception as e:
    print("Warning: could not save combined CSV:", e)

# optionally show GUI
if args.no_plot:
    sys.exit(0)

# Plot interactive GUI: show components and combined waveform
plt.style.use('dark_background')
fig, axs = plt.subplots(4, 1, figsize=(10, 8), sharex=True)
ax_h, ax_b, ax_hf, ax_comb = axs

x = list(range(len(combined)))
ax_h.plot(x, heart_wf, label="HeartWaveform", linewidth=1)
ax_h.set_ylabel("HeartWF")
ax_b.plot(x, breath_wf, label="BreathWaveform", linewidth=1)
ax_b.set_ylabel("BreathWF")
ax_hf.plot(x, hr_fft, label="HR_FFT", linewidth=1)
ax_hf.set_ylabel("HR_FFT")
ax_comb.plot(x, combined, label="COMBINED", linewidth=2)
ax_comb.set_ylabel("Combined")
ax_comb.set_xlabel("Sample index")

for a in axs:
    a.grid(alpha=0.2)
    a.legend(loc="upper right", fontsize=8)

fig.suptitle("Combined Vital Signs Waveform — user: {} config: {}".format(USER_EMAIL, CONFIG_TYPE))

# Add a small button to save the combined plot as PNG
axsave = plt.axes([0.85, 0.92, 0.12, 0.05])
btn = Button(axsave, 'Save PNG')

def on_save(event):
    out_png = os.path.splitext(CSV_PATH)[0] + "_combined_{}.png".format(datetime.now().strftime("%Y%m%d_%H%M%S"))
    fig.savefig(out_png, dpi=180, bbox_inches='tight')
    print("Saved combined figure to:", out_png)

btn.on_clicked(on_save)

plt.tight_layout(rect=[0,0,1,0.96])
plt.show(block=True)
