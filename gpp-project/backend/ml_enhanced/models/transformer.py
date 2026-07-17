"""
ml_enhanced/models/transformer.py
─────────────────────────────────
Transformer / multi-head self-attention model for sequential
sleep signal classification.

Architecture:
    Positional encoding → N × (MultiHeadAttention + FFN) → pooling → dense

Uses TensorFlow / Keras.
"""

from __future__ import annotations
import os
import warnings
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseModel
from .. import config as CFG

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


# ────────────────────────────────────────────────────────────────────
#  POSITIONAL ENCODING (learnable)
# ────────────────────────────────────────────────────────────────────

if _HAS_TF:
    class _PositionalEncoding(layers.Layer):
        """Learnable positional embedding added to the input."""

        def __init__(self, max_len: int, d_model: int, **kwargs):
            super().__init__(**kwargs)
            self.pos_embed = layers.Embedding(max_len, d_model)

        def call(self, x):
            positions = tf.range(start=0, limit=tf.shape(x)[1])
            return x + self.pos_embed(positions)

    class _TransformerBlock(layers.Layer):
        """Single transformer encoder block."""

        def __init__(self, d_model, n_heads, ff_dim, dropout=0.1, **kwargs):
            super().__init__(**kwargs)
            self.att = layers.MultiHeadAttention(
                num_heads=n_heads, key_dim=d_model // n_heads,
            )
            self.ffn = keras.Sequential([
                layers.Dense(ff_dim, activation="relu"),
                layers.Dense(d_model),
            ])
            self.ln1 = layers.LayerNormalization(epsilon=1e-6)
            self.ln2 = layers.LayerNormalization(epsilon=1e-6)
            self.drop1 = layers.Dropout(dropout)
            self.drop2 = layers.Dropout(dropout)

        def call(self, x, training=False):
            attn = self.att(x, x, training=training)
            x = self.ln1(x + self.drop1(attn, training=training))
            ffn_out = self.ffn(x)
            return self.ln2(x + self.drop2(ffn_out, training=training))


class TransformerModel(BaseModel):
    """
    Transformer encoder for sleep-stage / event classification.

    Input shape: (batch, seq_len, n_features)
    """
    name = "transformer"

    def __init__(
        self,
        input_shape: Optional[Tuple[int, int]] = None,
        n_classes: int = 2,
        hidden_dim: int = CFG.DL_HIDDEN_DIM,
        n_heads: int = CFG.TF_N_HEADS,
        ff_dim: int = CFG.TF_FF_DIM,
        n_layers: int = CFG.TF_N_LAYERS,
        dropout: float = CFG.DL_DROPOUT,
        **kwargs,
    ):
        self.input_shape_ = input_shape
        self.n_classes = n_classes
        self.hidden_dim = hidden_dim
        self.n_heads = n_heads
        self.ff_dim = ff_dim
        self.n_layers = n_layers
        self.dropout = dropout
        self.model: Any = None
        self.history: Dict = {}

    def _build(self):
        if not _HAS_TF:
            warnings.warn("TensorFlow not installed – Transformer unavailable.")
            return

        seq_len, n_feat = self.input_shape_

        inp = layers.Input(shape=self.input_shape_)

        # Project features to hidden_dim
        x = layers.Dense(self.hidden_dim)(inp)
        x = _PositionalEncoding(seq_len, self.hidden_dim)(x)

        for _ in range(self.n_layers):
            x = _TransformerBlock(
                self.hidden_dim, self.n_heads,
                self.ff_dim, self.dropout,
            )(x)

        # Pool over time
        x = layers.GlobalAveragePooling1D()(x)
        x = layers.Dropout(self.dropout)(x)
        x = layers.Dense(self.hidden_dim // 2, activation="relu")(x)
        x = layers.Dropout(self.dropout)(x)
        out = layers.Dense(self.n_classes, activation="softmax")(x)

        self.model = Model(inp, out)
        self.model.compile(
            optimizer=keras.optimizers.Adam(CFG.DL_LEARNING_RATE),
            loss="sparse_categorical_crossentropy",
            metrics=["accuracy"],
        )

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

    def predict(self, X):
        if self.model is None:
            return np.array([])
        return np.argmax(self.model.predict(X, verbose=0), axis=1)

    def predict_proba(self, X):
        if self.model is None:
            return None
        return self.model.predict(X, verbose=0)

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
                       "n_heads": self.n_heads,
                       "n_layers": self.n_layers,
                       "tf_available": _HAS_TF}
        if self.model is not None:
            info["params"] = int(self.model.count_params())
        return info
