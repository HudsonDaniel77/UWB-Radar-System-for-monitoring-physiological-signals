import os
import json
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np

from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from xgboost import XGBClassifier
import joblib

# ==========================================================
# PATHS
# ==========================================================
BASE_DIR = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project-behindwall\data_analysis"

CSV = os.path.join(BASE_DIR, "final_run_stats_new.csv")
ENCODER_FILE = os.path.join(BASE_DIR, "class_label_encodings.json")

MODEL_HR = os.path.join(BASE_DIR, "hr_class_model.joblib")
MODEL_RR = os.path.join(BASE_DIR, "rr_class_model.joblib")
MODEL_STRESS = os.path.join(BASE_DIR, "stress_class_model.joblib")

METRIC_HR = os.path.join(BASE_DIR, "hr_class_metrics.json")
METRIC_RR = os.path.join(BASE_DIR, "rr_class_metrics.json")
METRIC_STRESS = os.path.join(BASE_DIR, "stress_class_metrics.json")

# ==========================================================
# FEATURES & TARGETS
# ==========================================================
FEATURES = [
    "Avg_HR_clean", "Avg_RR_clean", "Avg_Range",
    "Range_SD", "HR_SD", "RR_SD",
    "HR_P2P", "RR_P2P", "SQI", "Range_Slope"
]

TARGETS = ["HR_Class", "RR_Class", "Stress_Class"]


# ==========================================================
# LOAD + CLEAN
# ==========================================================
def load_and_clean():
    df = pd.read_csv(CSV)
    df = df.drop_duplicates()
    df = df.dropna(subset=TARGETS)

    for f in FEATURES:
        df[f] = pd.to_numeric(df[f], errors="coerce")

    df = df.dropna(subset=FEATURES)
    return df


# ==========================================================
# TRAIN SINGLE CLASSIFIER
# ==========================================================
def train_single_classifier(df, target, save_model, save_metrics, encoders):

    print("\n================================")
    print(f"🚀 Training model for {target}")
    print("================================")

    X = df[FEATURES]
    y = df[target]

    # Encode labels
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    encoders[target] = {
        "classes": le.classes_.tolist(),
        "mapping": {cls: int(idx) for cls, idx in zip(le.classes_, le.transform(le.classes_))}
    }

    # Split
    # Check if we have enough samples for stratified splitting
    class_counts = pd.Series(y_encoded).value_counts()
    min_class_count = class_counts.min()
    
    if len(class_counts) < 2:
        print(f"⚠ Warning: Only {len(class_counts)} class(es) found. Skipping training for {target}.")
        return
    
    if min_class_count < 2:
        print(f"⚠ Warning: Class {class_counts.idxmin()} has only {min_class_count} sample(s). Using random split instead of stratified.")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_encoded,
            test_size=0.25,
            random_state=42
        )
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_encoded,
            test_size=0.25,
            random_state=42,
            stratify=y_encoded
        )
    
    # Check if we have multiple classes in both train and test sets
    train_classes = set(y_train)
    test_classes = set(y_test)
    
    if len(train_classes) < 2 or len(test_classes) < 2:
        print(f"⚠ Warning: Not enough class diversity in splits. Skipping training for {target}.")
        return

    # Build pipeline
    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("clf", XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="multi:softprob",
            num_class=len(le.classes_),
            eval_metric="mlogloss",
            random_state=42
        ))
    ])

    # Train model
    model.fit(X_train, y_train)

    # ==========================================
    # CORRECT PREDICT_PROBA EXTRACTION
    # ==========================================
    X_test_processed = model.named_steps["imputer"].transform(X_test)
    X_test_processed = model.named_steps["scale"].transform(X_test_processed)

    clf = model.named_steps["clf"]
    probas = clf.predict_proba(X_test_processed)

    y_pred = np.argmax(probas, axis=1)

    # Classification metrics
    rep = classification_report(
        y_test, y_pred,
        output_dict=True,
        zero_division=0
    )

    # Save model
    joblib.dump(model, save_model)
    print(f"✔ Saved model → {save_model}")

    # Save metrics
    with open(save_metrics, "w") as f:
        json.dump(rep, f, indent=2)
    print(f"✔ Saved metrics → {save_metrics}")


# ==========================================================
# TRAIN ALL THREE MODELS
# ==========================================================
def train_all():

    df = load_and_clean()
    encoders = {}

    train_single_classifier(df, "HR_Class", MODEL_HR, METRIC_HR, encoders)
    train_single_classifier(df, "RR_Class", MODEL_RR, METRIC_RR, encoders)
    train_single_classifier(df, "Stress_Class", MODEL_STRESS, METRIC_STRESS, encoders)

    with open(ENCODER_FILE, "w") as f:
        json.dump(encoders, f, indent=2)

    print(f"\n✔ Saved encoders → {ENCODER_FILE}")


# ==========================================================
# MAIN
# ==========================================================
if __name__ == "__main__":
    train_all()
