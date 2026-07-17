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
CLEANED_DATA_FILE = os.path.join(BASE_DIR, "data_analysis", "cleaned_vital_signs_new.csv")
MODEL_FILE = os.path.join(BASE_DIR, "data_analysis", "hr_model.joblib")
ENHANCED_MODEL_FILE = os.path.join(BASE_DIR, "data_analysis", "hr_model_enhanced.joblib")
METRICS_FILE = os.path.join(BASE_DIR, "data_analysis", "hr_model_enhanced_metrics.json")

print("🚀 Enhanced Model Training - Adding Waveform Features")
print("=" * 60)

# Load processed data
df_processed = pd.read_csv(DATA_FILE)
print(f"📊 Loaded processed data: {len(df_processed)} runs")

# Load raw data with waveforms
df_raw = pd.read_csv(CLEANED_DATA_FILE)
print(f"📊 Loaded raw data with waveforms: {len(df_raw)} rows")

# Create enhanced dataset by adding waveform features
# We'll extract waveform statistics from raw data and add to processed data

enhanced_data = []

for idx, row in df_processed.iterrows():
    # Get corresponding raw data for this run
    date_part = row['Timestamp'].split()[0]  # Get date part
    run_data = df_raw[df_raw['Timestamp'].str.contains(date_part, na=False)]
    
    if len(run_data) > 0:
        # Extract waveform statistics
        heart_waveforms = run_data['HeartWaveform'].values
        breath_waveforms = run_data['BreathWaveform'].values
        
        # Calculate waveform features
        heart_wave_std = np.std(heart_waveforms) if len(heart_waveforms) > 1 else 0
        heart_wave_range = np.max(heart_waveforms) - np.min(heart_waveforms) if len(heart_waveforms) > 1 else 0
        breath_wave_std = np.std(breath_waveforms) if len(breath_waveforms) > 1 else 0
        breath_wave_range = np.max(breath_waveforms) - np.min(breath_waveforms) if len(breath_waveforms) > 1 else 0
        
        # Create enhanced row
        enhanced_row = row.copy()
        enhanced_row['HeartWave_Std'] = heart_wave_std
        enhanced_row['HeartWave_Range'] = heart_wave_range
        enhanced_row['BreathWave_Std'] = breath_wave_std
        enhanced_row['BreathWave_Range'] = breath_wave_range
        
        enhanced_data.append(enhanced_row)
    else:
        # If no matching raw data, add row with 0 waveform features
        enhanced_row = row.copy()
        enhanced_row['HeartWave_Std'] = 0
        enhanced_row['HeartWave_Range'] = 0
        enhanced_row['BreathWave_Std'] = 0
        enhanced_row['BreathWave_Range'] = 0
        
        enhanced_data.append(enhanced_row)

# Create enhanced dataframe
df_enhanced = pd.DataFrame(enhanced_data)
print(f"📊 Created enhanced dataset: {len(df_enhanced)} runs")

# Enhanced features
feature_cols = [
    'Avg_HR_clean', 'Avg_RR_clean', 'Avg_Range', 'Range_SD', 
    'HR_SD', 'RR_SD', 'HR_P2P', 'RR_P2P', 'Range_Slope', 'SQI',
    # New waveform features
    'HeartWave_Std', 'HeartWave_Range', 'BreathWave_Std', 'BreathWave_Range'
]

X = df_enhanced[feature_cols]
y_raw = df_enhanced['Avg_HR_clean']  # Raw HR target

print(f"📊 Enhanced Features: {len(feature_cols)} total")
print(f"  Original features: 10")
print(f"  Waveform features: 4")

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y_raw, test_size=0.2, random_state=42)

print(f"\n🎯 Training Enhanced Model:")
print(f"  Training samples: {len(X_train)}")
print(f"  Test samples: {len(X_test)}")

# Train enhanced model
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

print(f"\n📈 Enhanced Model Performance:")
print(f"  MAE: {mae:.2f} BPM")
print(f"  RMSE: {rmse:.2f} BPM")
print(f"  R²: {r2:.3f}")

# Performance assessment
if mae <= 1:
    print("  🏆 PERFECT: MAE ≤ 1 BPM")
elif mae <= 2:
    print("  🏆 OUTSTANDING: MAE ≤ 2 BPM")
elif mae <= 5:
    print("  ✅ EXCELLENT: MAE ≤ 5 BPM")
else:
    print("  ⚠️ NEEDS IMPROVEMENT: MAE > 5 BPM")

# Save enhanced model
joblib.dump(model, ENHANCED_MODEL_FILE)
print(f"\n💾 Enhanced model saved as: hr_model_enhanced.joblib")

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
    'chosen_model': 'XGBoost Enhanced',
    'includes_waveforms': True
}

with open(METRICS_FILE, 'w') as f:
    json.dump(metrics, f, indent=2)

print(f"📊 Metrics saved as: hr_model_enhanced_metrics.json")

# Feature importance analysis
print(f"\n🎯 Top 10 Feature Importances:")
importances = model.feature_importances_
indices = np.argsort(importances)[::-1]

for i in range(min(10, len(feature_cols))):
    idx = indices[i]
    print(f"  {i+1}. {feature_cols[idx]}: {importances[idx]:.4f}")

print(f"\n🎉 Enhanced model training complete!")
print(f"📝 Use 'hr_model_enhanced.joblib' for improved predictions with waveform features")
