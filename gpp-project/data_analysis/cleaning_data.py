import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
from scipy.signal import butter, filtfilt
import os, re
from pathlib import Path
import glob

# ==========================================================
# PATHS - Find most recent session file
# ==========================================================
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

# Find the most recent session CSV file
session_files = glob.glob(os.path.join(BACKEND_DIR, "vital_signs_session_*.csv"))
if not session_files:
    raise FileNotFoundError("❌ No session vital signs files found in backend directory")

RAW_FILE = max(session_files, key=os.path.getmtime)  # Most recent file
CLEAN_FILE = os.path.join(os.path.dirname(__file__), "cleaned_vital_signs_new_tryingsomething.csv")

os.makedirs(os.path.dirname(CLEAN_FILE), exist_ok=True)

# ==========================================================
# TIMESTAMP PARSING
# ==========================================================
def parse_ts(s):
    if pd.isna(s):
        return pd.NaT
    s = str(s).strip()
    fmts = [
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S.%f",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M"
    ]
    for f in fmts:
        try:
            return pd.to_datetime(s, format=f)
        except:
            pass
    return pd.to_datetime(s, errors="coerce")

# ==========================================================
# LOAD RAW DATA
# ==========================================================
if not os.path.exists(RAW_FILE):
    raise FileNotFoundError("❌ Raw vital signs file not found")

raw = pd.read_csv(RAW_FILE, engine="python")

# Required columns only
COLS = [
    "Timestamp",
    "User",
    "Configuration",
    "SessionTime",
    "HeartRate_BPM",
    "RespirationRate_BPM",
    "Range_m",
    "HeartWaveform",
    "BreathWaveform",
    "HeartRate_FFT",
    "BreathRate_FFT"
]
raw = raw[[c for c in COLS if c in raw.columns]]

raw = raw.rename(columns={"Configuration": "ConfigurationFile"})
raw["Timestamp"] = raw["Timestamp"].apply(parse_ts)

raw = raw.dropna(subset=["Timestamp", "SessionTime"])
raw = raw.sort_values(["Timestamp", "SessionTime"]).reset_index(drop=True)

# ==========================================================
# LOAD LAST CLEANED POINT (ROBUST INCREMENTAL MODE)
# ==========================================================
if os.path.exists(CLEAN_FILE) and os.path.getsize(CLEAN_FILE) > 0:
    try:
        prev = pd.read_csv(CLEAN_FILE)
        prev["Timestamp"] = prev["Timestamp"].apply(parse_ts)

        last_ts = prev["Timestamp"].max()
        last_st = prev.loc[
            prev["Timestamp"] == last_ts, "SessionTime"
        ].max()

        raw_new = raw[
            (raw["Timestamp"] > last_ts) |
            ((raw["Timestamp"] == last_ts) & (raw["SessionTime"] > last_st))
        ].copy()

    except Exception as e:
        print("⚠ Previous clean file unreadable, starting fresh:", e)
        raw_new = raw.copy()
else:
    raw_new = raw.copy()

# ==========================================================
# NUMERIC CONVERSION
# ==========================================================
for c in ["SessionTime", "HeartRate_BPM", "RespirationRate_BPM", "Range_m"]:
    raw_new[c] = pd.to_numeric(raw_new[c], errors="coerce")

# ==========================================================
# HR / RR FILTERING ONLY (DO NOT TOUCH RANGE YET)
# ==========================================================
clean = raw_new[
    raw_new["HeartRate_BPM"].between(40, 180) &
    raw_new["RespirationRate_BPM"].between(5, 40)
].copy()

if clean.empty:
    print("⚠ No valid rows after HR/RR filtering (respiration rate likely 0)")
    # Create empty but valid cleaned output file
    empty_df = pd.DataFrame(columns=[
        "Timestamp", "User", "Configuration", "SessionTime",
        "Heart_clean", "Resp_clean", "Range_clean"
    ])
    empty_df.to_csv(CLEAN_FILE, index=False)
    print("✔ Empty cleaned file created")
    exit(0)  # Exit successfully, not with error

# ==========================================================
# RANGE CONTINUITY FIX (THIS IS THE KEY)
# ==========================================================
# Make range continuous BEFORE filtering it
clean["Range_m"] = clean["Range_m"].ffill()

# If range is still NaN (early frames), fill with first valid later value
clean["Range_m"] = clean["Range_m"].bfill()

# ==========================================================
# OPTIONAL SAFETY CLAMP (NO DROPPING)
# ==========================================================
clean.loc[
    (clean["Range_m"] < 0.1) | (clean["Range_m"] > 2.5),
    "Range_m"
] = np.nan

clean["Range_m"] = clean["Range_m"].ffill().bfill()

# ==========================================================
# SMOOTHING (FRAME SAFE)
# ==========================================================
def lowpass(x, cutoff=0.35, fs=20):
    x = x.ffill().bfill()
    if len(x) < 15:
        return x.rolling(3, center=True, min_periods=1).mean()
    b, a = butter(4, cutoff / (fs / 2), btype="low")
    return filtfilt(b, a, x)

win = min(7, len(clean))

clean["Heart_clean"] = lowpass(
    clean["HeartRate_BPM"].rolling(win, center=True, min_periods=1).median()
)
clean["Resp_clean"] = lowpass(
    clean["RespirationRate_BPM"].rolling(win, center=True, min_periods=1).median()
)
clean["Range_clean"] = lowpass(
    clean["Range_m"].rolling(win, center=True, min_periods=1).median()
)

# ==========================================================
# FINAL CLEANED OUTPUT
# ==========================================================
out = clean[
    [
        "Timestamp",
        "User",
        "SessionTime",
        "HeartRate_BPM",
        "RespirationRate_BPM",
        "Range_m",
        "HeartWaveform",
        "BreathWaveform",
        "HeartRate_FFT",
        "BreathRate_FFT",
        "ConfigurationFile",
        "Heart_clean",
        "Resp_clean",
        "Range_clean"
    ]
]

write_header = not os.path.exists(CLEAN_FILE) or os.path.getsize(CLEAN_FILE) == 0
out.to_csv(CLEAN_FILE, mode="a", index=False, header=write_header)

print(f"✔ Cleaned rows appended: {len(out)}")
print(f"✔ Saved to: {CLEAN_FILE}")
