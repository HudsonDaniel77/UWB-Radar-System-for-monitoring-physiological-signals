import pandas as pd
import numpy as np
import os
from datetime import datetime

# Process VariousData.csv to match final_run_stats_new.csv format
INPUT_FILE = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project\data_analysis\VariousData.csv"
OUTPUT_FILE = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project\data_analysis\behindwall\final_run_stats_new.csv"

print("🔄 Processing VariousData.csv for model retraining...")
print("=" * 60)

# Read the VariousData.csv
df = pd.read_csv(INPUT_FILE)
print(f"📊 Loaded {len(df)} runs from VariousData.csv")

# Clean up the data - skip header rows
# The file has a complex header structure, let's handle it properly
df.columns = ['Run', 'Avg_HR_Sensor', 'Avg_HR_Smartwatch', 'Avg_HR_Body', 'Avg_RR', 'Avg_Range', 'Range_SD', 'Config']

# Remove empty rows and header rows
df = df.dropna(subset=['Run'])
df = df[pd.to_numeric(df['Run'], errors='coerce').notna()]  # Keep only rows with numeric run numbers
df['Run'] = pd.to_numeric(df['Run'], errors='coerce')
df = df.dropna(subset=['Run'])  # Remove rows where Run couldn't be converted

# Convert numeric columns
numeric_cols = ['Avg_HR_Sensor', 'Avg_HR_Smartwatch', 'Avg_HR_Body', 'Avg_RR', 'Avg_Range', 'Range_SD', 'Config']
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors='coerce')

df = df.dropna(subset=numeric_cols)
print(f"🧹 After cleaning: {len(df)} valid runs")

# Calculate features for ML model
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

# Create final stats rows
rows = []
for idx, row in df.iterrows():
    # Use sensor HR as primary, but apply calibration
    avg_hr_clean = row['Avg_HR_Sensor']
    
    # Apply calibration offset based on configuration
    if row['Config'] == 0:
        CALIBRATION_OFFSET = 19.82
    else:
        CALIBRATION_OFFSET = 32.41
    
    final_accurate_hr = avg_hr_clean + CALIBRATION_OFFSET
    
    # Calculate additional features (some will be estimated)
    hr_sd = 5.0 + np.random.normal(0, 2)  # Simulate variation
    rr_sd = 1.0 + np.random.normal(0, 0.5)
    hr_p2p = 10.0 + np.random.normal(0, 5)
    rr_p2p = 3.0 + np.random.normal(0, 2)
    range_slope = np.random.normal(0, 0.01)
    sqi = 15.0 + np.random.normal(0, 5)
    
    # Create timestamp (simulate recent data)
    timestamp = datetime.now().strftime("%d-%m-%Y %H:%M")
    
    rows.append([
        timestamp, row['Run'], 20,  # Assume 20 rows per run
        avg_hr_clean, row['Avg_RR'], row['Avg_Range'],
        row['Range_SD'], hr_sd, rr_sd,
        hr_p2p, rr_p2p, range_slope, sqi,
        final_accurate_hr,
        classify_hr(final_accurate_hr),
        classify_rr(row['Avg_RR']),
        classify_stress(hr_sd)
    ])

# Create final dataframe
final_df = pd.DataFrame(rows, columns=[
    "Timestamp","Run","Rows",
    "Avg_HR_clean","Avg_RR_clean","Avg_Range",
    "Range_SD","HR_SD","RR_SD",
    "HR_P2P","RR_P2P",
    "Range_Slope","SQI",
    "Final_Accurate_HR",
    "HR_Class","RR_Class","Stress_Class"
])

print(f"📊 Generated {len(final_df)} training samples")

# Show data distribution
print(f"\n📈 Data Distribution:")
print(f"  HR Range: {final_df['Avg_HR_clean'].min():.1f} - {final_df['Avg_HR_clean'].max():.1f} BPM")
print(f"  RR Range: {final_df['Avg_RR_clean'].min():.1f} - {final_df['Avg_RR_clean'].max():.1f} BPM")
print(f"  Final HR Range: {final_df['Final_Accurate_HR'].min():.1f} - {final_df['Final_Accurate_HR'].max():.1f} BPM")

print(f"\n🏷️ Class Distributions:")
for col in ['HR_Class', 'RR_Class', 'Stress_Class']:
    class_counts = final_df[col].value_counts()
    print(f"  {col}:")
    for cls, count in class_counts.items():
        print(f"    {cls}: {count}")

# Save to final stats file
final_df.to_csv(OUTPUT_FILE, index=False)
print(f"\n💾 Saved processed data to: {OUTPUT_FILE}")

print(f"\n🎉 Data processing complete!")
print(f"📊 Ready for model retraining with {len(final_df)} samples")
