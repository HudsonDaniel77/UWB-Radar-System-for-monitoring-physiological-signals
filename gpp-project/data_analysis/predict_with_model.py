import os
import pandas as pd
import numpy as np
import joblib
import json
import sys
import io
import glob
import warnings

# Suppress sklearn/xgboost feature name warnings
warnings.filterwarnings("ignore")

# UTF-8 encoding fix
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "backend"))

FINAL_STATS_FILE = os.path.join(BASE_DIR, "final_run_stats_new_tryingsomething.csv")
CLEAN_FILE = os.path.join(BASE_DIR, "cleaned_vital_signs_new_tryingsomething.csv")

HR_MODEL_FILE = os.path.join(BASE_DIR, "hr_model.joblib")   # regression model
MODEL_HR = os.path.join(BASE_DIR, "hr_class_model.joblib")
MODEL_RR = os.path.join(BASE_DIR, "rr_class_model.joblib")
MODEL_ST = os.path.join(BASE_DIR, "stress_class_model.joblib")

ENCODER_FILE = os.path.join(BASE_DIR, "class_label_encodings.json")

# Features for regression (matches train_hr_model.py: Range_Slope before SQI)
REG_FEATURES = [
    "Avg_HR_clean", "Avg_RR_clean", "Avg_Range",
    "Range_SD", "HR_SD", "RR_SD",
    "HR_P2P", "RR_P2P", "Range_Slope", "SQI"
]

# Features for classifiers (matches train_hr_classifier.py: SQI before Range_Slope)
CLS_FEATURES = [
    "Avg_HR_clean", "Avg_RR_clean", "Avg_Range",
    "Range_SD", "HR_SD", "RR_SD",
    "HR_P2P", "RR_P2P", "SQI", "Range_Slope"
]


# --------------------------------------------------------
# SAFE CLEAN FUNCTION -> handles ANY shape
# --------------------------------------------------------
def clean_pred(v):
    if isinstance(v, (int, np.integer)):
        return int(v)

    if isinstance(v, np.ndarray):
        arr = v.flatten()
        if arr.dtype.kind == "f" and len(arr) > 1:
            return int(np.argmax(arr))
        if len(arr) != 1:
            raise ValueError(f"Cannot convert array of size {len(arr)} to scalar: {arr}")
        return int(arr[0])

    if isinstance(v, (list, tuple)):
        if len(v) == 1:
            return clean_pred(v[0])
        if all(isinstance(x, float) for x in v):
            return int(np.argmax(v))
        raise ValueError(f"List has more than 1 element: {v}")

    raise ValueError(f"Unknown prediction type: {type(v)}, value={v}")


# --------------------------------------------------------
# LOAD LABEL ENCODERS
# --------------------------------------------------------
def load_encoders():
    default_enc = {
        "HR_Class": {0: "Elevated", 1: "High", 2: "Normal"},
        "RR_Class": {0: "Low", 1: "Normal"},
        "Stress_Class": {0: "Relaxed", 1: "Very High Stress"}
    }

    if not os.path.exists(ENCODER_FILE):
        return default_enc

    try:
        enc = json.load(open(ENCODER_FILE))
        fixed = {}
        for key in ["HR_Class", "RR_Class", "Stress_Class"]:
            if key not in enc:
                fixed[key] = default_enc.get(key, {})
                continue
            mapping = enc[key].get("mapping", {})
            inv = {}
            for label, idx in mapping.items():
                if isinstance(idx, list) and len(idx) == 1:
                    idx = idx[0]
                if hasattr(idx, "item"):
                    idx = int(idx.item())
                inv[int(idx)] = label
            fixed[key] = inv
        return fixed
    except Exception as e:
        return default_enc


def hr_category_from_hr(hr):
    if hr < 60:
        return "Low"
    elif hr <= 100:
        return "Normal"
    else:
        return "High"


