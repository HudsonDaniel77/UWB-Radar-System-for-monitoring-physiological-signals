import pandas as pd
import numpy as np
import joblib
import json
import os
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

BASE_DIR = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project-behindwall"
MODEL_FILE = os.path.join(BASE_DIR, "data_analysis", "hr_model.joblib")
TEST_DATA_FILE = os.path.join(BASE_DIR, "data_analysis", "final_run_stats_new.csv")

print("🎯 Final Model Validation Test")
print("=" * 50)

# Load the trained model and test data
model = joblib.load(MODEL_FILE)
df_test = pd.read_csv(TEST_DATA_FILE)

# Features used for training
feature_cols = ['Avg_HR_clean', 'Avg_RR_clean', 'Avg_Range', 'Range_SD', 
                'HR_SD', 'RR_SD', 'HR_P2P', 'RR_P2P', 'Range_Slope', 'SQI']

X_test = df_test[feature_cols]
y_true = df_test['Final_Accurate_HR']

# Make predictions
y_pred = model.predict(X_test)

# Apply calibration offset (subtract to get raw HR)
OFFSET_FILE = os.path.join(BASE_DIR, "data_analysis", "calibration_offsets.json")
if os.path.exists(OFFSET_FILE):
    offsets = json.load(open(OFFSET_FILE))
    CALIBRATION_OFFSET = offsets["offset_0"]
    y_pred_raw = y_pred - CALIBRATION_OFFSET
    print(f"🔧 Applied calibration offset: -{CALIBRATION_OFFSET:.2f} BPM")
else:
    y_pred_raw = y_pred
    print("⚠️ No calibration offset found")

# Calculate metrics
mae = mean_absolute_error(y_true, y_pred_raw)
rmse = np.sqrt(mean_squared_error(y_true, y_pred_raw))
r2 = r2_score(y_true, y_pred_raw)

print(f"\n📊 Model Performance Metrics:")
print(f"  MAE: {mae:.2f} BPM")
print(f"  RMSE: {rmse:.2f} BPM") 
print(f"  R²: {r2:.3f}")

print(f"\n📈 Performance Analysis:")
if mae <= 5:
    print("  ✅ EXCELLENT: MAE ≤ 5 BPM")
elif mae <= 8:
    print("  ✅ GOOD: MAE ≤ 8 BPM")
elif mae <= 12:
    print("  ⚠️ MODERATE: MAE ≤ 12 BPM")
else:
    print("  ❌ POOR: MAE > 12 BPM")

if r2 >= 0.85:
    print("  ✅ EXCELLENT: R² ≥ 0.85")
elif r2 >= 0.75:
    print("  ✅ GOOD: R² ≥ 0.75")
elif r2 >= 0.65:
    print("  ⚠️ MODERATE: R² ≥ 0.65")
else:
    print("  ❌ POOR: R² < 0.65")

print(f"\n🎯 Sample Predictions (First 5):")
for i in range(min(5, len(y_pred_raw))):
    print(f"  Sample {i+1}: True={y_true.iloc[i]:.1f} BPM, Pred={y_pred_raw[i]:.1f} BPM, Error={abs(y_true.iloc[i]-y_pred_raw[i]):.1f} BPM")

print(f"\n🎉 Model validation complete!")
