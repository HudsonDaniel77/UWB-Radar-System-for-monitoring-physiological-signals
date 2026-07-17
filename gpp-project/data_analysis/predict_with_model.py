import os
import pandas as pd
import numpy as np
import joblib
import json
import sys
import io

# UTF-8 encoding fix
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FINAL_STATS_FILE = os.path.join(BASE_DIR, "final_run_stats_new_tryingsomething.csv")

HR_MODEL_FILE = os.path.join(BASE_DIR, "hr_model.joblib")   # regression model
MODEL_HR = os.path.join(BASE_DIR, "hr_class_model.joblib")
MODEL_RR = os.path.join(BASE_DIR, "rr_class_model.joblib")
MODEL_ST = os.path.join(BASE_DIR, "stress_class_model.joblib")

ENCODER_FILE = os.path.join(BASE_DIR, "class_label_encodings.json")

FEATURES = [
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

    # 1️⃣ Direct integer
    if isinstance(v, (int, np.integer)):
        return int(v)

    # 2️⃣ If numpy array:
    if isinstance(v, np.ndarray):
        arr = v.flatten()

        # Probability vector? (example: [0. 1.])
        if arr.dtype.kind == "f" and len(arr) > 1:
            return int(np.argmax(arr))

        # Must be scalar after flatten
        if len(arr) != 1:
            raise ValueError(f"Cannot convert array of size {len(arr)} to scalar: {arr}")

        return int(arr[0])

    # 3️⃣ If list / tuple:
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
    """Load encoders with fallback to defaults if file doesn't exist."""
    default_enc = {
        "HR_Class": {},
        "RR_Class": {},
        "Stress_Class": {}
    }
    
    if not os.path.exists(ENCODER_FILE):
        print("⚠ Encoder file not found, using empty encoders")
        return default_enc
    
    try:
        enc = json.load(open(ENCODER_FILE))
    except Exception as e:
        print(f"⚠ Failed to load encoders: {e}")
        return default_enc

    fixed = {}

    for key in ["HR_Class", "RR_Class", "Stress_Class"]:
        if key not in enc:
            fixed[key] = {}
            continue
            
        mapping = enc[key].get("mapping", {})
        inv = {}

        # mapping is dict: label -> encoded_int
        for label, idx in mapping.items():
            if isinstance(idx, list) and len(idx) == 1:
                idx = idx[0]
            if hasattr(idx, "item"):
                idx = int(idx.item())
            inv[int(idx)] = label

        fixed[key] = inv

    return fixed


# --------------------------------------------------------
# MAIN INFERENCE
# --------------------------------------------------------
def hr_category_from_hr(hr):
    if hr < 60:
        return "Low"
    elif hr <= 100:
        return "Normal"
    else:
        return "High"

def inference_from_latest_run():
    """Load latest stats and make predictions with error handling."""
    
    if not os.path.exists(FINAL_STATS_FILE):
        print("ℹ No final stats file yet")
        return {
            "Predicted_HR": None,
            "HR_Class": "N/A",
            "RR_Class": "N/A",
            "Stress_Class": "N/A",
            "note": "No data available"
        }
    
    df = pd.read_csv(FINAL_STATS_FILE).drop_duplicates()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df = df.sort_values("Timestamp")
    
    if df.empty:
        print("ℹ No rows in final stats")
        return {
            "Predicted_HR": None,
            "HR_Class": "N/A",
            "RR_Class": "N/A",
            "Stress_Class": "N/A",
            "note": "No data available"
        }
    
    latest = df.iloc[-1]
    X = latest[FEATURES].astype(float).values.reshape(1, -1)

    # Regression - with fallback if model fails
    if not os.path.exists(HR_MODEL_FILE):
        print("⚠ HR model not found, using default")
        hr_pred = 75.0
        hr_label = "Normal"
    else:
        try:
            reg_model = joblib.load(HR_MODEL_FILE)
            hr_pred = float(reg_model.predict(X)[0])
            hr_label = hr_category_from_hr(hr_pred)
        except Exception as e:
            print(f"⚠ HR prediction failed: {str(e)[:100]}, using default")
            hr_pred = 75.0
            hr_label = "Normal"

    # Encoders
    try:
        enc = load_encoders()
    except Exception as e:
        print(f"⚠ Encoder loading failed: {str(e)[:100]}, using default")
        enc = {"RR_Class": {}, "Stress_Class": {}}

    # Classifier models - with fallbacks
    rr_label = "Normal"
    if os.path.exists(MODEL_RR):
        try:
            rr_model = joblib.load(MODEL_RR)
            rr_code = clean_pred(rr_model.predict(X))
            rr_label = enc["RR_Class"].get(rr_code, "Normal")
        except Exception as e:
            print(f"⚠ RR prediction failed: {str(e)[:100]}, using default")
            rr_label = "Normal"

    st_label = "Normal"
    if os.path.exists(MODEL_ST):
        try:
            st_model = joblib.load(MODEL_ST)
            st_code = clean_pred(st_model.predict(X))
            st_label = enc["Stress_Class"].get(st_code, "Normal")
        except Exception as e:
            print(f"⚠ Stress prediction failed: {str(e)[:100]}, using default")
            st_label = "Normal"

    return {
        "Predicted_HR": round(hr_pred, 2) if hr_pred else None,
        "HR_Class": hr_label,
        "RR_Class": rr_label,
        "Stress_Class": st_label
    }


# --------------------------------------------------------
# RUN
# --------------------------------------------------------
if __name__ == "__main__":
    try:
        out = inference_from_latest_run()
        print(json.dumps(out))
        exit(0)
    except Exception as e:
        print("⚠ ERROR:", str(e)[:200])
        # Still output valid JSON with error defaults
        error_output = {
            "Predicted_HR": None,
            "HR_Class": "N/A",
            "RR_Class": "N/A",
            "Stress_Class": "N/A",
            "error": str(e)[:100]
        }
        print(json.dumps(error_output))
        exit(0)  # Exit successfully even on error - pipeline continues
