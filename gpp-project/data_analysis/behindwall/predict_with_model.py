import os
import pandas as pd
import numpy as np
import joblib
import json
import sys

# Behind-Wall enhanced prediction model (14 features)
BASE_DIR = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project\data_analysis\behindwall"

FINAL_STATS_FILE = os.path.join(BASE_DIR, "final_run_stats_new.csv")

PARENT_DIR = os.path.dirname(BASE_DIR)  # data_analysis/

HR_MODEL_FILE = os.path.join(BASE_DIR, "hr_model_enhanced.joblib")   # enhanced model with 14 features
MODEL_HR = os.path.join(PARENT_DIR, "hr_class_model.joblib")
MODEL_RR = os.path.join(PARENT_DIR, "rr_class_model.joblib")
MODEL_ST = os.path.join(PARENT_DIR, "stress_class_model.joblib")

ENCODER_FILE = os.path.join(PARENT_DIR, "class_label_encodings.json")

FEATURES_REGRESSION = [
    "Avg_HR_clean", "Avg_RR_clean", "Avg_Range",
    "Range_SD", "HR_SD", "RR_SD",
    "HR_P2P", "RR_P2P", "SQI", "Range_Slope",
    "HeartWave_Std", "HeartWave_Range", "BreathWave_Std", "BreathWave_Range"
]

FEATURES_CLASSIFICATION = [
    "Avg_HR_clean", "Avg_RR_clean", "Avg_Range",
    "Range_SD", "HR_SD", "RR_SD",
    "HR_P2P", "RR_P2P", "SQI", "Range_Slope"
]


# --------------------------------------------------------
# SAFE CLEAN FUNCTION -> handles ANY shape
# --------------------------------------------------------
def clean_pred(v):
    """
    Takes ANY output and returns a clean integer.
    Handles:
      - integer
      - array([1])
      - array([[1]])
      - array([0., 1.])  <-- probability vector
      - list [1]
      - list [[1]]
      - list of probas
    """

    # 1. Direct integer
    if isinstance(v, (int, np.integer)):
        return int(v)

    # 2. If numpy array:
    if isinstance(v, np.ndarray):
        arr = v.flatten()

        # Probability vector? (example: [0. 1.])
        if arr.dtype.kind == "f" and len(arr) > 1:
            return int(np.argmax(arr))

        # Must be scalar after flatten
        if len(arr) != 1:
            raise ValueError(f"Cannot convert array of size {len(arr)} to scalar: {arr}")

        return int(arr[0])

    # 3. If list / tuple:
    if isinstance(v, (list, tuple)):
        if len(v) == 1:
            return clean_pred(v[0])

        # Probability list (example [0.1, 0.9])
        if all(isinstance(x, float) for x in v):
            return int(np.argmax(v))

        raise ValueError(f"List has more than 1 element: {v}")

    raise ValueError(f"Unknown prediction type: {type(v)}, value={v}")



# --------------------------------------------------------
# LOAD LABEL ENCODERS
# --------------------------------------------------------
def load_encoders():
    try:
        with open(ENCODER_FILE, 'r') as f:
            enc = json.load(f)
        
        fixed = {}
        
        for key in ["HR_Class", "RR_Class", "Stress_Class"]:
            mapping = enc[key]["mapping"]
            inv = {}
            
            # mapping is dict: label -> encoded_int
            for label, idx in mapping.items():
                # Handle both int and numpy integer types
                if hasattr(idx, "item"):
                    idx = int(idx.item())
                else:
                    idx = int(idx)
                inv[idx] = label
            
            fixed[key] = inv
        
        return fixed
    except FileNotFoundError:
        print(f"Error: Encoder file {ENCODER_FILE} not found")
        raise
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in encoder file: {e}")
        raise


