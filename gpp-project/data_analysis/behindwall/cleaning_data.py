import pandas as pd
import numpy as np
from scipy.signal import butter, filtfilt
import os, json
import re

# ==========================================================
# PATHS  (Behind-Wall cleaning pipeline)
# ==========================================================
RAW_FILE = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project\backend\vital_signs_data_new.csv"
CLEAN_FILE = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project\data_analysis\behindwall\cleaned_vital_signs_new.csv"
COMPARISON_FILE = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project\data_analysis\behindwall\VariousData.csv"
OFFSET_FILE = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project\data_analysis\behindwall\calibration_offsets.json"
FINAL_STATS_FILE = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project\data_analysis\behindwall\final_run_stats_new.csv"

os.makedirs(os.path.dirname(FINAL_STATS_FILE), exist_ok=True)

# ==========================================================
# Robust timestamp parsing helper
# ==========================================================
def clean_ts_string(s: str) -> str:
    """Sanitize raw timestamp string: normalize spaces, slashes, unicode dashes, remove tz text."""
    if pd.isna(s):
        return ""
    s = str(s)
    # replace unicode dashes with ascii hyphen
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    # replace slashes with hyphens
    s = s.replace("/", "-")
    # remove common timezone markers like 'GMT', 'UTC' and offsets
    s = re.sub(r'\b(?:GMT|UTC)\b[^\s]*', '', s, flags=re.IGNORECASE)
    # remove trailing timezone offsets like +05:30 or -0530
    s = re.sub(r'[\+\-]\d{2}:?\d{2}$', '', s)
    # collapse whitespace (tabs, multiple spaces) to a single space
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def parse_timestamps(series: pd.Series) -> pd.Series:
    """Try several formats, then fallback to pandas parser with dayfirst=True."""
    s = series.astype(str).apply(clean_ts_string)

    # common formats to try (most specific first)
    formats = [
        "%d-%m-%Y %H:%M:%S.%f",  # with microseconds
        "%d-%m-%Y %H:%M:%S",     # with seconds
        "%d-%m-%Y %H:%M",        # no seconds (your main format)
        "%d-%m-%y %H:%M:%S",
        "%d-%m-%y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]

    parsed = pd.Series(pd.NaT, index=s.index)

    # attempt strict parsing format-by-format
    for fmt in formats:
        mask = parsed.isna()
        if not mask.any():
            break
        try:
            parsed_vals = pd.to_datetime(s[mask], format=fmt, dayfirst=True, errors="coerce")
            parsed.loc[mask] = parsed_vals
        except Exception:
            # ignore and continue trying other formats
            pass

    # final broad fallback using pandas' flexible parser
    still_missing = parsed.isna()
    if still_missing.any():
        try:
            fallback = pd.to_datetime(s[still_missing], dayfirst=True, errors="coerce")
            parsed.loc[still_missing] = fallback
        except Exception:
            pass

    return parsed

# ==========================================================
# LOAD RAW FILE
# ==========================================================
if not os.path.exists(RAW_FILE):
    print("Raw file not found.")
    exit()

raw_df = pd.read_csv(RAW_FILE, on_bad_lines="skip")

# Rename config column if needed
if "Configuration" in raw_df.columns:
    raw_df = raw_df.rename(columns={"Configuration": "ConfigurationFile"})

# ==========================================================
# TIMESTAMP PARSING (robust)
# ==========================================================
# Keep raw strings for debugging then parse
raw_df["__ts_raw"] = raw_df["Timestamp"].astype(str)

parsed_ts = parse_timestamps(raw_df["__ts_raw"])
fail_count = parsed_ts.isna().sum()
print("Timestamp parse failures:", fail_count)

if fail_count:
    failed_strings = raw_df.loc[parsed_ts.isna(), "__ts_raw"].head(50).tolist()
    print("FAILED TIMESTAMP ROWS (showing first 50):")
    print(failed_strings)

raw_df["Timestamp"] = parsed_ts
raw_df = raw_df.drop(columns=["__ts_raw"])

# drop rows with unparseable timestamps
raw_df = raw_df.dropna(subset=["Timestamp"])
raw_df = raw_df.sort_values(by=["Timestamp", "SessionTime"]).reset_index(drop=True)

# ==========================================================
# LOAD EXISTING CLEAN FILE TO DETECT NEW RAW ROWS
# ==========================================================
if os.path.exists(CLEAN_FILE):
    prev = pd.read_csv(CLEAN_FILE)
    # parse prev timestamps robustly too
    prev["Timestamp"] = parse_timestamps(prev["Timestamp"].astype(str))
    last_clean_ts = prev["Timestamp"].max()
    print("Last clean timestamp:", last_clean_ts)
else:
    prev = None
    last_clean_ts = pd.Timestamp.min
    print("No previous clean file -> start fresh.")

# Only NEW raw rows
raw_new = raw_df[raw_df["Timestamp"] > last_clean_ts].copy()

if raw_new.empty:
    print("No NEW raw rows in vital_signs_data_new.csv")
    exit()

print("New raw rows:", len(raw_new))

# ==========================================================
# CLEANING PIPELINE
# ==========================================================
numeric_cols = ["SessionTime","HeartRate_BPM","RespirationRate_BPM","Range_m"]
for c in numeric_cols:
    if c in raw_new.columns:
        raw_new[c] = pd.to_numeric(raw_new[c], errors="coerce")

# Remove impossible values
clean = raw_new[
    raw_new["HeartRate_BPM"].between(40, 180) &
    raw_new["RespirationRate_BPM"].between(5, 40) &
    raw_new["Range_m"].between(0.1, 2.0)
].reset_index(drop=True)

if clean.empty:
    print("All new rows invalid")
    exit()

# Detect stuck HR
mode_hr = clean["HeartRate_BPM"].mode().iloc[0]
if clean["HeartRate_BPM"].value_counts().max() > 0.6 * len(clean) and mode_hr > 110:
    clean = clean[clean["HeartRate_BPM"] != mode_hr]

if clean.empty:
    print("Stuck HR removed all rows.")
    exit()

# LPF
def lowpass(arr, cutoff=0.3, fs=10):
    arr = arr.ffill().bfill()
    if len(arr) < 16:  # Need at least 16 samples for the filter
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

final_clean = clean[
    [
        "Timestamp","User","SessionTime",
        "HeartRate_BPM","RespirationRate_BPM","Range_m",
        "HeartWaveform","BreathWaveform","HeartRate_FFT","BreathRate_FFT",
        "ConfigurationFile",
        "Heart_clean","Resp_clean","Range_clean"
    ]
]

print("Cleaned new raw rows:", len(final_clean))

# ==========================================================
# RUN DETECTION PREPARATION
# ==========================================================
# concat previous cleaned (prev) + the newly cleaned rows for run detection
if prev is not None and not prev.empty:
    # ensure prev has the expected columns (if not, try to keep intersection)
    common_cols = [c for c in final_clean.columns if c in prev.columns]
    df = pd.concat([prev[common_cols], final_clean[common_cols]], ignore_index=True)
else:
    df = final_clean.copy()

# normalize timestamp column in df (parse robustly to be safe)
df["Timestamp"] = parse_timestamps(df["Timestamp"].astype(str))
df = df.sort_values(by=["Timestamp", "SessionTime"]).reset_index(drop=True)

# Ensure SessionTime numeric for run detection
df["SessionTime"] = pd.to_numeric(df["SessionTime"], errors="coerce").fillna(0).astype(float)

# ==========================================================
# LOAD OFFSETS
# ==========================================================
if os.path.exists(OFFSET_FILE):
    offsets = json.load(open(OFFSET_FILE))
else:
    offsets = {"offset_0": 10.5, "offset_1": 10.5}

# ==========================================================
# LOAD EXISTING FINAL STATS
# ==========================================================
if os.path.exists(FINAL_STATS_FILE):
    prev_stats = pd.read_csv(FINAL_STATS_FILE)
    prev_stats["Timestamp"] = parse_timestamps(prev_stats["Timestamp"].astype(str))
    last_final_ts = prev_stats["Timestamp"].max()
    last_run = int(prev_stats["Run"].max())
    print("Last final stats timestamp:", last_final_ts)
else:
    last_final_ts = pd.Timestamp.min
    last_run = 0
    print("No previous final stats -> fresh start")

# Only NEW cleaned rows for run detection
df_new = df[df["Timestamp"] > last_final_ts].copy()

if df_new.empty:
    print("No new runs to add")
    exit()

# Reset index (avoids KeyError when using loc[i])
df_new = df_new.reset_index(drop=True)

print("New cleaned rows for run detection:", len(df_new))

# ==========================================================
# RUN DETECTION
# ==========================================================
df_new["Run"] = 0
run_no = last_run + 1
df_new.loc[0, "Run"] = run_no

for i in range(1, len(df_new)):
    # SessionTime is numeric now, safe to compare
    if df_new.loc[i, "SessionTime"] < df_new.loc[i - 1, "SessionTime"]:
        run_no += 1
    df_new.loc[i, "Run"] = run_no

# Only valid runs (min 5 samples)
valid_runs = [(rn, g) for rn, g in df_new.groupby("Run") if len(g) >= 5]
if not valid_runs:
    print("No valid runs detected")
    exit()

print("Valid new runs:", [rn for rn, _ in valid_runs])

# ==========================================================
# SAVE ONLY CLEANED ROWS OF NEW RUNS (avoid duplicates)
# ==========================================================
new_run_ids = [rn for rn, _ in valid_runs]
new_run_cleaned_samples = df_new[df_new["Run"].isin(new_run_ids)].copy()

# If clean file exists, avoid appending rows that are already there
if os.path.exists(CLEAN_FILE):
    existing = pd.read_csv(CLEAN_FILE)
    # robustly parse existing timestamps
    existing["Timestamp"] = parse_timestamps(existing["Timestamp"].astype(str))
    # create a simple unique key to check duplicates: Timestamp + SessionTime + User
    existing["__key"] = existing["Timestamp"].astype(str) + "|" + existing["SessionTime"].astype(str) + "|" + existing["User"].astype(str)
    new_run_cleaned_samples["__key"] = new_run_cleaned_samples["Timestamp"].astype(str) + "|" + new_run_cleaned_samples["SessionTime"].astype(str) + "|" + new_run_cleaned_samples["User"].astype(str)
    new_run_cleaned_samples = new_run_cleaned_samples[~new_run_cleaned_samples["__key"].isin(existing["__key"])].drop(columns="__key")
else:
    # ensure we only have the final columns
    pass

write_header = not os.path.exists(CLEAN_FILE)
# write only the final columns (to preserve expected CSV layout)
cols_to_write = [
    "Timestamp","User","SessionTime",
    "HeartRate_BPM","RespirationRate_BPM","Range_m",
    "HeartWaveform","BreathWaveform","HeartRate_FFT","BreathRate_FFT",
    "ConfigurationFile",
    "Heart_clean","Resp_clean","Range_clean"
]
new_run_cleaned_samples.to_csv(CLEAN_FILE, mode="a", index=False, header=write_header, columns=cols_to_write)

print("------------------------------------------------------")
print(f"Appended cleaned samples for new runs only: {len(new_run_cleaned_samples)}")
print("------------------------------------------------------")

# ==========================================================
# COMPUTE FINAL RUN STATS
# ==========================================================
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
    config = int(g["ConfigurationFile"].iloc[0])
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

# ==========================================================
# SAVE RUN STATS
# ==========================================================
stats_df = pd.DataFrame(rows, columns=[
    "Timestamp","Run","Rows",
    "Avg_HR_clean","Avg_RR_clean","Avg_Range",
    "Range_SD","HR_SD","RR_SD",
    "HR_P2P","RR_P2P",
    "Range_Slope","SQI",
    "Final_Accurate_HR",
    "HR_Class","RR_Class","Stress_Class"
])

write_header = not os.path.exists(FINAL_STATS_FILE)
stats_df.to_csv(FINAL_STATS_FILE, mode="a", index=False, header=write_header)

print("======================================")
print("ADDED NEW RUNS:", len(stats_df))
print("Saved in:", FINAL_STATS_FILE)
print("======================================")
