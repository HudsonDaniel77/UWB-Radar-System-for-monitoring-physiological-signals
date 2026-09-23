import pandas as pd
import numpy as np
import os
import json
import sys
import io

# UTF-8 encoding fix
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ==========================================================
# PATHS - Dynamic resolution
# ==========================================================
DATA_ANALYSIS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(DATA_ANALYSIS_DIR, "..", "backend"))

CLEAN_FILE = os.path.join(DATA_ANALYSIS_DIR, "cleaned_vital_signs_new_tryingsomething.csv")
COMPARISON_FILE = os.path.join(DATA_ANALYSIS_DIR, "VariousData.csv")
OFFSET_FILE = os.path.join(DATA_ANALYSIS_DIR, "calibration_offsets.json")
FINAL_STATS_FILE = os.path.join(DATA_ANALYSIS_DIR, "final_run_stats_new_tryingsomething.csv")

os.makedirs(os.path.dirname(FINAL_STATS_FILE), exist_ok=True)

# Helper function to parse timestamps flexibly
def parse_dt(s):
    if pd.isna(s):
        return pd.NaT
    return pd.to_datetime(s, format="mixed", dayfirst=True, errors="coerce")

# ==========================================================
# 1️⃣ LOAD OR LEARN CONFIG HR OFFSETS
# ==========================================================
def learn_offsets():
    print("📘 Learning HR offsets from smartwatch + finger + radar...")
    if not os.path.exists(COMPARISON_FILE):
        return {"offset_0": 19.82, "offset_1": 32.41}

    comp = pd.read_csv(COMPARISON_FILE)
    comp = comp.rename(columns={
        "Average Heart Rate": "Sensor_HR",
        "Unnamed: 2": "Smartwatch_HR",
        "Unnamed: 3": "Finger_HR",
        "Configuration": "Config",
        "ConfigurationFile": "Config"
    })

    numeric_cols = ["Sensor_HR", "Smartwatch_HR", "Finger_HR", "Config"]
    for c in numeric_cols:
        if c in comp.columns:
            comp[c] = pd.to_numeric(comp[c], errors="coerce")

    comp = comp.dropna(subset=[c for c in numeric_cols if c in comp.columns])
    if comp.empty:
        return {"offset_0": 19.82, "offset_1": 32.41}

    comp["Real_HR"] = (comp["Smartwatch_HR"] + comp["Finger_HR"]) / 2
    comp["Offset"] = comp["Real_HR"] - comp["Sensor_HR"]

    o0 = comp[comp["Config"] == 0]["Offset"].mean()
    o1 = comp[comp["Config"] == 1]["Offset"].mean()

    offsets = {
        "offset_0": float(o0) if not np.isnan(o0) else 19.82,
        "offset_1": float(o1) if not np.isnan(o1) else 32.41,
    }

    try:
        with open(OFFSET_FILE, "w") as f:
            json.dump(offsets, f, indent=2)
        print("✔ Saved calibration offsets:", offsets)
    except Exception:
        pass

    return offsets

if os.path.exists(OFFSET_FILE):
    try:
        offsets = json.load(open(OFFSET_FILE))
        print("✔ Loaded calibration offsets:", offsets)
    except Exception:
        offsets = {"offset_0": 19.82, "offset_1": 32.41}
elif os.path.exists(COMPARISON_FILE):
    offsets = learn_offsets()
else:
    offsets = {"offset_0": 19.82, "offset_1": 32.41}

# ==========================================================
# 2️⃣ LOAD DATA (From specific session or CLEAN_FILE)
# ==========================================================
target_df = None

# If a specific raw session file was passed
if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
    arg_path = os.path.abspath(sys.argv[1])
    # If passed raw session CSV, ensure it has been cleaned or read CLEAN_FILE
    print(f"✔ Calibration requested for: {os.path.basename(arg_path)}")

if os.path.exists(CLEAN_FILE):
    df = pd.read_csv(CLEAN_FILE)
    df["Parsed_Timestamp"] = df["Timestamp"].apply(parse_dt)
    df = df.dropna(subset=["Parsed_Timestamp"])
    df = df.sort_values(by=["Parsed_Timestamp", "SessionTime"]).reset_index(drop=True)
else:
    print(f"❌ Cleaned file not found: {CLEAN_FILE}")
    sys.exit(1)

if df.empty:
    print("⚠ No cleaned data available.")
    sys.exit(0)

# ==========================================================
# 3️⃣ LOAD EXISTING FINAL STATS FOR INCREMENTAL / IDEMPOTENT RUN
# ==========================================================
existing_ts_strings = set()
last_run_number = 0