# --------------------------------------------------------
# MAIN INFERENCE
# --------------------------------------------------------
def inference_from_latest_run():
    # Try to read current session data first
    VITAL_SIGNS_FILE = os.path.join(os.path.dirname(BASE_DIR), "..", "backend", "vital_signs_data_new.csv")
    
    if os.path.exists(VITAL_SIGNS_FILE):
        try:
            # Read current session data
            df_vital = pd.read_csv(VITAL_SIGNS_FILE, on_bad_lines="skip")
            
            # Filter for recent data (last 30 minutes)
            import datetime
            current_time = datetime.datetime.now()
            thirty_minutes_ago = current_time - datetime.timedelta(minutes=30)
            
            df_vital['Timestamp'] = pd.to_datetime(df_vital['Timestamp'], format='mixed', errors='coerce')
            recent_data = df_vital[df_vital['Timestamp'] > thirty_minutes_ago]
            
            if not recent_data.empty:
                # Calculate features from current session
                features = calculate_features_from_current_session(recent_data)
                X = features.reshape(1, -1)
            else:
                # Use latest data if no recent data found
                latest_data = df_vital.tail(20)  # Use last 20 readings
                if not latest_data.empty:
                    features = calculate_features_from_current_session(latest_data)
                    X = features.reshape(1, -1)
                else:
                    # Fallback to historical data
                    X = get_historical_features()
        except Exception as e:
            print(f"Error processing current session data: {e}")
            # Fallback to historical data
            X = get_historical_features()
    else:
        # Fallback to historical data
        X = get_historical_features()
    
    # Load models and predict
    reg_model = joblib.load(HR_MODEL_FILE)
    hr_pred = float(reg_model.predict(X)[0])
    
    # If we used current session data, we need to subtract the calibration offset
    # to get back to raw sensor values
    if os.path.exists(VITAL_SIGNS_FILE):
        try:
            df_vital = pd.read_csv(VITAL_SIGNS_FILE, on_bad_lines="skip")
            if 'Configuration' in df_vital.columns:
                config = int(df_vital['Configuration'].iloc[-1])  # Use latest config
                OFFSET_FILE_PATH = os.path.join(BASE_DIR, "calibration_offsets.json")
                if os.path.exists(OFFSET_FILE_PATH):
                    try:
                        with open(OFFSET_FILE_PATH, 'r') as f:
                            offsets = json.load(f)
                        CALIBRATION_OFFSET = offsets[f"offset_{config}"]
                        hr_pred = hr_pred - CALIBRATION_OFFSET  # Subtract calibration to get raw value
                    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
                        print(f"Warning: Could not adjust for calibration: {e}")
        except Exception as e:
            print(f"Warning: Could not adjust for calibration: {e}")
    
    enc = load_encoders()
    
    hr_model = joblib.load(MODEL_HR)
    rr_model = joblib.load(MODEL_RR)
    st_model = joblib.load(MODEL_ST)
    
    # Use only first 10 features for classification models
    X_classification = X[:, :10]  # Take first 10 features
    
    hr_code = clean_pred(hr_model.predict(X_classification))
    rr_code = clean_pred(rr_model.predict(X_classification))
    st_code = clean_pred(st_model.predict(X_classification))
    
    hr_label = enc["HR_Class"].get(hr_code, "Unknown")
    rr_label = enc["RR_Class"].get(rr_code, "Unknown")
    st_label = enc["Stress_Class"].get(st_code, "Unknown")
    
    return {
        "Predicted_HR": round(hr_pred, 2),
        "HR_Class": hr_label,
        "RR_Class": rr_label,
        "Stress_Class": st_label
    }


