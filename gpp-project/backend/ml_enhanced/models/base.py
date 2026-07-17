"""
ml_enhanced/models/base.py
──────────────────────────
Abstract base class for all ML-enhanced models.

Provides a uniform interface for training, prediction, and
persistence across classical and deep-learning architectures.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import numpy as np


class BaseModel(ABC):
    """Common interface for every model in the ml_enhanced pipeline."""

    name: str = "base"

    @abstractmethod
    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        **kwargs,
    ) -> Dict:
        """
        Train the model.

        Returns a dict with training metadata (history, duration, etc.)
        """

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Return class predictions (int labels)."""

    def predict_proba(self, X: np.ndarray) -> Optional[np.ndarray]:
        """Return probability estimates.  None if not supported."""
        return None

    @abstractmethod
    def save(self, path: str) -> str:
        """Persist model to *path*.  Return actual path used."""

    @abstractmethod
    def load(self, path: str) -> None:
        """Load a previously saved model."""

    def summary(self) -> Dict[str, Any]:
        """Return a human-readable description of the model."""
        return {"name": self.name}
