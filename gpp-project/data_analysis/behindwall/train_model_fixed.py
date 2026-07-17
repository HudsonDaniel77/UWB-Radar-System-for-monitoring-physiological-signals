import pandas as pd
import numpy as np
import joblib
import json
import os
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb

BASE_DIR = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project"
DATA_FILE = os.path.join(BASE_DIR, "data_analysis", "final_run_stats_new.csv")
MODEL_FILE = os.path.join(BASE_DIR, "data_analysis", "hr_model_fixed.joblib")
METRICS_FILE = os.path.join(BASE_DIR, "data_analysis", "hr_model_fixed_metrics.json")

print("🔧 Fixing Model Training - Target: Raw HR (Not Calibrated)")
print("=" * 60)

# Load data
df = pd.read_csv(DATA_FILE)

# Features for training
feature_cols = ['Avg_HR_clean', 'Avg_RR_clean', 'Avg_Range', 'Range_SD', 
                'HR_SD', 'RR_SD', 'HR_P2P', 'RR_P2P', 'Range_Slope', 'SQI']

X = df[feature_cols]

# CRITICAL FIX: Use Avg_HR_clean (raw HR) as target, NOT Final_Accurate_HR (calibrated)
y_raw = df['Avg_HR_clean']  # This is the raw HR we want to predict
y_calibrated = df['Final_Accurate_HR']  # This is calibrated (raw + offset)

print(f"📊 Data Analysis:")
print(f"  Raw HR (Avg_HR_clean): {y_raw.mean():.1f} ± {y_raw.std():.1f} BPM")
print(f"  Calibrated HR (Final_Accurate_HR): {y_calibrated.mean():.1f} ± {y_calibrated.std():.1f} BPM")
print(f"  Calibration Offset: {(y_calibrated.mean() - y_raw.mean()):.2f} BPM")

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y_raw, test_size=0.2, random_state=42)

print(f"\n🎯 Training Model to Predict RAW HR:")
print(f"  Training samples: {len(X_train)}")
print(f"  Test samples: {len(X_test)}")

# Train model
model = xgb.XGBRegressor(
    n_estimators=100,
    max_depth=6,
    learning_rate=0.1,
    random_state=42
)

model.fit(X_train, y_train)

# Predictions
y_pred = model.predict(X_test)

# Calculate metrics
mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2 = r2_score(y_test, y_pred)

print(f"\n📈 Model Performance (RAW HR Target):")
print(f"  MAE: {mae:.2f} BPM")
print(f"  RMSE: {rmse:.2f} BPM")
print(f"  R²: {r2:.3f}")

# Performance assessment
if mae <= 5:
    print("  ✅ EXCELLENT: MAE ≤ 5 BPM")
elif mae <= 8:
    print("  ✅ GOOD: MAE ≤ 8 BPM")
else:
    print("  ⚠️ NEEDS IMPROVEMENT: MAE > 8 BPM")

# Save model
joblib.dump(model, MODEL_FILE)
print(f"\n💾 Model saved as: hr_model_fixed.joblib")

# Save metrics
metrics = {
    'MAE': mae,
    'RMSE': rmse,
    'R2': r2,
    'n_train': len(X_train),
    'n_test': len(X_test),
    'target': 'Avg_HR_clean (Raw HR)',
    'features': feature_cols,
    'feature_importances': {k: float(v) for k, v in zip(feature_cols, model.feature_importances_)},
    'chosen_model': 'XGBoost'
}

with open(METRICS_FILE, 'w') as f:
    json.dump(metrics, f, indent=2)

print(f"📊 Metrics saved as: hr_model_fixed_metrics.json")

# Test with current data
print(f"\n🧪 Testing with Current Sensor Data:")
VITAL_SIGNS_FILE = os.path.join(BASE_DIR, "backend", "vital_signs_data_new.csv")

if os.path.exists(VITAL_SIGNS_FILE):
    df_current = pd.read_csv(VITAL_SIGNS_FILE)
    if len(df_current) >= 20:
        recent_data = df_current.tail(20)
        
        # Calculate features (same as training)
        hr_data = recent_data['HeartRate_BPM'].astype(float)
        rr_data = recent_data['RespirationRate_BPM'].astype(float)
        range_data = recent_data['Range_m'].astype(float)
        
        features = np.array([
            hr_data.mean(),  # Avg_HR_clean (raw)
            rr_data.mean(),  # Avg_RR_clean
            range_data.mean(),  # Avg_Range
            range_data.std() if len(range_data) > 1 else 0.1,  # Range_SD
            hr_data.std() if len(hr_data) > 1 else 5.0,  # HR_SD
            rr_data.std() if len(rr_data) > 1 else 1.0,  # RR_SD
            hr_data.max() - hr_data.min(),  # HR_P2P
            rr_data.max() - rr_data.min(),  # RR_P2P
            1.0 / (1.0 + hr_data.std()) if len(hr_data) > 1 else 15.0,  # SQI
            (range_data.iloc[-1] - range_data.iloc[0]) / len(range_data) if len(range_data) > 1 else 0.001  # Range_Slope
        ])
        
        # Predict
        current_pred = float(model.predict(features.reshape(1, -1))[0])
        current_avg = hr_data.mean()
        
        print(f"  Current Raw HR: {current_avg:.1f} BPM")
        print(f"  Model Prediction: {current_pred:.1f} BPM")
        print(f"  Error: {abs(current_pred - current_avg):.1f} BPM")
        
        if abs(current_pred - current_avg) <= 5:
            print("  ✅ EXCELLENT: Error ≤ 5 BPM")
        elif abs(current_pred - current_avg) <= 8:
            print("  ✅ GOOD: Error ≤ 8 BPM")
        else:
            print("  ⚠️ NEEDS IMPROVEMENT: Error > 8 BPM")

print(f"\n🎉 Fixed model training complete!")
print(f"📝 Use 'hr_model_fixed.joblib' in your application for accurate raw HR predictions")
