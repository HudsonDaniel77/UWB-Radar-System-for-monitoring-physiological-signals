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

CLEAN_FILE = os.path.join(DATA_ANALYSIS_DIR, "cleaned_vital_signs_new_tryingsomething.csv")
COMPARISON_FILE = os.path.join(DATA_ANALYSIS_DIR, "VariousData.csv")
OFFSET_FILE = os.path.join(DATA_ANALYSIS_DIR, "calibration_offsets.json")
FINAL_STATS_FILE = os.path.join(DATA_ANALYSIS_DIR, "final_run_stats_new_tryingsomething.csv")

os.makedirs(os.path.dirname(FINAL_STATS_FILE), exist_ok=True)

# ==========================================================
# 1️⃣ LOAD CLEANED FILE (incremental)
# ==========================================================
if not os.path.exists(CLEAN_FILE):
    print("❌ cleaned_vital_signs_new.csv not found.")
    exit(1)

df = pd.read_csv(CLEAN_FILE)

# 🔑 FIX: Convert Timestamp back to datetime
df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")

df = df.dropna(subset=["Timestamp"])
df = df.sort_values(by=["Timestamp", "SessionTime"]).reset_index(drop=True)


# ==========================================================
# 2️⃣ LOAD OR LEARN CONFIG HR OFFSETS
# ==========================================================
def learn_offsets():
    print("📘 Learning HR offsets from smartwatch + finger + radar...")

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
        comp[c] = pd.to_numeric(comp[c], errors="coerce")

    comp = comp.dropna(subset=numeric_cols)

    if comp.empty:
        print("⚠ No calibration rows → Using defaults.")
        return {"offset_0": 10.5, "offset_1": 10.5}

    comp["Real_HR"] = (comp["Smartwatch_HR"] + comp["Finger_HR"]) / 2
    comp["Offset"] = comp["Real_HR"] - comp["Sensor_HR"]

    o0 = comp[comp["Config"] == 0]["Offset"].mean()
    o1 = comp[comp["Config"] == 1]["Offset"].mean()

    offsets = {
        "offset_0": float(o0) if not np.isnan(o0) else 10.5,
        "offset_1": float(o1) if not np.isnan(o1) else 10.5,
    }

    with open(OFFSET_FILE, "w") as f:
        json.dump(offsets, f, indent=2)

    print("✔ Saved calibration offsets:", offsets)
    return offsets


# Load or learn
if os.path.exists(OFFSET_FILE):
    offsets = json.load(open(OFFSET_FILE))
    print("✔ Loaded calibration offsets:", offsets)
elif os.path.exists(COMPARISON_FILE):
    offsets = learn_offsets()
else:
    print("⚠ No calibration available → Using default offsets.")
    offsets = {"offset_0": 10.5, "offset_1": 10.5}

# ==========================================================
# 3️⃣ LOAD EXISTING FINAL STATS FOR INCREMENTAL MODE
# ==========================================================
if os.path.exists(FINAL_STATS_FILE):
    prev = pd.read_csv(FINAL_STATS_FILE)
    prev["Timestamp"] = pd.to_datetime(prev["Timestamp"], format="%d-%m-%Y %H:%M", errors="coerce")
    last_final_ts = prev["Timestamp"].max()
    last_run_number = int(prev["Run"].max())
    print(f"✔ Previous final stats loaded. Last timestamp = {last_final_ts}, Last run = {last_run_number}")
else:
    prev = None
    last_final_ts = pd.Timestamp.min
    last_run_number = 0
    print("ℹ No previous final stats → starting fresh.")

# ==========================================================
# 4️⃣ SELECT ONLY NEW CLEANED ROWS
# ==========================================================
df_new = df[df["Timestamp"] > last_final_ts].copy()
df_new = df_new.reset_index(drop=True)


if df_new.empty:
    print("✔ No new cleaned rows to process.")
    exit(0)

print(f"➡ New cleaned rows: {len(df_new)}")

# ==========================================================
# 5️⃣ DETECT NEW RUNS USING SessionTime RESET
# ==========================================================
df_new["Run"] = 0
run_num = last_run_number + 1

df_new.loc[0, "Run"] = run_num

for i in range(1, len(df_new)):
    if df_new.loc[i, "SessionTime"] < df_new.loc[i - 1, "SessionTime"]:
        run_num += 1
    df_new.loc[i, "Run"] = run_num

# ==========================================================
# 6️⃣ FILTER RUNS WITH AT LEAST 5 SAMPLES
# ==========================================================
valid_runs = [(rn, g) for rn, g in df_new.groupby("Run") if len(g) >= 5]

if not valid_runs:
    print("⚠ No valid runs in new data.")
    exit(0)

# ==========================================================
# 7️⃣ COMPUTE FINAL RUN STATISTICS
# ==========================================================
final_rows = []

for rn, g in valid_runs:

    timestamp = g["Timestamp"].iloc[0].strftime("%d-%m-%Y %H:%M")

    avg_hr = g["Heart_clean"].mean()
    avg_rr = g["Resp_clean"].mean()
    avg_range = g["Range_clean"].mean()

    range_sd = g["Range_clean"].std()
    hr_sd = g["Heart_clean"].std()
    rr_sd = g["Resp_clean"].std()

    hr_p2p = g["Heart_clean"].max() - g["Heart_clean"].min()
    rr_p2p = g["Resp_clean"].max() - g["Resp_clean"].min()

    arr = g["Range_clean"].dropna().values
    t = np.arange(len(arr))
    range_slope = float(np.polyfit(t, arr, 1)[0]) if len(arr) > 1 else 0.0

    sqi = 0 if range_sd in [0, np.nan] else float(1 / range_sd)

    config = int(g["ConfigurationFile"].iloc[0])
    OFFSET = offsets["offset_0"] if config == 0 else offsets["offset_1"]

    final_hr = avg_hr + OFFSET

    # CLASSIFICATIONS
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

    def classify_stress(v):
        if v < 0.05: return "Relaxed"
        elif v < 0.15: return "Mild Stress"
        elif v < 0.25: return "High Stress"
        else: return "Very High Stress"

    final_rows.append([
        timestamp, rn, len(g),
        avg_hr, avg_rr, avg_range,
        range_sd, hr_sd, rr_sd,
        hr_p2p, rr_p2p,
        range_slope, sqi,
        final_hr,
        classify_hr(final_hr),
        classify_rr(avg_rr),
        classify_stress(hr_sd)
    ])

# ==========================================================
# 8️⃣ APPEND ONLY NEW RUNS TO final_run_stats_new.csv
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

out_df = pd.DataFrame(final_rows, columns=cols)

write_header = not os.path.exists(FINAL_STATS_FILE)
out_df.to_csv(FINAL_STATS_FILE, mode="a", index=False, header=write_header)

print("===============================================")
print("✔ NEW FINAL RUN STATS GENERATED")
print(f"✔ Added runs: {len(out_df)}")
print(f"✔ Saved → {FINAL_STATS_FILE}")
print("===============================================")
