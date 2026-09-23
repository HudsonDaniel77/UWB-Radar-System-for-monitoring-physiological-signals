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
# PATHS - Resolve session file dynamically
# ==========================================================
DATA_ANALYSIS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(DATA_ANALYSIS_DIR, "..", "backend"))
CLEAN_FILE = os.path.join(DATA_ANALYSIS_DIR, "cleaned_vital_signs_new_tryingsomething.csv")

os.makedirs(DATA_ANALYSIS_DIR, exist_ok=True)

# 1. Check if specific session file passed via command line
if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
    RAW_FILE = os.path.abspath(sys.argv[1])
    print(f"✔ Using specified session file: {os.path.basename(RAW_FILE)}")
else:
    session_files = glob.glob(os.path.join(BACKEND_DIR, "vital_signs_session_*.csv"))
    if not session_files:
        raise FileNotFoundError("❌ No session vital signs files found in backend directory")
    RAW_FILE = max(session_files, key=os.path.getmtime)
    print(f"✔ Using latest session file: {os.path.basename(RAW_FILE)}")

# Canonical 14-column schema
CANONICAL_COLS = [
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
        except Exception:
            pass
    return pd.to_datetime(s, errors="coerce")

# ==========================================================
# LOAD RAW DATA
# ==========================================================
if not os.path.exists(RAW_FILE):
    raise FileNotFoundError(f"❌ Raw vital signs file not found: {RAW_FILE}")

raw = pd.read_csv(RAW_FILE, engine="python")

if "Configuration" in raw.columns and "ConfigurationFile" not in raw.columns:
    raw = raw.rename(columns={"Configuration": "ConfigurationFile"})

if "ConfigurationFile" not in raw.columns:
    raw["ConfigurationFile"] = 0

if "User" not in raw.columns:
    raw["User"] = "default_user"

raw["Timestamp"] = raw["Timestamp"].apply(parse_ts)
raw = raw.dropna(subset=["Timestamp", "SessionTime"])
raw = raw.sort_values(["Timestamp", "SessionTime"]).reset_index(drop=True)

# Numeric conversion
for c in ["SessionTime", "HeartRate_BPM", "RespirationRate_BPM", "Range_m", "ConfigurationFile"]:
    if c in raw.columns:
        raw[c] = pd.to_numeric(raw[c], errors="coerce")

# Valid physiological HR is between 40 and 180 bpm
clean = raw[raw["HeartRate_BPM"].between(40, 180)].copy()

if clean.empty:
    print("⚠ No valid HR rows found in this session.")
    if not os.path.exists(CLEAN_FILE) or os.path.getsize(CLEAN_FILE) == 0:
        pd.DataFrame(columns=CANONICAL_COLS).to_csv(CLEAN_FILE, index=False)
    sys.exit(0)

# ==========================================================
# HARMONIC DE-ALIASING & WARM-UP CORRECTION
# ==========================================================
# In mmWave radar, 2nd harmonics (~120-150 BPM) frequently appear
# when true resting heart rate is ~60-75 BPM.
# We use FFT on the physical HeartWaveform as ground truth.
fundamental_wf_hr = None
if "HeartWaveform" in clean.columns and clean["HeartWaveform"].notna().sum() > 30:
    try:
        hw = clean["HeartWaveform"].dropna().values
        fps = 20.0
        hw_detrend = hw - np.mean(hw)
        fft_vals = np.abs(np.fft.rfft(hw_detrend))
        freqs = np.fft.rfftfreq(len(hw_detrend), d=1.0/fps)
        mask = (freqs >= 0.8) & (freqs <= 2.0)  # 48 to 120 BPM
        if np.any(mask):
            peak_freq = freqs[mask][np.argmax(fft_vals[mask])]
            fundamental_wf_hr = peak_freq * 60.0
    except Exception:
        fundamental_wf_hr = None

hr_series = clean["HeartRate_BPM"].copy()

# De-alias based on physical waveform frequency
if fundamental_wf_hr and 50 <= fundamental_wf_hr <= 95:
    double_mask = (hr_series > 105) & ((hr_series / 2.0).between(fundamental_wf_hr - 20, fundamental_wf_hr + 20))
    hr_series.loc[double_mask] = hr_series.loc[double_mask] / 2.0

# De-alias based on cluster distribution in session
low_cluster = hr_series[(hr_series >= 50) & (hr_series <= 95)]
high_cluster = hr_series[(hr_series >= 115) & (hr_series <= 150)]

if len(low_cluster) > 0 and len(high_cluster) > 0:
    double_mask = (hr_series >= 115) & (hr_series <= 150)
    hr_series.loc[double_mask] = hr_series.loc[double_mask] / 2.0
elif len(high_cluster) == len(hr_series) and (fundamental_wf_hr is None or fundamental_wf_hr < 95):
    # Entire session locked on 2nd harmonic (e.g. 133.33 BPM)
    hr_series = hr_series / 2.0

clean["HeartRate_BPM"] = hr_series

# ==========================================================
# RESPIRATION RATE DE-ALIASING & SMOOTHING
# ==========================================================
fundamental_wf_rr = None
if "BreathWaveform" in clean.columns and clean["BreathWaveform"].notna().sum() > 30:
    try:
        bw = clean["BreathWaveform"].dropna().values
        fps = 20.0
        bw_detrend = bw - np.mean(bw)
        b_fft = np.abs(np.fft.rfft(bw_detrend))
        b_freqs = np.fft.rfftfreq(len(bw_detrend), d=1.0/fps)
        b_mask = (b_freqs >= 0.1) & (b_freqs <= 0.5)  # 6 to 30 BPM
        if np.any(b_mask):
            fundamental_wf_rr = b_freqs[b_mask][np.argmax(b_fft[b_mask])] * 60.0
    except Exception:
        fundamental_wf_rr = None

clean["RespirationRate_BPM"] = clean["RespirationRate_BPM"].replace(0, np.nan)
if clean["RespirationRate_BPM"].notna().any():
    clean["RespirationRate_BPM"] = clean["RespirationRate_BPM"].ffill().bfill()
elif fundamental_wf_rr and 8 <= fundamental_wf_rr <= 30:
    clean["RespirationRate_BPM"] = fundamental_wf_rr
else:
    clean["RespirationRate_BPM"] = 14.0

if fundamental_wf_rr and 8 <= fundamental_wf_rr <= 30:
    clean.loc[clean["RespirationRate_BPM"] < 8, "RespirationRate_BPM"] = fundamental_wf_rr

clean["RespirationRate_BPM"] = clean["RespirationRate_BPM"].clip(lower=6.0, upper=35.0)

# ==========================================================
# RANGE CONTINUITY
# ==========================================================
if "Range_m" not in clean.columns:
    clean["Range_m"] = 0.5
else:
    clean["Range_m"] = clean["Range_m"].ffill().bfill()
    clean.loc[(clean["Range_m"] < 0.1) | (clean["Range_m"] > 2.5), "Range_m"] = np.nan
    clean["Range_m"] = clean["Range_m"].ffill().bfill().fillna(0.5)

# ==========================================================
# SMOOTHING (LOWPASS / ROLLING)
# ==========================================================
def lowpass(x, cutoff=0.35, fs=20):
    x = x.ffill().bfill()
    if len(x) < 15:
        return x.rolling(3, center=True, min_periods=1).mean()
    try:
        b, a = butter(4, cutoff / (fs / 2), btype="low")
        return filtfilt(b, a, x)
    except Exception:
        return x.rolling(3, center=True, min_periods=1).mean()

win = min(7, max(3, len(clean)))

clean["Heart_clean"] = lowpass(
    clean["HeartRate_BPM"].rolling(win, center=True, min_periods=1).median()
)
clean["Resp_clean"] = lowpass(
    clean["RespirationRate_BPM"].rolling(win, center=True, min_periods=1).median()
)
clean["Range_clean"] = lowpass(
    clean["Range_m"].rolling(win, center=True, min_periods=1).median()
)

# Fill optional waveform columns if missing
for col in ["HeartWaveform", "BreathWaveform", "HeartRate_FFT", "BreathRate_FFT"]:
    if col not in clean.columns:
        clean[col] = 0.0

# ==========================================================
# FINAL CLEANED OUTPUT
# ==========================================================
out = clean[CANONICAL_COLS].copy()

# Ensure file exists with canonical header
need_header = not os.path.exists(CLEAN_FILE) or os.path.getsize(CLEAN_FILE) == 0

if not need_header:
    try:
        existing = pd.read_csv(CLEAN_FILE, nrows=1)
        if list(existing.columns) != CANONICAL_COLS:
            need_header = True
    except Exception:
        need_header = True

if need_header:
    out.to_csv(CLEAN_FILE, mode="w", index=False, header=True)
else:
    try:
        existing_ts = set(pd.read_csv(CLEAN_FILE, usecols=["Timestamp"])["Timestamp"].astype(str))
        out_new = out[~out["Timestamp"].astype(str).isin(existing_ts)]
        if not out_new.empty:
            out_new.to_csv(CLEAN_FILE, mode="a", index=False, header=False)
            print(f"✔ Appended {len(out_new)} new cleaned rows to {CLEAN_FILE}")
        else:
            print(f"✔ Cleaned rows for this session already present in {CLEAN_FILE}")
    except Exception:
        out.to_csv(CLEAN_FILE, mode="a", index=False, header=False)

print(f"✔ Cleaned rows processed: {len(out)}")
print(f"✔ Heart Rate mean after de-aliasing: {clean['Heart_clean'].mean():.2f} BPM")
print(f"✔ Respiration Rate mean: {clean['Resp_clean'].mean():.2f} BPM")
print(f"✔ Target: {CLEAN_FILE}")
