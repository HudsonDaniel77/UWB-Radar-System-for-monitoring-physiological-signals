"""
sleep_staging/models_deep.py
────────────────────────────
Deep‑learning models for sleep‑stage classification.

Supported architectures (require TensorFlow / Keras):
    • LSTM                – sequence‑aware recurrent model
    • CNN + LSTM          – temporal convolutions + recurrent head
    • TCN (dilated CNN)   – temporal convolutional network

If TensorFlow is not installed every builder returns ``None`` and
the training pipeline gracefully falls back to classical models.
"""

from __future__ import annotations
import os, warnings
import numpy as np
from typing import Any, Dict, Optional, Tuple

from . import config as CFG

# ── Optional TF import ─────────────────────────────────────────────
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers, Model  # type: ignore
    _HAS_TF = True
except ImportError:
    _HAS_TF = False

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


def is_available() -> bool:
    """Return True if TensorFlow is installed."""
    return _HAS_TF


# ────────────────────────────────────────────────────────────────────
#  LSTM
# ────────────────────────────────────────────────────────────────────

def build_lstm(
    input_shape: Tuple[int, int],
    n_classes: int = 4,
    hidden_dim: int = CFG.DL_HIDDEN_DIM,
    dropout: float = CFG.DL_DROPOUT,
) -> Any:
    """
    Simple 2‑layer LSTM → Dense classifier.

    input_shape : (sequence_len, n_features)
    """
    if not _HAS_TF:
        warnings.warn("TensorFlow not installed – LSTM model unavailable.")
        return None

    model = keras.Sequential([
        layers.Input(shape=input_shape),
        layers.LSTM(hidden_dim, return_sequences=True),
        layers.Dropout(dropout),
        layers.LSTM(hidden_dim // 2),
        layers.Dropout(dropout),
        layers.Dense(hidden_dim // 2, activation="relu"),
        layers.Dense(n_classes, activation="softmax"),
    ])
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=CFG.DL_LEARNING_RATE),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


# ────────────────────────────────────────────────────────────────────
#  CNN + LSTM
# ────────────────────────────────────────────────────────────────────

def build_cnn_lstm(
    input_shape: Tuple[int, int],
    n_classes: int = 4,
    hidden_dim: int = CFG.DL_HIDDEN_DIM,
    dropout: float = CFG.DL_DROPOUT,
) -> Any:
    """
    1D‑CNN feature extractor → LSTM sequence model → Dense head.

    input_shape : (sequence_len, n_features)
    """
    if not _HAS_TF:
        warnings.warn("TensorFlow not installed – CNN+LSTM model unavailable.")
        return None

    model = keras.Sequential([
        layers.Input(shape=input_shape),
        layers.Conv1D(hidden_dim, kernel_size=3, padding="same", activation="relu"),
        layers.BatchNormalization(),
        layers.Conv1D(hidden_dim, kernel_size=3, padding="same", activation="relu"),
        layers.MaxPooling1D(pool_size=2),
        layers.LSTM(hidden_dim // 2),
        layers.Dropout(dropout),
        layers.Dense(hidden_dim // 4, activation="relu"),
        layers.Dense(n_classes, activation="softmax"),
    ])
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=CFG.DL_LEARNING_RATE),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


# ────────────────────────────────────────────────────────────────────
#  TCN (Temporal Convolutional Network)
# ────────────────────────────────────────────────────────────────────

def _tcn_residual_block(x, filters, kernel_size, dilation_rate, dropout):
    """Single TCN residual block with dilated causal convolution."""
    conv = layers.Conv1D(
        filters, kernel_size,
        padding="causal",
        dilation_rate=dilation_rate,
        activation="relu",
    )(x)
    conv = layers.BatchNormalization()(conv)
    conv = layers.Dropout(dropout)(conv)
    conv = layers.Conv1D(
        filters, kernel_size,
        padding="causal",
        dilation_rate=dilation_rate,
        activation="relu",
    )(conv)
    conv = layers.BatchNormalization()(conv)
    conv = layers.Dropout(dropout)(conv)
    # residual connection
    if x.shape[-1] != filters:
        x = layers.Conv1D(filters, 1)(x)
    return layers.Add()([x, conv])


def build_tcn(
    input_shape: Tuple[int, int],
    n_classes: int = 4,
    hidden_dim: int = CFG.DL_HIDDEN_DIM,
    dropout: float = CFG.DL_DROPOUT,
    n_blocks: int = 3,
) -> Any:
    """
    Temporal Convolutional Network with residual blocks.

    input_shape : (sequence_len, n_features)
    """
    if not _HAS_TF:
        warnings.warn("TensorFlow not installed – TCN model unavailable.")
        return None

    inp = layers.Input(shape=input_shape)
    x = inp
    for i in range(n_blocks):
        x = _tcn_residual_block(x, hidden_dim, kernel_size=3,
                                dilation_rate=2 ** i, dropout=dropout)
    x = layers.GlobalAveragePooling1D()(x)
    x = layers.Dense(hidden_dim // 2, activation="relu")(x)
    out = layers.Dense(n_classes, activation="softmax")(x)

    model = Model(inp, out)
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=CFG.DL_LEARNING_RATE),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


# ────────────────────────────────────────────────────────────────────
#  FACTORY
# ────────────────────────────────────────────────────────────────────

_BUILDERS = {
    "lstm":     build_lstm,
    "cnn_lstm": build_cnn_lstm,
    "tcn":      build_tcn,
}


def build_deep_model(
    model_type: str,
    input_shape: Tuple[int, int],
    n_classes: int = 4,
    **kwargs,
) -> Any:
    """
    Build a deep learning model by name.

    Parameters
    ──────────
    model_type   : "lstm" | "cnn_lstm" | "tcn"
    input_shape  : (sequence_len, n_features)
    n_classes    : number of output classes

    Returns None if TensorFlow is not installed.
    """
    key = model_type.lower().replace("-", "_")
    if key not in _BUILDERS:
        raise ValueError(f"Unknown deep model type: {model_type}. "
                         f"Choose from {list(_BUILDERS)}")
    return _BUILDERS[key](input_shape, n_classes, **kwargs)


# ────────────────────────────────────────────────────────────────────
#  SAVE / LOAD
# ────────────────────────────────────────────────────────────────────

def save_deep_model(model: Any, model_type: str, path: Optional[str] = None) -> str:
    """Save a Keras model to disk."""
    if not _HAS_TF or model is None:
        return ""
    if path is None:
        path = os.path.join(MODULE_DIR, f"sleep_stage_{model_type}.keras")
    model.save(path)
    return path


def load_deep_model(model_type: str, path: Optional[str] = None) -> Any:
    """Load a Keras model from disk."""
    if not _HAS_TF:
        return None
    if path is None:
        path = os.path.join(MODULE_DIR, f"sleep_stage_{model_type}.keras")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Deep model not found: {path}")
    return keras.models.load_model(path)
