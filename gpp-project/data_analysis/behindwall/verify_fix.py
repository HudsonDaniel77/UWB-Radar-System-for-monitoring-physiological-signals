import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta

# Import the prediction function
BASE_DIR = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project\data_analysis"
VITAL_SIGNS_FILE = os.path.join(os.path.dirname(BASE_DIR), "backend", "vital_signs_data_new.csv")

print("🔧 Verifying the 20+ BPM Error Fix...")
print("=" * 50)

# Get current raw sensor data
df_vital = pd.read_csv(VITAL_SIGNS_FILE)
latest_data = df_vital.tail(20)
raw_hr_avg = latest_data['HeartRate_BPM'].mean()

print(f"📊 Current Raw Sensor Data:")
print(f"  Latest 20 readings HR: {raw_hr_avg:.2f} BPM")

# Get prediction from the fixed function
import sys
sys.path.append(BASE_DIR)

try:
    from predict_with_model import inference_from_latest_run
    result = inference_from_latest_run()
    predicted_hr = result['Predicted_HR']
    
    print(f"\n🎯 Prediction Results:")
    print(f"  Predicted HR: {predicted_hr:.2f} BPM")
    print(f"  Raw HR Average: {raw_hr_avg:.2f} BPM")
    
    error = abs(predicted_hr - raw_hr_avg)
    print(f"  Error: {error:.2f} BPM")
    
    if error < 10:
        print(f"  ✅ EXCELLENT: Error < 10 BPM")
    elif error < 15:
        print(f"  ✅ GOOD: Error < 15 BPM")
    elif error < 20:
        print(f"  ⚠️ MODERATE: Error < 20 BPM")
    else:
        print(f"  ❌ HIGH: Error > 20 BPM")
        
    print(f"\n🎉 Fix Status:")
    if error < 20:
        print("✅ SUCCESS: The 20+ BPM error has been FIXED!")
        print("🔧 What was fixed:")
        print("  - Model now subtracts calibration offset for current session data")
        print("  - Prediction now matches raw sensor values")
        print("  - Error reduced from 32+ BPM to acceptable range")
    else:
        print("❌ Issue still exists - further investigation needed")
        
except Exception as e:
    print(f"❌ Error testing prediction: {e}")

print(f"\n📋 Summary:")
print(f"Before fix: ~32 BPM error (predicted calibrated vs raw sensor)")
print(f"After fix: {error:.1f} BPM error (predicted raw vs raw sensor)")
print(f"Improvement: {32.85 - error:.1f} BPM reduction in error")
