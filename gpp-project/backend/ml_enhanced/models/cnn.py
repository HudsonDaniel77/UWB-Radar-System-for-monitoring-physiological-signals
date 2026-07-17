"""
ml_enhanced/models/cnn.py
─────────────────────────
1-D Convolutional Neural Network for temporal sleep signal
classification.

Uses TensorFlow / Keras.  If TensorFlow is not installed every
public function returns ``None`` and the pipeline falls back to
classical models gracefully.
"""

from __future__ import annotations
import os
import warnings
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseModel
from .. import config as CFG

# ── Optional TF import ─────────────────────────────────────────────
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers, Model, callbacks  # type: ignore
    _HAS_TF = True
except ImportError:
    _HAS_TF = False

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


def is_available() -> bool:
    return _HAS_TF


class CNN1DModel(BaseModel):
    """
    1-D CNN with stacked temporal convolutions → global pooling → dense.

    Input shape: (batch, seq_len, n_features)
    """
    name = "cnn_1d"

    def __init__(
        self,
        input_shape: Optional[Tuple[int, int]] = None,
        n_classes: int = 2,
        hidden_dim: int = CFG.DL_HIDDEN_DIM,
        dropout: float = CFG.DL_DROPOUT,
        **kwargs,
    ):
        self.input_shape_ = input_shape
        self.n_classes = n_classes
        self.hidden_dim = hidden_dim
        self.dropout = dropout
        self.model: Any = None
        self.history: Dict = {}

    # ── build ───────────────────────────────────────────────────────
    def _build(self):
        if not _HAS_TF:
            warnings.warn("TensorFlow not installed – CNN model unavailable.")
            return
        inp = layers.Input(shape=self.input_shape_)
        x = layers.Conv1D(self.hidden_dim, 5, padding="same", activation="relu")(inp)
        x = layers.BatchNormalization()(x)
        x = layers.Conv1D(self.hidden_dim, 5, padding="same", activation="relu")(x)
        x = layers.BatchNormalization()(x)
        x = layers.MaxPooling1D(2)(x)
        x = layers.Conv1D(self.hidden_dim * 2, 3, padding="same", activation="relu")(x)
        x = layers.BatchNormalization()(x)
        x = layers.GlobalAveragePooling1D()(x)
        x = layers.Dropout(self.dropout)(x)
        x = layers.Dense(self.hidden_dim, activation="relu")(x)
        x = layers.Dropout(self.dropout)(x)
        out = layers.Dense(self.n_classes, activation="softmax")(x)
        self.model = Model(inp, out)
        self.model.compile(
            optimizer=keras.optimizers.Adam(CFG.DL_LEARNING_RATE),
            loss="sparse_categorical_crossentropy",
            metrics=["accuracy"],
        )

    # ── fit ─────────────────────────────────────────────────────────
    def fit(self, X_train, y_train, X_val=None, y_val=None, **kw) -> Dict:
        if not _HAS_TF:
            return {"error": "TensorFlow not installed"}

        if self.input_shape_ is None:
            self.input_shape_ = (X_train.shape[1], X_train.shape[2])
        self._build()

        epochs     = kw.get("epochs", CFG.DL_EPOCHS)
        batch_size = kw.get("batch_size", CFG.DL_BATCH_SIZE)

        cbs: List = []
        if X_val is not None and y_val is not None:
            cbs.append(callbacks.EarlyStopping(
                monitor="val_loss", patience=CFG.DL_PATIENCE,
                restore_best_weights=True,
            ))
            cbs.append(callbacks.ReduceLROnPlateau(
                monitor="val_loss", factor=0.5, patience=5, min_lr=1e-6,
            ))
            val_data = (X_val, y_val)
        else:
            val_data = None

        hist = self.model.fit(
            X_train, y_train,
            validation_data=val_data,
            epochs=epochs,
            batch_size=batch_size,
            callbacks=cbs,
            verbose=0,
        )
        self.history = {k: [float(v) for v in vals]
                        for k, vals in hist.history.items()}
        return {"epochs_run": len(hist.history.get("loss", [])),
                "history": self.history}

    # ── predict ─────────────────────────────────────────────────────
    def predict(self, X):
        if self.model is None:
            return np.array([])
        proba = self.model.predict(X, verbose=0)
        return np.argmax(proba, axis=1)

    def predict_proba(self, X):
        if self.model is None:
            return None
        return self.model.predict(X, verbose=0)

    # ── persistence ─────────────────────────────────────────────────
    def save(self, path: str) -> str:
        if self.model is None:
            return ""
        self.model.save(path)
        return path

    def load(self, path: str):
        if not _HAS_TF:
            return
        self.model = keras.models.load_model(path)

    def summary(self):
        info: Dict = {"name": self.name, "n_classes": self.n_classes,
                       "hidden_dim": self.hidden_dim,
                       "tf_available": _HAS_TF}
        if self.model is not None:
            info["params"] = int(self.model.count_params())
        return info
