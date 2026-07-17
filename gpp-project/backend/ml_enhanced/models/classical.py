"""
ml_enhanced/models/classical.py
───────────────────────────────
Classical ML model wrappers:  Random Forest, SVM, XGBoost.

Each wrapper implements the :class:`BaseModel` interface and wraps
an sklearn Pipeline (imputer → scaler → estimator).
"""

from __future__ import annotations
import os
import warnings
import numpy as np
import joblib
from typing import Any, Dict, Optional

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC

from .base import BaseModel
from .. import config as CFG

# Optional XGBoost import
try:
    from xgboost import XGBClassifier
    _HAS_XGB = True
except ImportError:
    _HAS_XGB = False

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


# ────────────────────────────────────────────────────────────────────
#  RANDOM FOREST
# ────────────────────────────────────────────────────────────────────

class RandomForestModel(BaseModel):
    name = "random_forest"

    def __init__(
        self,
        n_estimators: int = CFG.RF_N_ESTIMATORS,
        max_depth: int = CFG.RF_MAX_DEPTH,
        min_samples_leaf: int = CFG.RF_MIN_SAMPLES,
        seed: int = CFG.RANDOM_SEED,
        **kwargs,
    ):
        self.pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler",  StandardScaler()),
            ("model",   RandomForestClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                min_samples_leaf=min_samples_leaf,
                class_weight="balanced",
                random_state=seed,
                n_jobs=-1,
            )),
        ])
        self._params = dict(n_estimators=n_estimators,
                            max_depth=max_depth,
                            min_samples_leaf=min_samples_leaf)

    def fit(self, X_train, y_train, X_val=None, y_val=None, **kw) -> Dict:
        self.pipeline.fit(X_train, y_train)
        return {"n_train": len(X_train)}

    def predict(self, X):
        return self.pipeline.predict(X)

    def predict_proba(self, X):
        return self.pipeline.predict_proba(X)

    def save(self, path: str) -> str:
        joblib.dump(self.pipeline, path)
        return path

    def load(self, path: str):
        self.pipeline = joblib.load(path)

    def summary(self):
        return {"name": self.name, **self._params}


# ────────────────────────────────────────────────────────────────────
#  SVM
# ────────────────────────────────────────────────────────────────────

class SVMModel(BaseModel):
    name = "svm"

    def __init__(
        self,
        C: float = CFG.SVM_C,
        kernel: str = CFG.SVM_KERNEL,
        gamma: str = CFG.SVM_GAMMA,
        seed: int = CFG.RANDOM_SEED,
        **kwargs,
    ):
        self.pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler",  StandardScaler()),
            ("model",   SVC(
                C=C, kernel=kernel, gamma=gamma,
                class_weight="balanced",
                probability=True,
                random_state=seed,
            )),
        ])
        self._params = dict(C=C, kernel=kernel, gamma=gamma)

    def fit(self, X_train, y_train, X_val=None, y_val=None, **kw) -> Dict:
        self.pipeline.fit(X_train, y_train)
        return {"n_train": len(X_train)}

    def predict(self, X):
        return self.pipeline.predict(X)

    def predict_proba(self, X):
        return self.pipeline.predict_proba(X)

    def save(self, path: str) -> str:
        joblib.dump(self.pipeline, path)
        return path

    def load(self, path: str):
        self.pipeline = joblib.load(path)

    def summary(self):
        return {"name": self.name, **self._params}


# ────────────────────────────────────────────────────────────────────
#  XGBOOST  (fallback to sklearn GradientBoosting if not installed)
# ────────────────────────────────────────────────────────────────────

class XGBoostModel(BaseModel):
    name = "xgboost"

    def __init__(
        self,
        n_estimators: int = CFG.XGB_N_ESTIMATORS,
        max_depth: int = CFG.XGB_MAX_DEPTH,
        learning_rate: float = CFG.XGB_LEARNING_RATE,
        subsample: float = CFG.XGB_SUBSAMPLE,
        colsample_bytree: float = CFG.XGB_COLSAMPLE,
        reg_lambda: float = CFG.XGB_REG_LAMBDA,
        seed: int = CFG.RANDOM_SEED,
        n_classes: int = 2,
        **kwargs,
    ):
        if _HAS_XGB:
            estimator = XGBClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                learning_rate=learning_rate,
                subsample=subsample,
                colsample_bytree=colsample_bytree,
                reg_lambda=reg_lambda,
                objective="multi:softprob" if n_classes > 2 else "binary:logistic",
                eval_metric="mlogloss" if n_classes > 2 else "logloss",
                use_label_encoder=False,
                random_state=seed,
                verbosity=0,
            )
        else:
            warnings.warn("XGBoost not installed – falling back to "
                          "sklearn GradientBoostingClassifier.")
            estimator = GradientBoostingClassifier(
                n_estimators=n_estimators,
                max_depth=min(max_depth, 10),
                learning_rate=learning_rate,
                subsample=subsample,
                random_state=seed,
            )

        self.pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler",  StandardScaler()),
            ("model",   estimator),
        ])
        self._params = dict(n_estimators=n_estimators,
                            max_depth=max_depth,
                            learning_rate=learning_rate)

    def fit(self, X_train, y_train, X_val=None, y_val=None, **kw) -> Dict:
        fit_params = {}
        if X_val is not None and y_val is not None and _HAS_XGB:
            # XGBoost early stopping via eval_set
            X_tr_s = self.pipeline[:-1].fit_transform(X_train)
            X_va_s = self.pipeline[:-1].transform(X_val)
            self.pipeline.named_steps["model"].fit(
                X_tr_s, y_train,
                eval_set=[(X_va_s, y_val)],
                verbose=False,
            )
            # re-fit pipeline steps so .predict works end-to-end
            self.pipeline[:-1].fit(X_train)
        else:
            self.pipeline.fit(X_train, y_train)
        return {"n_train": len(X_train)}

    def predict(self, X):
        return self.pipeline.predict(X)

    def predict_proba(self, X):
        return self.pipeline.predict_proba(X)

    def save(self, path: str) -> str:
        joblib.dump(self.pipeline, path)
        return path

    def load(self, path: str):
        self.pipeline = joblib.load(path)

    def summary(self):
        return {"name": self.name, "xgboost_available": _HAS_XGB,
                **self._params}


# ────────────────────────────────────────────────────────────────────
#  FACTORY
# ────────────────────────────────────────────────────────────────────

_REGISTRY = {
    "random_forest": RandomForestModel,
    "svm":           SVMModel,
    "xgboost":       XGBoostModel,
}


def build_classical_model(
    model_type: str,
    n_classes: int = 2,
    **kwargs,
) -> BaseModel:
    """Instantiate a classical ML model by name."""
    key = model_type.lower().replace("-", "_")
    if key not in _REGISTRY:
        raise ValueError(f"Unknown classical model: {model_type}. "
                         f"Choose from {list(_REGISTRY)}")
    return _REGISTRY[key](n_classes=n_classes, **kwargs)


def list_classical_models() -> list:
    """Return list of available classical model names."""
    return list(_REGISTRY.keys())