# --------------------------------------------------------
# EXTRACT FEATURES FROM A RAW OR CLEANED SESSION DATAFRAME
# --------------------------------------------------------
def compute_features_from_df(df):
    hr_col = "Heart_clean" if "Heart_clean" in df.columns else "HeartRate_BPM"
    rr_col = "Resp_clean" if "Resp_clean" in df.columns else "RespirationRate_BPM"
    rg_col = "Range_clean" if "Range_clean" in df.columns else "Range_m"

    valid = df[df[hr_col].between(40, 180)].copy() if hr_col in df.columns else df.copy()
    if valid.empty:
        valid = df.copy()

    # Skip initial warm-up transient (first 25-30 frames)
    skip = min(30, len(valid) // 4)
    steady = valid.iloc[skip:].copy() if len(valid) > 20 else valid.copy()

    hr_series = pd.to_numeric(steady[hr_col], errors="coerce").dropna()
    rr_series = pd.to_numeric(steady[rr_col], errors="coerce").dropna()
    rg_series = pd.to_numeric(steady[rg_col], errors="coerce").dropna()

    # Harmonic de-aliasing if raw HeartRate_BPM was used
    if hr_col == "HeartRate_BPM" and not hr_series.empty:
        fundamental_wf = None
        if "HeartWaveform" in df.columns and df["HeartWaveform"].notna().sum() > 30:
            try:
                hw = df["HeartWaveform"].dropna().values
                fps = 20.0
                hw_detrend = hw - np.mean(hw)
                fft_vals = np.abs(np.fft.rfft(hw_detrend))
                freqs = np.fft.rfftfreq(len(hw_detrend), d=1.0/fps)
                mask = (freqs >= 0.8) & (freqs <= 2.0)
                if np.any(mask):
                    fundamental_wf = freqs[mask][np.argmax(fft_vals[mask])] * 60.0
            except Exception:
                fundamental_wf = None

        low_c = hr_series[(hr_series >= 50) & (hr_series <= 95)]
        high_c = hr_series[(hr_series >= 115) & (hr_series <= 150)]

        if len(low_c) > 0 and len(high_c) > 0:
            hr_series.loc[(hr_series >= 115) & (hr_series <= 150)] /= 2.0
        elif len(high_c) == len(hr_series) and (fundamental_wf is None or fundamental_wf < 95):
            hr_series /= 2.0
        elif fundamental_wf and 50 <= fundamental_wf <= 95:
            dm = (hr_series > 105) & ((hr_series / 2.0).between(fundamental_wf - 20, fundamental_wf + 20))
            hr_series.loc[dm] /= 2.0

    # For respiration rate: exclude initial 0.0 values from radar warm-up
    rr_non_zero = rr_series[rr_series >= 6.0]
    if not rr_non_zero.empty:
        avg_rr = float(rr_non_zero.mean())
        rr_sd = float(rr_non_zero.std()) if len(rr_non_zero) > 1 else 1.0
        rr_p2p = float(rr_non_zero.max() - rr_non_zero.min()) if len(rr_non_zero) > 1 else 2.0
    else:
        avg_rr = 14.0
        rr_sd = 1.0
        rr_p2p = 2.0

    avg_hr = float(hr_series.mean()) if not hr_series.empty else 72.0
    avg_rg = float(rg_series.mean()) if not rg_series.empty else 0.5

    range_sd = float(rg_series.std()) if len(rg_series) > 1 else 0.05
    hr_sd = float(hr_series.std()) if len(hr_series) > 1 else 3.5

    hr_p2p = float(hr_series.max() - hr_series.min()) if not hr_series.empty else 8.0

    arr = rg_series.values
    t = np.arange(len(arr))
    range_slope = float(np.polyfit(t, arr, 1)[0]) if len(arr) > 1 else 0.0
    sqi = 0.0 if (range_sd == 0 or np.isnan(range_sd)) else float(1.0 / range_sd)

    return {
        "Avg_HR_clean": avg_hr,
        "Avg_RR_clean": avg_rr,
        "Avg_Range": avg_rg,
        "Range_SD": range_sd,
        "HR_SD": hr_sd,
        "RR_SD": rr_sd,
        "HR_P2P": hr_p2p,
        "RR_P2P": rr_p2p,
        "Range_Slope": range_slope,
        "SQI": sqi
    }


# --------------------------------------------------------
# MAIN INFERENCE
# --------------------------------------------------------
def inference_from_latest_run(target_session_file=None):
    features_dict = None

    # 1. If explicit session file passed
    if target_session_file and os.path.exists(target_session_file):
        try:
            df_sess = pd.read_csv(target_session_file)
            if not df_sess.empty:
                features_dict = compute_features_from_df(df_sess)
        except Exception as e:
            print(f"⚠ Could not read passed session file: {e}")

    # 2. Check if CLEAN_FILE has recently cleaned session
    if features_dict is None and os.path.exists(CLEAN_FILE) and os.path.getsize(CLEAN_FILE) > 0:
        try:
            df_clean = pd.read_csv(CLEAN_FILE)
            if not df_clean.empty:
                features_dict = compute_features_from_df(df_clean.tail(150))
        except Exception:
            pass

    # 3. Check if FINAL_STATS_FILE exists and has rows
    if features_dict is None and os.path.exists(FINAL_STATS_FILE) and os.path.getsize(FINAL_STATS_FILE) > 0:
        try:
            df_stats = pd.read_csv(FINAL_STATS_FILE).drop_duplicates()
            if not df_stats.empty:
                latest = df_stats.iloc[-1]
                features_dict = {f: float(latest.get(f, 0.0)) for f in REG_FEATURES}
        except Exception as e:
            print(f"⚠ Error reading final stats: {e}")

    # 4. Fallback to default healthy vitals if no data available
    if features_dict is None:
        features_dict = {
            "Avg_HR_clean": 72.0, "Avg_RR_clean": 14.0, "Avg_Range": 0.5,
            "Range_SD": 0.05, "HR_SD": 4.0, "RR_SD": 1.0,
            "HR_P2P": 8.0, "RR_P2P": 2.0, "Range_Slope": 0.0, "SQI": 20.0
        }

    # Build DataFrames with exact column names to eliminate sklearn warnings
    df_reg = pd.DataFrame([features_dict])[REG_FEATURES]
    df_cls = pd.DataFrame([features_dict])[CLS_FEATURES]

    actual_sensor_hr = float(features_dict["Avg_HR_clean"])

    # Model inference: Regression
    if os.path.exists(HR_MODEL_FILE):
        try:
            reg_model = joblib.load(HR_MODEL_FILE)
            raw_model_pred = float(reg_model.predict(df_reg)[0])

            # The training data baked in a +19.82 offset (Final_Accurate_HR = Sensor_HR + offset).
            # When the true resting heart rate is ~65-80 BPM, adding 20 BPM artificially pushes it above 100 BPM.
            # If the raw prediction is inflated (> 90 BPM) while the actual cleaned sensor HR is normal (< 85 BPM),
            # adjust for the training offset:
            if raw_model_pred > 90 and actual_sensor_hr < 85:
                hr_pred = max(actual_sensor_hr, raw_model_pred - 19.82)
            else:
                hr_pred = raw_model_pred

            hr_pred = max(45.0, min(hr_pred, 180.0))
            hr_label = hr_category_from_hr(hr_pred)
        except Exception:
            hr_pred = actual_sensor_hr
            hr_label = hr_category_from_hr(hr_pred)
    else:
        hr_pred = actual_sensor_hr
        hr_label = hr_category_from_hr(hr_pred)

    # Encoders & Classifiers
    enc = load_encoders()

    # RR Class
    rr_val = features_dict.get("Avg_RR_clean", 14.0)
    rr_label = "Low" if rr_val < 12 else ("Fast" if rr_val > 20 else "Normal")
    if os.path.exists(MODEL_RR):
        try:
            rr_model = joblib.load(MODEL_RR)
            rr_code = clean_pred(rr_model.predict(df_cls))
            predicted_rr_label = enc.get("RR_Class", {}).get(rr_code, None)
            if predicted_rr_label:
                if predicted_rr_label == "Low" and 12 <= rr_val <= 20:
                    rr_label = "Normal"
                else:
                    rr_label = predicted_rr_label
        except Exception:
            pass

    # Stress Class
    hr_sd = features_dict.get("HR_SD", 4.0)
    avg_hr = features_dict.get("Avg_HR_clean", 72.0)
    cv = hr_sd / avg_hr if avg_hr > 0 else 0.05
    st_label = "Relaxed" if cv < 0.10 else ("Mild Stress" if cv < 0.18 else "High Stress")
    if os.path.exists(MODEL_ST):
        try:
            st_model = joblib.load(MODEL_ST)
            st_code = clean_pred(st_model.predict(df_cls))
            predicted_st_label = enc.get("Stress_Class", {}).get(st_code, None)
            if predicted_st_label:
                # If model predicts Very High Stress but heart rhythm is calm and resting (<85 BPM, CV < 0.12)
                if predicted_st_label == "Very High Stress" and cv < 0.12 and hr_pred < 85:
                    st_label = "Relaxed"
                else:
                    st_label = predicted_st_label
        except Exception:
            pass

    return {
        "Predicted_HR": round(hr_pred, 2),
        "HR_Class": hr_label,
        "RR_Class": rr_label,
        "Stress_Class": st_label
    }


# --------------------------------------------------------
# RUN
# --------------------------------------------------------
if __name__ == "__main__":
    try:
        session_arg = sys.argv[1] if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else None
        out = inference_from_latest_run(session_arg)
        print(json.dumps(out))
        sys.exit(0)
    except Exception as e:
        error_output = {
            "Predicted_HR": 72.0,
            "HR_Class": "Normal",
            "RR_Class": "Normal",
            "Stress_Class": "Relaxed",
            "error": str(e)[:100]
        }
        print(json.dumps(error_output))
        sys.exit(0)
