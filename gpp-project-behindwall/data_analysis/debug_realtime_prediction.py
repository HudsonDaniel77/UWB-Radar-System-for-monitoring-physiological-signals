import pandas as pd
import numpy as np
import joblib
import json
import os
from datetime import datetime, timedelta

# Load the prediction script functions
BASE_DIR = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project-behindwall\data_analysis"
FINAL_STATS_FILE = os.path.join(BASE_DIR, "final_run_stats_new.csv")
VITAL_SIGNS_FILE = os.path.join(os.path.dirname(BASE_DIR), "backend", "vital_signs_data_new.csv")
MODEL_FILE = os.path.join(BASE_DIR, "hr_model.joblib")

print("🔍 Debugging Real-time Prediction...")
print("=" * 50)

# Check current sensor data
if os.path.exists(VITAL_SIGNS_FILE):
    df_vital = pd.read_csv(VITAL_SIGNS_FILE)
    print(f"📊 Current sensor data: {len(df_vital)} rows")
    
    # Check recent data (last 5 minutes)
    df_vital['Timestamp'] = pd.to_datetime(df_vital['Timestamp'], format='mixed', errors='coerce')
    current_time = datetime.now()
    five_minutes_ago = current_time - timedelta(minutes=5)
    recent_data = df_vital[df_vital['Timestamp'] > five_minutes_ago]
    
    print(f"🕐 Recent data (last 5 min): {len(recent_data)} rows")
    
    if not recent_data.empty:
        print(f"📈 Recent HR range: {recent_data['HeartRate_BPM'].min():.1f} - {recent_data['HeartRate_BPM'].max():.1f} BPM")
        print(f"📈 Recent RR range: {recent_data['RespirationRate_BPM'].min():.1f} - {recent_data['RespirationRate_BPM'].max():.1f} BPM")
        print(f"📈 Recent Range: {recent_data['Range_m'].min():.3f} - {recent_data['Range_m'].max():.3f} m")
        
        # Calculate features from current session
        hr_data = recent_data['HeartRate_BPM'].astype(float)
        rr_data = recent_data['RespirationRate_BPM'].astype(float)
        range_data = recent_data['Range_m'].astype(float)
        
        # Load calibration offsets
        OFFSET_FILE = os.path.join(BASE_DIR, "calibration_offsets.json")
        if os.path.exists(OFFSET_FILE):
            offsets = json.load(open(OFFSET_FILE))
        else:
            offsets = {"offset_0": 19.82, "offset_1": 32.41}
        
        # Determine configuration from current data
        config = int(recent_data['Configuration'].iloc[0]) if 'Configuration' in recent_data.columns else 0
        CALIBRATION_OFFSET = offsets[f"offset_{config}"]
        
        # Apply calibration to match training data format
        calibrated_hr = hr_data + CALIBRATION_OFFSET
        
        current_features = [
            calibrated_hr.mean(),  # Avg_HR_clean (calibrated to match training)
            rr_data.mean(),  # Avg_RR_clean
            range_data.mean(),  # Avg_Range
            range_data.std() if len(range_data) > 1 else 0.1,  # Range_SD
            calibrated_hr.std() if len(calibrated_hr) > 1 else 5.0,  # HR_SD
            rr_data.std() if len(rr_data) > 1 else 1.0,  # RR_SD
            calibrated_hr.max() - calibrated_hr.min(),  # HR_P2P
            rr_data.max() - rr_data.min(),  # RR_P2P
            1.0 / (1.0 + calibrated_hr.std()) if len(calibrated_hr) > 1 else 15.0,  # SQI
            (range_data.iloc[-1] - range_data.iloc[0]) / len(range_data) if len(range_data) > 1 else 0.001  # Range_Slope
        ]
        
        print(f"\n🔧 Current Session Features:")
        feature_names = ["Avg_HR_clean", "Avg_RR_clean", "Avg_Range", "Range_SD", "HR_SD", "RR_SD", "HR_P2P", "RR_P2P", "SQI", "Range_Slope"]
        for name, value in zip(feature_names, current_features):
            print(f"  {name:<15}: {value:.3f}")
        
        print(f"\n🔧 Calibration Info:")
        print(f"  Configuration: {config}")
        print(f"  Calibration Offset: {CALIBRATION_OFFSET:.2f} BPM")
        print(f"  Raw HR Avg: {hr_data.mean():.2f} BPM")
        print(f"  Calibrated HR Avg: {calibrated_hr.mean():.2f} BPM")
        
        # Load model and predict
        model = joblib.load(MODEL_FILE)
        current_prediction = float(model.predict(np.array(current_features).reshape(1, -1))[0])
        print(f"\n🎯 Current Session Prediction: {current_prediction:.2f} BPM")
        
        # Compare with calibrated average
        avg_calibrated_hr = calibrated_hr.mean()
        print(f"📊 Calibrated Data Average HR: {avg_calibrated_hr:.2f} BPM")
        print(f"📊 Prediction Error: {abs(current_prediction - avg_calibrated_hr):.2f} BPM")
        
        # Also compare with raw data
        avg_raw_hr = hr_data.mean()
        print(f"📊 Raw Data Average HR: {avg_raw_hr:.2f} BPM")
        print(f"📊 Raw vs Prediction Error: {abs(current_prediction - avg_raw_hr):.2f} BPM")
        
    else:
        print("⚠️ No recent data found (last 5 minutes)")
        
        # Check latest data anyway
        if not df_vital.empty:
            latest_data = df_vital.tail(10)
            print(f"📊 Latest 10 readings:")
            print(f"  HR: {latest_data['HeartRate_BPM'].mean():.1f} ± {latest_data['HeartRate_BPM'].std():.1f} BPM")
            print(f"  RR: {latest_data['RespirationRate_BPM'].mean():.1f} ± {latest_data['RespirationRate_BPM'].std():.1f} BPM")
            print(f"  Range: {latest_data['Range_m'].mean():.3f} ± {latest_data['Range_m'].std():.3f} m")
else:
    print("❌ No sensor data file found")

# Check what the prediction script is actually using
print(f"\n🔍 Checking what prediction script uses...")

# Load historical data
try:
    df_hist = pd.read_csv(FINAL_STATS_FILE)
    if not df_hist.empty:
        latest_hist = df_hist.iloc[-1]
        print(f"📊 Historical Latest Run:")
        print(f"  Run #{latest_hist['Run']}")
        print(f"  True HR: {latest_hist['Final_Accurate_HR']:.1f} BPM")
        print(f"  Avg_HR_clean: {latest_hist['Avg_HR_clean']:.1f} BPM")
        print(f"  Timestamp: {latest_hist['Timestamp']}")
        
        # Calculate how old this data is
        try:
            hist_time = pd.to_datetime(latest_hist['Timestamp'], format='mixed')
            age_minutes = (current_time - hist_time).total_seconds() / 60
            print(f"  Age: {age_minutes:.1f} minutes ago")
        except:
            print("  Age: Unknown")
            
except Exception as e:
    print(f"❌ Error loading historical data: {e}")

# Test the actual prediction function
print(f"\n🧪 Testing actual prediction function...")

# Import the prediction function
import sys
sys.path.append(BASE_DIR)

try:
    from predict_with_model import inference_from_latest_run
    result = inference_from_latest_run()
    print(f"✅ Prediction function result: {result}")
except Exception as e:
    print(f"❌ Error in prediction function: {e}")

print(f"\n🎯 Potential Issues:")
print("1. Using old historical data instead of current session")
print("2. Calibration offset mismatch")
print("3. Feature calculation differences")
print("4. Data preprocessing inconsistencies")