if os.path.exists(FINAL_STATS_FILE) and os.path.getsize(FINAL_STATS_FILE) > 0:
    try:
        prev = pd.read_csv(FINAL_STATS_FILE)
        if not prev.empty and "Run" in prev.columns:
            last_run_number = int(pd.to_numeric(prev["Run"], errors="coerce").fillna(0).max())
            existing_ts_strings = set(prev["Timestamp"].astype(str))
            print(f"✔ Previous final stats loaded. Total runs = {len(prev)}, Last run = {last_run_number}")
    except Exception as e:
        print(f"⚠ Could not read previous final stats: {e}")

# ==========================================================
# 4️⃣ DETECT RUNS IN CLEANED DATA
# ==========================================================
# Detect run boundaries: SessionTime reset or time jump > 60 seconds
df["Run"] = 0
run_counter = 1

df.loc[0, "Run"] = run_counter
for i in range(1, len(df)):
    st_reset = df.loc[i, "SessionTime"] < df.loc[i - 1, "SessionTime"]
    time_jump = False
    try:
        diff_sec = (df.loc[i, "Parsed_Timestamp"] - df.loc[i - 1, "Parsed_Timestamp"]).total_seconds()
        if diff_sec > 60:
            time_jump = True
    except Exception:
        pass

    if st_reset or time_jump:
        run_counter += 1
    df.loc[i, "Run"] = run_counter

# Group each detected run with at least 5 samples
valid_runs = [(rn, g) for rn, g in df.groupby("Run") if len(g) >= 5]

if not valid_runs:
    print("⚠ No valid runs found in cleaned data (need >= 5 samples per run).")
    sys.exit(0)

# ==========================================================
# 5️⃣ COMPUTE RUN STATISTICS FOR RUNS NOT YET SAVED
# ==========================================================
final_rows = []
assigned_run_num = last_run_number

for rn, g in valid_runs:
    first_row = g.iloc[0]
    ts_formatted = g["Parsed_Timestamp"].iloc[0].strftime("%d-%m-%Y %H:%M")

    # If this run was already saved in final_stats, skip duplicate
    if ts_formatted in existing_ts_strings:
        continue

    assigned_run_num += 1

    avg_hr = float(g["Heart_clean"].mean())
    avg_rr = float(g["Resp_clean"].mean())
    avg_range = float(g["Range_clean"].mean())

    range_sd = float(g["Range_clean"].std()) if len(g) > 1 else 0.05
    hr_sd = float(g["Heart_clean"].std()) if len(g) > 1 else 5.0
    rr_sd = float(g["Resp_clean"].std()) if len(g) > 1 else 1.0

    hr_p2p = float(g["Heart_clean"].max() - g["Heart_clean"].min())
    rr_p2p = float(g["Resp_clean"].max() - g["Resp_clean"].min())

    arr = g["Range_clean"].dropna().values
    t = np.arange(len(arr))
    range_slope = float(np.polyfit(t, arr, 1)[0]) if len(arr) > 1 else 0.0

    sqi = 0.0 if (range_sd == 0 or np.isnan(range_sd)) else float(1.0 / range_sd)

    config = int(first_row.get("ConfigurationFile", 0))
    offset = offsets.get("offset_0", 19.82) if config == 0 else offsets.get("offset_1", 32.41)

    final_hr = avg_hr + offset

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

    def classify_stress(sd, mean_hr):
        cv = sd / mean_hr if mean_hr > 0 else 0.05
        if cv < 0.08: return "Relaxed"
        elif cv < 0.15: return "Mild Stress"
        elif cv < 0.22: return "High Stress"
        else: return "Very High Stress"

    final_rows.append([
        ts_formatted, assigned_run_num, len(g),
        avg_hr, avg_rr, avg_range,
        range_sd, hr_sd, rr_sd,
        hr_p2p, rr_p2p,
        range_slope, sqi,
        final_hr,
        classify_hr(final_hr),
        classify_rr(avg_rr),
        classify_stress(hr_sd, avg_hr)
    ])
    existing_ts_strings.add(ts_formatted)

# ==========================================================
# 6️⃣ APPEND NEW RUNS TO FINAL_STATS_FILE
# ==========================================================
cols = [
    "Timestamp", "Run", "Rows",
    "Avg_HR_clean", "Avg_RR_clean", "Avg_Range",
    "Range_SD", "HR_SD", "RR_SD",
    "HR_P2P", "RR_P2P",
    "Range_Slope", "SQI",
    "Final_Accurate_HR",
    "HR_Class", "RR_Class", "Stress_Class"
]

if final_rows:
    out_df = pd.DataFrame(final_rows, columns=cols)
    write_header = not os.path.exists(FINAL_STATS_FILE) or os.path.getsize(FINAL_STATS_FILE) == 0
    out_df.to_csv(FINAL_STATS_FILE, mode="a", index=False, header=write_header)

    print("===============================================")
    print("✔ NEW FINAL RUN STATS GENERATED")
    print(f"✔ Added runs: {len(out_df)}")
    print(f"✔ Saved → {FINAL_STATS_FILE}")
    print("===============================================")
else:
    print("✔ All runs in cleaned data are already recorded in final stats.")