def calculate_features_from_current_session(df):
    """Calculate ML features from current session data"""
    # Extract the same features as in your training data
    hr_data = df['HeartRate_BPM'].astype(float)
    rr_data = df['RespirationRate_BPM'].astype(float)
    range_data = df['Range_m'].astype(float)
    
    # Load calibration offsets
    OFFSET_FILE_PATH = os.path.join(BASE_DIR, "calibration_offsets.json")
    if os.path.exists(OFFSET_FILE_PATH):
        try:
            with open(OFFSET_FILE_PATH, 'r') as f:
                offsets = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load calibration offsets: {e}")
            offsets = {"offset_0": 19.82, "offset_1": 32.41}
    else:
        offsets = {"offset_0": 19.82, "offset_1": 32.41}
    
    # Determine configuration from current data
    config = int(df['Configuration'].iloc[0]) if 'Configuration' in df.columns else 0
    CALIBRATION_OFFSET = offsets[f"offset_{config}"]
    
    # Apply calibration to match training data format
    # In training: Final_Accurate_HR = Avg_HR_clean + CALIBRATION_OFFSET
    # So we need to add the offset to current HR to match training format
    calibrated_hr = hr_data + CALIBRATION_OFFSET
    
    # Calculate waveform features if available
    heart_wave_std = 0
    heart_wave_range = 0
    breath_wave_std = 0
    breath_wave_range = 0
    
    if 'HeartWaveform' in df.columns:
        heart_waveforms = df['HeartWaveform'].values
        heart_wave_std = np.std(heart_waveforms) if len(heart_waveforms) > 1 else 0
        heart_wave_range = np.max(heart_waveforms) - np.min(heart_waveforms) if len(heart_waveforms) > 1 else 0
    
    if 'BreathWaveform' in df.columns:
        breath_waveforms = df['BreathWaveform'].values
        breath_wave_std = np.std(breath_waveforms) if len(breath_waveforms) > 1 else 0
        breath_wave_range = np.max(breath_waveforms) - np.min(breath_waveforms) if len(breath_waveforms) > 1 else 0
    
    features = [
        calibrated_hr.mean(),  # Avg_HR_clean (calibrated to match training)
        rr_data.mean(),  # Avg_RR_clean
        range_data.mean(),  # Avg_Range
        range_data.std() if len(range_data) > 1 else 0.1,  # Range_SD
        calibrated_hr.std() if len(calibrated_hr) > 1 else 5.0,  # HR_SD
        rr_data.std() if len(rr_data) > 1 else 1.0,  # RR_SD
        calibrated_hr.max() - calibrated_hr.min(),  # HR_P2P
        rr_data.max() - rr_data.min(),  # RR_P2P
        calculate_sqi(calibrated_hr),  # SQI
        calculate_range_slope(range_data),  # Range_Slope
        # Waveform features
        heart_wave_std,  # HeartWave_Std
        heart_wave_range,  # HeartWave_Range
        breath_wave_std,  # BreathWave_Std
        breath_wave_range  # BreathWave_Range
    ]
    
    return np.array(features)

def calculate_sqi(hr_data):
    """Calculate Signal Quality Index"""
    # Simple SQI calculation - adjust based on your needs
    if len(hr_data) < 2:
        return 0.0
    return 1.0 / (1.0 + hr_data.std())

def calculate_range_slope(range_data):
    """Calculate range slope over time"""
    if len(range_data) < 2:
        return 0.0
    return (range_data.iloc[-1] - range_data.iloc[0]) / len(range_data)

def get_historical_features():
    """Fallback to original method using historical data"""
    try:
        df = pd.read_csv(FINAL_STATS_FILE).drop_duplicates()
        if df.empty:
            # Return default features if no historical data (14 features for enhanced model)
            return np.array([70.0, 12.0, 0.5, 0.1, 5.0, 1.0, 10.0, 3.0, 15.0, 0.001, 0.0, 0.0, 0.0, 0.0]).reshape(1, -1)
        df = df.sort_values("Timestamp")
        latest = df.iloc[-1]
        
        # Get the 10 original features
        original_features = latest[FEATURES_CLASSIFICATION].astype(float).values
        
        # Add 4 default waveform features (0 since we don't have waveform data in historical)
        waveform_features = [0.0, 0.0, 0.0, 0.0]  # HeartWave_Std, HeartWave_Range, BreathWave_Std, BreathWave_Range
        
        # Combine all 14 features
        all_features = np.concatenate([original_features, waveform_features])
        
        return all_features.reshape(1, -1)
    except Exception as e:
        print(f"Error loading historical data: {e}")
        # Return default features if any error occurs (14 features for enhanced model)
        return np.array([70.0, 12.0, 0.5, 0.1, 5.0, 1.0, 10.0, 3.0, 15.0, 0.001, 0.0, 0.0, 0.0, 0.0]).reshape(1, -1)


# --------------------------------------------------------
# RUN
# --------------------------------------------------------
if __name__ == "__main__":
    try:
        out = inference_from_latest_run()
        print(json.dumps(out))
    except Exception as e:
        print("FATAL_ERROR:", str(e))
        raise
