import pandas as pd
import numpy as np
from scipy.signal import butter, filtfilt
import os, json
import re

# Paths
RAW_FILE = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project-behindwall\backend\vital_signs_data_new.csv"
CLEAN_FILE = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project-behindwall\data_analysis\cleaned_vital_signs_new.csv"
FINAL_STATS_FILE = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project-behindwall\data_analysis\final_run_stats_new.csv"
OFFSET_FILE = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project-behindwall\data_analysis\calibration_offsets.json"

# Ensure directories exist
os.makedirs(os.path.dirname(FINAL_STATS_FILE), exist_ok=True)

print("🔄 Force reprocessing all data...")

# Load raw data
raw_df = pd.read_csv(RAW_FILE)
print(f"📊 Loaded {len(raw_df)} raw rows")

# Parse timestamps
def clean_ts_string(s: str) -> str:
    if pd.isna(s):
        return ""
    s = str(s)
    s = s.replace("–", "-").replace("—", "-")
    s = s.replace("/", "-")
    s = re.sub(r'\b(?:GMT|UTC)\b[^\s]*', '', s, flags=re.IGNORECASE)
    s = re.sub(r'[\+\-]\d{2}:?\d{2}$', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def parse_timestamps(series: pd.Series) -> pd.Series:
    s = series.astype(str).apply(clean_ts_string)
    formats = [
        "%d-%m-%Y %H:%M:%S.%f",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d-%m-%y %H:%M:%S",
        "%d-%m-%y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]
    
    parsed = pd.Series(pd.NaT, index=s.index)
    for fmt in formats:
        mask = parsed.isna()
        if not mask.any():
            break
        try:
            parsed_vals = pd.to_datetime(s[mask], format=fmt, dayfirst=True, errors="coerce")
            parsed.loc[mask] = parsed_vals
        except Exception:
            pass
    
    still_missing = parsed.isna()
    if still_missing.any():
        try:
            fallback = pd.to_datetime(s[still_missing], dayfirst=True, errors="coerce", infer_datetime_format=True)
            parsed.loc[still_missing] = fallback
        except Exception:
            pass
    
    return parsed

# Parse timestamps
raw_df["Timestamp"] = parse_timestamps(raw_df["Timestamp"])
raw_df = raw_df.dropna(subset=["Timestamp"])
raw_df = raw_df.sort_values(by=["Timestamp", "SessionTime"]).reset_index(drop=True)

print(f"✅ Parsed timestamps, {len(raw_df)} valid rows")

# Rename config column if needed
if "Configuration" in raw_df.columns:
    raw_df = raw_df.rename(columns={"Configuration": "ConfigurationFile"})

# Clean numeric columns
numeric_cols = ["SessionTime","HeartRate_BPM","RespirationRate_BPM","Range_m"]
for c in numeric_cols:
    if c in raw_df.columns:
        raw_df[c] = pd.to_numeric(raw_df[c], errors="coerce")

# Remove impossible values
clean = raw_df[
    raw_df["HeartRate_BPM"].between(40, 180) &
    raw_df["RespirationRate_BPM"].between(5, 40) &
    raw_df["Range_m"].between(0.1, 2.0)
].reset_index(drop=True)

print(f"🧹 After filtering: {len(clean)} rows")

# Detect stuck HR
if not clean.empty:
    mode_hr = clean["HeartRate_BPM"].mode().iloc[0]
    if clean["HeartRate_BPM"].value_counts().max() > 0.6 * len(clean) and mode_hr > 110:
        clean = clean[clean["HeartRate_BPM"] != mode_hr]
        print(f"🚫 Removed stuck HR values: {len(clean)} rows remaining")

if clean.empty:
    print("⚠ All rows invalid after filtering")
    exit()

# Apply filters
def lowpass(arr, cutoff=0.3, fs=10):
    arr = arr.ffill().bfill()
    if len(arr) < 12:
        return arr.rolling(3, min_periods=1, center=True).mean()
    b, a = butter(4, cutoff/(fs/2), btype='low')
    return filtfilt(b, a, arr)

win = min(5, len(clean))
clean["Heart_med"] = clean["HeartRate_BPM"].rolling(win, center=True, min_periods=1).median()
clean["Resp_med"]  = clean["RespirationRate_BPM"].rolling(win, center=True, min_periods=1).median()
clean["Range_med"] = clean["Range_m"].rolling(win, center=True, min_periods=1).median()

clean["Heart_clean"] = lowpass(clean["Heart_med"])
clean["Resp_clean"]  = lowpass(clean["Resp_med"])
clean["Range_clean"] = lowpass(clean["Range_med"])

clean = clean.ffill().bfill()

# Select final columns
final_clean = clean[
    [
        "Timestamp","User","SessionTime",
        "HeartRate_BPM","RespirationRate_BPM","Range_m",
        "HeartWaveform","BreathWaveform","HeartRate_FFT","BreathRate_FFT",
        "ConfigurationFile",
        "Heart_clean","Resp_clean","Range_clean"
    ]
]

print(f"✅ Cleaned data: {len(final_clean)} rows")

# Save cleaned data
final_clean.to_csv(CLEAN_FILE, index=False)
print(f"💾 Saved cleaned data to: {CLEAN_FILE}")

# Run detection
df = final_clean.copy()
df["SessionTime"] = pd.to_numeric(df["SessionTime"], errors="coerce").fillna(0).astype(float)

# Load offsets
if os.path.exists(OFFSET_FILE):
    offsets = json.load(open(OFFSET_FILE))
else:
    offsets = {"offset_0": 10.5, "offset_1": 10.5}

# Run detection
df["Run"] = 0
run_no = 1
df.loc[0, "Run"] = run_no

for i in range(1, len(df)):
    if df.loc[i, "SessionTime"] < df.loc[i - 1, "SessionTime"]:
        run_no += 1
    df.loc[i, "Run"] = run_no

# Only valid runs (min 5 samples)
valid_runs = [(rn, g) for rn, g in df.groupby("Run") if len(g) >= 5]
if not valid_runs:
    print("⚠ No valid runs detected")
    exit()

print(f"✔ Valid runs detected: {[rn for rn, _ in valid_runs]}")

# Compute final stats
rows = []

def classify_hr(hr):
    if hr < 65: return "Low"
    elif hr <= 90: return "Normal"
    elif hr <= 115: return "Elevated"
    else: return "High"

def classify_rr(rr):
    if rr < 12: return "Low"
    elif rr <= 20: return "Normal"
    elif rr <= 25: return "Fast"
    else: return "Very High"

def classify_stress(sd):
    if sd < 0.05: return "Relaxed"
    elif sd < 0.15: return "Mild Stress"
    elif sd < 0.25: return "High Stress"
    else: return "Very High Stress"

for rn, g in valid_runs:
    ts = g["Timestamp"].iloc[0].strftime("%d-%m-%Y %H:%M")
    avg_hr = g["Heart_clean"].mean()
    avg_rr = g["Resp_clean"].mean()
    avg_range = g["Range_clean"].mean()
    
    hr_sd = g["Heart_clean"].std()
    config = int(g["ConfigurationFile"].iloc[0]) if "ConfigurationFile" in g.columns else 0
    OFFSET = offsets["offset_0"] if config == 0 else offsets["offset_1"]
    final_hr = avg_hr + OFFSET
    
    rows.append([
        ts, rn, len(g),
        avg_hr, avg_rr, avg_range,
        g["Range_clean"].std(), hr_sd, g["Resp_clean"].std(),
        g["Heart_clean"].max() - g["Heart_clean"].min(),
        g["Resp_clean"].max() - g["Resp_clean"].min(),
        np.polyfit(np.arange(len(g)), g["Range_clean"], 1)[0],
        1 / g["Range_clean"].std(),
        final_hr,
        classify_hr(final_hr),
        classify_rr(avg_rr),
        classify_stress(hr_sd)
    ])

# Save run stats
stats_df = pd.DataFrame(rows, columns=[
    "Timestamp","Run","Rows",
    "Avg_HR_clean","Avg_RR_clean","Avg_Range",
    "Range_SD","HR_SD","RR_SD",
    "HR_P2P","RR_P2P",
    "Range_Slope","SQI",
    "Final_Accurate_HR",
    "HR_Class","RR_Class","Stress_Class"
])

stats_df.to_csv(FINAL_STATS_FILE, index=False)
print(f"💾 Saved {len(stats_df)} runs to: {FINAL_STATS_FILE}")
print("🎉 Force reprocessing complete!")
