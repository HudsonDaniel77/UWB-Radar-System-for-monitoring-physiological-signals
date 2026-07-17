import pandas as pd
import numpy as np
import os
import time
from datetime import datetime

# Generate sample waveform data
def generate_sample_data():
    """Generate realistic sample waveform data"""
    
    # Read existing data to get the structure
    data_file = "vital_signs_data_new.csv"
    
    if os.path.exists(data_file):
        df = pd.read_csv(data_file)
    else:
        # Create new dataframe with correct structure
        df = pd.DataFrame(columns=[
            'Timestamp', 'User', 'Configuration', 'SessionTime',
            'HeartRate_BPM', 'RespirationRate_BPM', 'Range_m',
            'HeartWaveform', 'BreathWaveform', 'HeartRate_FFT', 'BreathRate_FFT'
        ])
    
    # Generate 50 new data points
    new_data = []
    base_time = datetime.now()
    
    for i in range(50):
        # Simulate realistic heart and respiration waveforms
        time_offset = i * 0.1
        
        # Heart waveform (simulated ECG-like pattern)
        heart_wave = 200 + 50 * np.sin(2 * np.pi * 1.2 * time_offset) + \
                    20 * np.sin(2 * np.pi * 2.4 * time_offset) + \
                    np.random.normal(0, 5)
        
        # Respiration waveform (slower sine wave)
        resp_wave = 100 + 30 * np.sin(2 * np.pi * 0.3 * time_offset) + \
                   np.random.normal(0, 3)
        
        # Vary heart rate slightly
        hr = 75 + 5 * np.sin(2 * np.pi * 0.1 * time_offset) + np.random.normal(0, 2)
        
        # Vary respiration rate slightly
        rr = 14 + 2 * np.sin(2 * np.pi * 0.05 * time_offset) + np.random.normal(0, 0.5)
        
        new_row = {
            'Timestamp': (base_time + pd.Timedelta(seconds=time_offset)).strftime('%Y-%m-%d %H:%M:%S'),
            'User': 'test@example.com',
            'Configuration': 0,
            'SessionTime': time_offset,
            'HeartRate_BPM': round(hr, 2),
            'RespirationRate_BPM': round(rr, 2),
            'Range_m': round(0.6 + 0.1 * np.sin(2 * np.pi * 0.2 * time_offset), 3),
            'HeartWaveform': round(heart_wave, 4),
            'BreathWaveform': round(resp_wave, 4),
            'HeartRate_FFT': round(hr, 2),
            'BreathRate_FFT': round(rr, 2)
        }
        
        new_data.append(new_row)
    
    # Append new data to dataframe
    new_df = pd.DataFrame(new_data)
    df_combined = pd.concat([df, new_df], ignore_index=True)
    
    # Save to CSV
    df_combined.to_csv(data_file, index=False)
    print(f"Generated {len(new_data)} sample data points")
    print(f"Total rows in {data_file}: {len(df_combined)}")

if __name__ == "__main__":
    generate_sample_data()
