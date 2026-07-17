"""
Train a machine learning model to predict Heart Rate (HR)
from final_run_stats_new.csv using XGBoost.
"""

import os
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib
import json
import warnings

warnings.filterwarnings("ignore")

# ----------------------------------------------------
# CONFIG
# ----------------------------------------------------
BASE_DIR = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project-behindwall\data_analysis"

FINAL_STATS_FILE = os.path.join(BASE_DIR, "final_run_stats_new.csv")
MODEL_OUTPUT_PATH = os.path.join(BASE_DIR, "hr_model.joblib")
METRICS_OUTPUT_PATH = os.path.join(BASE_DIR, "hr_model_metrics.json")

# ORDER MUST MATCH calibration.py
FEATURES = [
    "Avg_HR_clean", "Avg_RR_clean", "Avg_Range",
    "Range_SD", "HR_SD", "RR_SD",
    "HR_P2P", "RR_P2P",
    "Range_Slope", "SQI"
]

TARGET = "Final_Accurate_HR"
RANDOM_STATE = 42

# ----------------------------------------------------
# TRAINING FUNCTION
# ----------------------------------------------------
def train_hr_model():
    print("📌 Loading dataset:", FINAL_STATS_FILE)
    df = pd.read_csv(FINAL_STATS_FILE)

    # Remove duplicate runs
    df = df.drop_duplicates()

    # Make sure numeric fields are numeric
    df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce")
    for f in FEATURES:
        df[f] = pd.to_numeric(df[f], errors="coerce")

    # Remove missing target rows
    df = df.dropna(subset=[TARGET])
    df = df.dropna(subset=FEATURES)

    X = df[FEATURES]
    y = df[TARGET]

    if len(X) < 10:
        print("⚠ WARNING: Dataset is small. Model accuracy may be unstable.")

    # Split dataset
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=RANDOM_STATE
    )

    # Pipeline
    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", XGBRegressor(
            n_estimators=350,
            learning_rate=0.04,
            max_depth=5,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.0,
            objective="reg:squarederror",
            random_state=RANDOM_STATE
        ))
    ])

    print("🚀 Training XGBoost model...")
    pipeline.fit(X_train, y_train)

    # Predictions
    y_pred = pipeline.predict(X_test)

    # Metrics
    mae = float(mean_absolute_error(y_test, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    r2 = float(r2_score(y_test, y_pred))

    # Extract feature importances
    model = pipeline.named_steps["model"]
    importances = model.feature_importances_

    feature_importance_dict = {
        FEATURES[i]: float(importances[i])
        for i in range(len(FEATURES))
    }

    metrics = {
        "MAE": mae,
        "RMSE": rmse,
        "R2": r2,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "features": FEATURES,
        "feature_importances": feature_importance_dict,
        "chosen_model": "XGBoost"
    }

    # Show performance
    print("\n📊 MODEL PERFORMANCE:")
    print(json.dumps(metrics, indent=2))

    # Save model
    joblib.dump(pipeline, MODEL_OUTPUT_PATH)
    print("✔ Model saved at:", MODEL_OUTPUT_PATH)

    # Save metrics
    with open(METRICS_OUTPUT_PATH, "w") as f:
        json.dump(metrics, f, indent=2)
    print("✔ Metrics saved at:", METRICS_OUTPUT_PATH)

    return pipeline


if __name__ == "__main__":
    train_hr_model()
