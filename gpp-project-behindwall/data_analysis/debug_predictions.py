import pandas as pd
import numpy as np
import joblib
import json
import os

# Load the trained model and data
BASE_DIR = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project-behindwall\data_analysis"
FINAL_STATS_FILE = os.path.join(BASE_DIR, "final_run_stats_new.csv")
MODEL_FILE = os.path.join(BASE_DIR, "hr_model.joblib")

print("🔍 Debugging Heart Rate Predictions...")
print("=" * 50)

# Load the final stats data
df = pd.read_csv(FINAL_STATS_FILE)
print(f"📊 Total runs in dataset: {len(df)}")

# Load the trained model
model = joblib.load(MODEL_FILE)
print("✅ Model loaded successfully")

# Define features
FEATURES = [
    "Avg_HR_clean", "Avg_RR_clean", "Avg_Range",
    "Range_SD", "HR_SD", "RR_SD",
    "HR_P2P", "RR_P2P", "Range_Slope", "SQI"
]

# Make predictions on all data
X = df[FEATURES].astype(float)
y_true = df["Final_Accurate_HR"].astype(float)
y_pred = model.predict(X)

# Calculate errors
errors = np.abs(y_pred - y_true)
mae = np.mean(errors)
rmse = np.sqrt(np.mean(errors**2))

print(f"\n📈 Prediction Performance:")
print(f"MAE: {mae:.2f} BPM")
print(f"RMSE: {rmse:.2f} BPM")
print(f"Max Error: {np.max(errors):.2f} BPM")
print(f"Min Error: {np.min(errors):.2f} BPM")

# Find worst predictions
worst_indices = np.argsort(errors)[-10:]  # Top 10 worst

print(f"\n🚨 Worst 10 Predictions:")
print("-" * 80)
print(f"{'Run':<5} {'True HR':<10} {'Pred HR':<10} {'Error':<10} {'Avg_HR_clean':<12} {'Config':<8}")
print("-" * 80)

for idx in worst_indices:
    run = df.iloc[idx]['Run']
    true_hr = y_true.iloc[idx]
    pred_hr = y_pred[idx]
    error = errors[idx]
    avg_hr_clean = df.iloc[idx]['Avg_HR_clean']
    config = df.iloc[idx].get('ConfigurationFile', 'N/A')
    
    print(f"{run:<5} {true_hr:<10.1f} {pred_hr:<10.1f} {error:<10.1f} {avg_hr_clean:<12.1f} {config:<8}")

# Analyze error distribution
print(f"\n📊 Error Distribution:")
print(f"0-5 BPM:   {np.sum(errors <= 5)} runs ({np.sum(errors <= 5)/len(errors)*100:.1f}%)")
print(f"5-10 BPM:  {np.sum((errors > 5) & (errors <= 10))} runs ({np.sum((errors > 5) & (errors <= 10))/len(errors)*100:.1f}%)")
print(f"10-15 BPM: {np.sum((errors > 10) & (errors <= 15))} runs ({np.sum((errors > 10) & (errors <= 15))/len(errors)*100:.1f}%)")
print(f"15-20 BPM: {np.sum((errors > 15) & (errors <= 20))} runs ({np.sum((errors > 15) & (errors <= 20))/len(errors)*100:.1f}%)")
print(f">20 BPM:   {np.sum(errors > 20)} runs ({np.sum(errors > 20)/len(errors)*100:.1f}%)")

# Check calibration offsets
print(f"\n🔧 Calibration Analysis:")
print(f"Final_Accurate_HR range: {y_true.min():.1f} - {y_true.max():.1f} BPM")
print(f"Avg_HR_clean range: {df['Avg_HR_clean'].min():.1f} - {df['Avg_HR_clean'].max():.1f} BPM")

# Calculate average offset
avg_offset = np.mean(y_true - df['Avg_HR_clean'])
print(f"Average calibration offset: {avg_offset:.2f} BPM")

# Check if there are different configurations
if 'ConfigurationFile' in df.columns:
    config_groups = df.groupby('ConfigurationFile')
    print(f"\n📋 Configuration Analysis:")
    for config, group in config_groups:
        config_errors = np.abs(model.predict(group[FEATURES]) - group["Final_Accurate_HR"])
        print(f"Config {config}: {len(group)} runs, MAE: {np.mean(config_errors):.2f} BPM")

# Feature correlation with error
print(f"\n🔗 Feature Correlation with Error:")
for feature in FEATURES:
    corr = np.abs(np.corrcoef(df[feature], errors)[0, 1])
    print(f"{feature:<15}: {corr:.3f}")

print(f"\n🎯 Recommendations:")
if mae > 15:
    print("❌ High error detected! Consider:")
    print("  1. Checking data quality and preprocessing")
    print("  2. Reviewing calibration offsets")
    print("  3. Collecting more diverse training data")
elif mae > 10:
    print("⚠️ Moderate error detected. Consider:")
    print("  1. Feature engineering improvements")
    print("  2. Hyperparameter tuning")
else:
    print("✅ Error is within acceptable range")
