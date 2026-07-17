"""
ml_enhanced/inference.py
────────────────────────
Production inference functions.

Public API
──────────
load_trained_model(task, model_type, path)
predict_enhanced_events(model, features, ...)
save_trained_model(model, task, model_type, output_dir)
"""

from __future__ import annotations
import os
import json
import joblib
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from . import config as CFG
from .feature_engineering import FeatureScaler
from .dataset import build_sequences

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


# ────────────────────────────────────────────────────────────────────
#  SAVE
# ────────────────────────────────────────────────────────────────────

def save_trained_model(
    model: Any,
    task: str,
    model_type: str,
    output_dir: Optional[str] = None,
    scaler: Optional[FeatureScaler] = None,
    metadata: Optional[Dict] = None,
) -> Dict[str, str]:
    """
    Persist a trained model (and optional scaler / metadata) to disk.

    Returns dict of paths written.
    """
    if output_dir is None:
        output_dir = MODULE_DIR

    os.makedirs(output_dir, exist_ok=True)
    paths: Dict[str, str] = {}

    # Determine if deep model (has .save callable from keras)
    is_deep = hasattr(model, "model") and hasattr(model, "save")

    if is_deep:
        fname = CFG.DL_MODEL_TEMPLATE.format(task=task, model_type=model_type)
        mpath = os.path.join(output_dir, fname)
        model.save(mpath)
        paths["model"] = mpath
    else:
        fname = CFG.MODEL_FILE_TEMPLATE.format(task=task, model_type=model_type)
        mpath = os.path.join(output_dir, fname)
        if hasattr(model, "pipeline"):
            joblib.dump(model.pipeline, mpath)
        elif hasattr(model, "save"):
            model.save(mpath)
        else:
            joblib.dump(model, mpath)
        paths["model"] = mpath

    # Scaler
    if scaler is not None and scaler.fitted:
        spath = os.path.join(output_dir,
                             f"ml_enhanced_{task}_{model_type}_scaler.joblib")
        joblib.dump(scaler, spath)
        paths["scaler"] = spath

    # Metadata
    if metadata is not None:
        meta_path = os.path.join(output_dir,
                                  f"ml_enhanced_{task}_{model_type}_meta.json")
        with open(meta_path, "w") as f:
            json.dump(_serialisable(metadata), f, indent=2)
        paths["metadata"] = meta_path

    return paths


# ────────────────────────────────────────────────────────────────────
#  LOAD
# ────────────────────────────────────────────────────────────────────

def load_trained_model(
    task: str,
    model_type: str,
    model_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Load a previously saved model + optional scaler.

    Returns dict with keys: "model", "scaler" (or None), "metadata".
    """
    if model_dir is None:
        model_dir = MODULE_DIR

    # Try deep model path first
    deep_path = os.path.join(
        model_dir,
        CFG.DL_MODEL_TEMPLATE.format(task=task, model_type=model_type),
    )
    classic_path = os.path.join(
        model_dir,
        CFG.MODEL_FILE_TEMPLATE.format(task=task, model_type=model_type),
    )

    model = None
    if os.path.exists(deep_path):
        try:
            from tensorflow import keras  # type: ignore
            model = keras.models.load_model(deep_path)
        except ImportError:
            raise ImportError("TensorFlow required to load deep model")
    elif os.path.exists(classic_path):
        model = joblib.load(classic_path)
    else:
        raise FileNotFoundError(
            f"No model file for task={task}, model_type={model_type} "
            f"in {model_dir}")

    # Scaler
    scaler_path = os.path.join(
        model_dir,
        f"ml_enhanced_{task}_{model_type}_scaler.joblib",
    )
    scaler = joblib.load(scaler_path) if os.path.exists(scaler_path) else None

    # Metadata
    meta_path = os.path.join(
        model_dir,
        f"ml_enhanced_{task}_{model_type}_meta.json",
    )
    metadata = {}
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            metadata = json.load(f)

    return {"model": model, "scaler": scaler, "metadata": metadata}


# ────────────────────────────────────────────────────────────────────
#  PREDICT
# ────────────────────────────────────────────────────────────────────

def predict_enhanced_events(
    model: Any,
    X: np.ndarray,
    scaler: Optional[FeatureScaler] = None,
    is_deep: bool = False,
    seq_len: int = CFG.SEQUENCE_LEN,
    label_names: Optional[List[str]] = None,
) -> Dict:
    """
    Run inference on feature matrix *X* using a trained model.

    Parameters
    ──────────
    model       : trained model object (pipeline or Keras model)
    X           : (n_epochs, n_features)
    scaler      : FeatureScaler for deep models
    is_deep     : if True, build sequences before prediction
    label_names : optional label list for decoding

    Returns
    ───────
    {
        "predictions"   : list[int],
        "label_names"   : list[str] | None,
        "probabilities" : list[list[float]] | None,
        "decoded"       : list[str] (if label_names given),
    }
    """
    if label_names is None:
        label_names = CFG.EVENT_LABELS_BINARY

    if is_deep:
        X_s = scaler.transform(X) if scaler and scaler.fitted else X
        X_seq, _ = build_sequences(X_s, np.zeros(len(X_s), dtype=int), seq_len)

        if hasattr(model, "predict"):
            proba = model.predict(X_seq, verbose=0) if hasattr(model, "predict") else None
            preds = np.argmax(proba, axis=1) if proba is not None else np.array([])
        else:
            preds = np.array([])
            proba = None
    else:
        if hasattr(model, "predict"):
            preds = model.predict(X)
        else:
            preds = np.array([])

        proba = None
        if hasattr(model, "predict_proba"):
            try:
                proba = model.predict_proba(X)
            except Exception:
                pass

    decoded = [label_names[int(p)] for p in preds] if label_names and len(preds) > 0 else []

    return {
        "predictions":   preds.tolist(),
        "label_names":   label_names,
        "probabilities": proba.tolist() if proba is not None else None,
        "decoded":       decoded,
    }


# ────────────────────────────────────────────────────────────────────
#  HELPERS
# ────────────────────────────────────────────────────────────────────

def _serialisable(obj):
    """Make dict JSON-serialisable."""
    if isinstance(obj, dict):
        return {k: _serialisable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialisable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj
