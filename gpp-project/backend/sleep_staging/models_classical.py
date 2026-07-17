"""
sleep_staging/models_classical.py
─────────────────────────────────
Classical ML models for sleep‑stage classification.

Supported models:
    • Random Forest
    • SVM (RBF kernel, with probability calibration)
    • XGBoost (gradient‑boosted trees)
"""

from __future__ import annotations
import os, joblib
import numpy as np
from typing import Any, Dict, Optional

from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from . import config as CFG

# Optional XGBoost
try:
    from xgboost import XGBClassifier
    _HAS_XGB = True
except ImportError:
    _HAS_XGB = False

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


# ────────────────────────────────────────────────────────────────────
#  FACTORY
# ────────────────────────────────────────────────────────────────────

def build_model(
    model_type: str = CFG.DEFAULT_MODEL_TYPE,
    n_classes: int = 4,
    seed: int = CFG.RANDOM_SEED,
    **kwargs,
) -> Pipeline:
    """
    Build a scikit‑learn Pipeline (scaler + classifier).

    Parameters
    ──────────
    model_type : "random_forest" | "svm" | "xgboost"
    n_classes  : number of target classes
    seed       : random state
    **kwargs   : forwarded to the classifier constructor

    Returns
    ───────
    sklearn Pipeline  (StandardScaler → Classifier)
    """
    model_type = model_type.lower().replace("-", "_")

    if model_type == "random_forest":
        clf = RandomForestClassifier(
            n_estimators=kwargs.get("n_estimators", CFG.DEFAULT_N_ESTIMATORS),
            max_depth=kwargs.get("max_depth", CFG.DEFAULT_MAX_DEPTH),
            min_samples_leaf=kwargs.get("min_samples_leaf", 5),
            random_state=seed,
            n_jobs=-1,
        )
    elif model_type == "svm":
        clf = SVC(
            C=kwargs.get("C", CFG.DEFAULT_SVM_C),
            kernel=kwargs.get("kernel", CFG.DEFAULT_SVM_KERNEL),
            probability=True,
            random_state=seed,
        )
    elif model_type == "xgboost":
        if not _HAS_XGB:
            raise ImportError("XGBoost is not installed. pip install xgboost")
        clf = XGBClassifier(
            n_estimators=kwargs.get("n_estimators", CFG.XGB_N_ESTIMATORS),
            max_depth=kwargs.get("max_depth", CFG.XGB_MAX_DEPTH),
            learning_rate=kwargs.get("learning_rate", CFG.XGB_LEARNING_RATE),
            eval_metric="mlogloss",
            random_state=seed,
            n_jobs=-1,
        )
    else:
        raise ValueError(f"Unknown classical model type: {model_type}")

    return Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", clf),
    ])


# ────────────────────────────────────────────────────────────────────
#  SAVE / LOAD
# ────────────────────────────────────────────────────────────────────

def save_model(pipeline: Pipeline, model_type: str, path: Optional[str] = None) -> str:
    """Persist trained pipeline to disk.  Returns the saved path."""
    if path is None:
        fname = CFG.MODEL_FILE_TEMPLATE.format(model_type=model_type)
        path = os.path.join(MODULE_DIR, fname)
    joblib.dump(pipeline, path)
    return path


def load_model(model_type: str, path: Optional[str] = None) -> Pipeline:
    """Load a trained pipeline from disk."""
    if path is None:
        fname = CFG.MODEL_FILE_TEMPLATE.format(model_type=model_type)
        path = os.path.join(MODULE_DIR, fname)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Model not found: {path}")
    return joblib.load(path)
