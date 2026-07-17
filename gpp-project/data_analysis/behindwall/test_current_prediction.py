import pandas as pd
import numpy as np
import joblib
import json
import os
from datetime import datetime, timedelta

# Load the prediction script functions
BASE_DIR = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project\data_analysis"
VITAL_SIGNS_FILE = os.path.join(os.path.dirname(BASE_DIR), "backend", "vital_signs_data_new.csv")
MODEL_FILE = os.path.join(BASE_DIR, "hr_model.joblib")

print("🧪 Testing Current Prediction Logic...")
print("=" * 60)

# Load current sensor data
df_vital = pd.read_csv(VITAL_SIGNS_FILE)
print(f"📊 Total sensor data: {len(df_vital)} rows")

# Get latest 20 readings (as per our new logic)
latest_data = df_vital.tail(20)
print(f"📊 Latest 20 readings analysis:")
print(f"  HR: {latest_data['HeartRate_BPM'].mean():.1f} ± {latest_data['HeartRate_BPM'].std():.1f} BPM")
print(f"  RR: {latest_data['RespirationRate_BPM'].mean():.1f} ± {latest_data['RespirationRate_BPM'].std():.1f} BPM")
print(f"  Range: {latest_data['Range_m'].mean():.3f} ± {latest_data['Range_m'].std():.3f} m")

# Check configuration
config = int(latest_data['Configuration'].iloc[0]) if 'Configuration' in latest_data.columns else 0
print(f"  Configuration: {config}")

# Load calibration offsets
OFFSET_FILE = os.path.join(BASE_DIR, "calibration_offsets.json")
if os.path.exists(OFFSET_FILE):
    offsets = json.load(open(OFFSET_FILE))
else:
    offsets = {"offset_0": 19.82, "offset_1": 32.41}

CALIBRATION_OFFSET = offsets[f"offset_{config}"]
print(f"  Calibration Offset: {CALIBRATION_OFFSET:.2f} BPM")

# Calculate features exactly as the prediction script does
hr_data = latest_data['HeartRate_BPM'].astype(float)
rr_data = latest_data['RespirationRate_BPM'].astype(float)
range_data = latest_data['Range_m'].astype(float)

# Apply calibration
calibrated_hr = hr_data + CALIBRATION_OFFSET

def calculate_sqi(hr_data):
    if len(hr_data) < 2:
        return 0.0
    return 1.0 / (1.0 + hr_data.std())

def calculate_range_slope(range_data):
    if len(range_data) < 2:
        return 0.0
    return (range_data.iloc[-1] - range_data.iloc[0]) / len(range_data)

features = [
    calibrated_hr.mean(),  # Avg_HR_clean (calibrated)
    rr_data.mean(),  # Avg_RR_clean
    range_data.mean(),  # Avg_Range
    range_data.std() if len(range_data) > 1 else 0.1,  # Range_SD
    calibrated_hr.std() if len(calibrated_hr) > 1 else 5.0,  # HR_SD
    rr_data.std() if len(rr_data) > 1 else 1.0,  # RR_SD
    calibrated_hr.max() - calibrated_hr.min(),  # HR_P2P
    rr_data.max() - rr_data.min(),  # RR_P2P
    calculate_sqi(calibrated_hr),  # SQI
    calculate_range_slope(range_data)  # Range_Slope
]

print(f"\n🔧 Calculated Features:")
feature_names = ["Avg_HR_clean", "Avg_RR_clean", "Avg_Range", "Range_SD", "HR_SD", "RR_SD", "HR_P2P", "RR_P2P", "SQI", "Range_Slope"]
for name, value in zip(feature_names, features):
    print(f"  {name:<15}: {value:.3f}")

print(f"\n📊 Calibration Analysis:")
print(f"  Raw HR Avg: {hr_data.mean():.2f} BPM")
print(f"  Calibrated HR Avg: {calibrated_hr.mean():.2f} BPM")
print(f"  Difference: {CALIBRATION_OFFSET:.2f} BPM")

# Load model and predict
model = joblib.load(MODEL_FILE)
prediction = float(model.predict(np.array(features).reshape(1, -1))[0])

# Apply calibration offset fix (same as in predict_with_model.py)
OFFSET_FILE = os.path.join(BASE_DIR, "calibration_offsets.json")
if os.path.exists(OFFSET_FILE):
    offsets = json.load(open(OFFSET_FILE))
    CALIBRATION_OFFSET = offsets["offset_0"]  # Assuming config 0
    prediction = prediction - CALIBRATION_OFFSET  # Subtract to get raw HR
    print(f"\n🔧 Applied calibration offset: -{CALIBRATION_OFFSET:.2f} BPM")
    print(f"  Original model prediction: {prediction + CALIBRATION_OFFSET:.2f} BPM")
    print(f"  After calibration fix: {prediction:.2f} BPM")

print(f"\n🎯 Prediction Results:")
print(f"  Final Prediction: {prediction:.2f} BPM")
print(f"  Raw HR Average: {hr_data.mean():.2f} BPM")
print(f"  Calibrated HR Average: {calibrated_hr.mean():.2f} BPM")

print(f"\n📈 Error Analysis:")
error_vs_raw = abs(prediction - hr_data.mean())
error_vs_calibrated = abs(prediction - calibrated_hr.mean())
print(f"  Error vs Raw HR: {error_vs_raw:.2f} BPM")
print(f"  Error vs Calibrated HR: {error_vs_calibrated:.2f} BPM")

# Check if this is reasonable
if error_vs_raw > 20:
    print(f"  ❌ HIGH ERROR detected vs raw data!")
elif error_vs_raw > 15:
    print(f"  ⚠️ Moderate error vs raw data")
else:
    print(f"  ✅ Reasonable error vs raw data")

if error_vs_calibrated > 20:
    print(f"  ❌ HIGH ERROR detected vs calibrated data!")
elif error_vs_calibrated > 15:
    print(f"  ⚠️ Moderate error vs calibrated data")
else:
    print(f"  ✅ Reasonable error vs calibrated data")

# Compare with training data characteristics
print(f"\n🎓 Training Data Context:")
FINAL_STATS_FILE = os.path.join(BASE_DIR, "final_run_stats_new.csv")
df_train = pd.read_csv(FINAL_STATS_FILE)
print(f"  Training HR Range: {df_train['Avg_HR_clean'].min():.1f} - {df_train['Avg_HR_clean'].max():.1f} BPM")
print(f"  Current Avg_HR_clean: {features[0]:.1f} BPM")

if features[0] < df_train['Avg_HR_clean'].min() or features[0] > df_train['Avg_HR_clean'].max():
    print(f"  ⚠️ Current feature is OUTSIDE training range!")
else:
    print(f"  ✅ Current feature is within training range")

print(f"\n🎯 Diagnosis:")
if error_vs_raw > 20:
    print("❌ The 20+ BPM error is confirmed.")
    print("🔧 Potential fixes:")
    print("  1. Check if calibration offset is appropriate")
    print("  2. Verify sensor data quality")
    print("  3. Consider retraining with more diverse data")
else:
    print("✅ Prediction error is within acceptable range")
