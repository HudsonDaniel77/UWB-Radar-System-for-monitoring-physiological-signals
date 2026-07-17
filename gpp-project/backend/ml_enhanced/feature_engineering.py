"""
ml_enhanced/feature_engineering.py
──────────────────────────────────
Feature normalisation, HRV / RRV computation, spectral features,
and importance analysis for the enhanced ML pipeline.

All functions operate on NumPy arrays and return NumPy arrays so
they can be used with both classical and deep-learning models.
"""

from __future__ import annotations
import numpy as np
from typing import Dict, List, Optional, Tuple

from . import config as CFG

# ────────────────────────────────────────────────────────────────────
#  NORMALISATION / SCALING
# ────────────────────────────────────────────────────────────────────

class FeatureScaler:
    """Z-score normaliser that remembers training statistics."""

    def __init__(self):
        self.mean_: Optional[np.ndarray] = None
        self.std_: Optional[np.ndarray] = None
        self.fitted = False

    def fit(self, X: np.ndarray) -> "FeatureScaler":
        self.mean_ = np.mean(X, axis=0)
        self.std_ = np.std(X, axis=0)
        self.std_[self.std_ < 1e-12] = 1.0       # prevent div-by-zero
        self.fitted = True
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if not self.fitted:
            raise RuntimeError("FeatureScaler not fitted – call .fit() first")
        return (X - self.mean_) / self.std_

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        return self.fit(X).transform(X)

    def inverse_transform(self, X: np.ndarray) -> np.ndarray:
        if not self.fitted:
            raise RuntimeError("FeatureScaler not fitted")
        return X * self.std_ + self.mean_

    def get_params(self) -> Dict:
        return {"mean": self.mean_.tolist() if self.mean_ is not None else [],
                "std":  self.std_.tolist()  if self.std_ is not None else []}


# ────────────────────────────────────────────────────────────────────
#  HRV FEATURES (time domain)
# ────────────────────────────────────────────────────────────────────

def compute_hrv_time_domain(
    hr_series: np.ndarray,
) -> Dict[str, float]:
    """
    Compute time-domain HRV features from a heart-rate series.

    Parameters
    ──────────
    hr_series : 1-D array of HR values (one per sample or per epoch)

    Returns dict with hrv_sdnn, hrv_rmssd, hrv_range, hrv_pnn50
    """
    if len(hr_series) < 3:
        return {"hrv_sdnn": 0.0, "hrv_rmssd": 0.0,
                "hrv_range": 0.0, "hrv_pnn50": 0.0}

    # NN intervals approximated from HR:  NN_i ≈ 60/HR_i  (seconds)
    nn = 60.0 / np.clip(hr_series, 30, 200)

    diffs = np.diff(nn)

    sdnn  = float(np.std(nn))
    rmssd = float(np.sqrt(np.mean(diffs ** 2)))
    rng   = float(np.max(nn) - np.min(nn))

    # pNN50: fraction of successive diffs > 50 ms
    pnn50 = float(np.mean(np.abs(diffs) > 0.050)) if len(diffs) > 0 else 0.0

    return {"hrv_sdnn": sdnn, "hrv_rmssd": rmssd,
            "hrv_range": rng, "hrv_pnn50": pnn50}


# ────────────────────────────────────────────────────────────────────
#  HRV FEATURES (frequency domain)
# ────────────────────────────────────────────────────────────────────

def compute_hrv_frequency_domain(
    hr_series: np.ndarray,
    fs: float = 1.0,              # 1 sample / epoch
) -> Dict[str, float]:
    """
    Compute LF and HF power from HR series using Welch / FFT.

    LF band : 0.04 – 0.15 Hz
    HF band : 0.15 – 0.40 Hz

    When the input is epoch-level (one HR per 30 s epoch), the
    effective sampling rate is 1/30 Hz ≈ 0.033 Hz, which is below
    the typical LF/HF range.  In that case we estimate spectral
    power from the available bandwidth.
    """
    defaults = {"hrv_lf_power": 0.0, "hrv_hf_power": 0.0,
                "hrv_lf_hf_ratio": 0.0}
    n = len(hr_series)
    if n < 8:
        return defaults

    nn = 60.0 / np.clip(hr_series, 30, 200)
    nn = nn - np.mean(nn)

    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    power = np.abs(np.fft.rfft(nn)) ** 2 / n

    # Adaptive bands based on actual Nyquist
    nyq = fs / 2
    lf_lo, lf_hi = 0.04, min(0.15, nyq)
    hf_lo, hf_hi = max(0.15, lf_hi), min(0.40, nyq)

    lf_mask = (freqs >= lf_lo) & (freqs < lf_hi)
    hf_mask = (freqs >= hf_lo) & (freqs < hf_hi)

    lf_power = float(np.sum(power[lf_mask])) if np.any(lf_mask) else 0.0
    hf_power = float(np.sum(power[hf_mask])) if np.any(hf_mask) else 0.0

    ratio = lf_power / hf_power if hf_power > 1e-12 else 0.0

    return {"hrv_lf_power": lf_power, "hrv_hf_power": hf_power,
            "hrv_lf_hf_ratio": ratio}


# ────────────────────────────────────────────────────────────────────
#  RESPIRATORY DYNAMICS
# ────────────────────────────────────────────────────────────────────

def compute_rr_dynamics(
    rr_series: np.ndarray,
) -> Dict[str, float]:
    """
    Compute respiratory-rate dynamics features.

    Returns rr_trend_3, rr_trend_5, rr_cv, rr_delta
    """
    n = len(rr_series)
    result: Dict[str, float] = {}

    # Rolling-slope over 3 epochs
    if n >= 3:
        win = rr_series[-3:]
        x = np.arange(len(win))
        result["rr_trend_3"] = float(np.polyfit(x, win, 1)[0])
    else:
        result["rr_trend_3"] = 0.0

    # Rolling-slope over 5 epochs
    if n >= 5:
        win = rr_series[-5:]
        x = np.arange(len(win))
        result["rr_trend_5"] = float(np.polyfit(x, win, 1)[0])
    else:
        result["rr_trend_5"] = 0.0

    # Coefficient of variation
    mu = np.mean(rr_series)
    result["rr_cv"] = float(np.std(rr_series) / mu) if abs(mu) > 1e-6 else 0.0

    # Epoch-to-epoch delta (latest)
    result["rr_delta"] = float(rr_series[-1] - rr_series[-2]) if n >= 2 else 0.0

    return result


# ────────────────────────────────────────────────────────────────────
#  MOTION SPECTRAL FEATURES
# ────────────────────────────────────────────────────────────────────

def compute_motion_spectral(
    motion_series: np.ndarray,
    fs: float = 1.0,
) -> Dict[str, float]:
    """
    Compute spectral energy and dominant frequency of motion signal.
    """
    n = len(motion_series)
    if n < 4:
        return {"motion_spectral_energy": 0.0, "motion_dominant_freq": 0.0}

    sig = motion_series - np.mean(motion_series)
    power = np.abs(np.fft.rfft(sig)) ** 2 / n
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)

    energy = float(np.sum(power[1:]))      # skip DC
    dom_idx = np.argmax(power[1:]) + 1 if len(power) > 1 else 0
    dom_freq = float(freqs[dom_idx]) if dom_idx < len(freqs) else 0.0

    return {"motion_spectral_energy": energy, "motion_dominant_freq": dom_freq}


# ────────────────────────────────────────────────────────────────────
#  CARDIORESPIRATORY COUPLING
# ────────────────────────────────────────────────────────────────────

def compute_cardiorespiratory_coupling(
    rr_series: np.ndarray,
    hr_series: np.ndarray,
) -> float:
    """Pearson correlation between RR and HR over a window."""
    if len(rr_series) < 3 or len(hr_series) < 3:
        return 0.0
    n = min(len(rr_series), len(hr_series))
    rr_s = rr_series[:n].astype(float)
    hr_s = hr_series[:n].astype(float)
    if np.std(rr_s) < 1e-12 or np.std(hr_s) < 1e-12:
        return 0.0
    return float(np.corrcoef(rr_s, hr_s)[0, 1])


# ────────────────────────────────────────────────────────────────────
#  FULL FEATURE ENGINEERING PIPELINE
# ────────────────────────────────────────────────────────────────────

def engineer_features_epoch(
    raw_features: np.ndarray,
    rr_history: np.ndarray,
    hr_history: np.ndarray,
    motion_history: np.ndarray,
) -> np.ndarray:
    """
    Given a raw feature vector for one epoch plus signal histories,
    compute all engineered features and return the full feature vector.

    Parameters
    ──────────
    raw_features    : 1-D array of shape (len(RAW_FEATURES),)
    rr_history      : recent RR values (up to 5 epochs)
    hr_history      : recent HR values (up to 5 epochs)
    motion_history  : recent motion values (up to 5 epochs)

    Returns
    ───────
    1-D array of shape (FEATURE_DIM,)
    """
    # HRV time-domain
    hrv_td = compute_hrv_time_domain(hr_history)
    # HRV frequency-domain
    hrv_fd = compute_hrv_frequency_domain(hr_history)
    # RR dynamics
    rr_dyn = compute_rr_dynamics(rr_history)
    # Motion spectral
    mot_sp = compute_motion_spectral(motion_history)
    # Cardiorespiratory coupling
    crc = compute_cardiorespiratory_coupling(rr_history, hr_history)

    engineered = np.array([
        hrv_td["hrv_sdnn"], hrv_td["hrv_rmssd"],
        hrv_td["hrv_range"], hrv_td["hrv_pnn50"],
        hrv_fd["hrv_lf_power"], hrv_fd["hrv_hf_power"],
        hrv_fd["hrv_lf_hf_ratio"],
        rr_dyn["rr_trend_3"], rr_dyn["rr_trend_5"],
        rr_dyn["rr_cv"], rr_dyn["rr_delta"],
        mot_sp["motion_spectral_energy"], mot_sp["motion_dominant_freq"],
        crc,
    ], dtype=np.float64)

    return np.concatenate([raw_features.astype(np.float64), engineered])


def engineer_features_batch(
    raw_matrix: np.ndarray,
    rr_col: int = 0,
    hr_col: int = 9,
    motion_col: int = 18,
    window: int = 5,
) -> np.ndarray:
    """
    Apply feature engineering to every epoch in a (n_epochs, n_raw) matrix.

    Parameters
    ──────────
    raw_matrix  : (n_epochs, n_raw_features)
    rr_col      : column index of rr_mean in raw features
    hr_col      : column index of hr_mean in raw features
    motion_col  : column index of motion_index in raw features
    window      : look-back window for history features

    Returns (n_epochs, FEATURE_DIM)
    """
    n = raw_matrix.shape[0]
    out = np.zeros((n, CFG.FEATURE_DIM), dtype=np.float64)

    for i in range(n):
        lo = max(0, i - window + 1)
        rr_hist     = raw_matrix[lo:i + 1, rr_col]
        hr_hist     = raw_matrix[lo:i + 1, hr_col]
        motion_hist = raw_matrix[lo:i + 1, motion_col]

        out[i] = engineer_features_epoch(
            raw_matrix[i], rr_hist, hr_hist, motion_hist,
        )

    return out


# ────────────────────────────────────────────────────────────────────
#  FEATURE IMPORTANCE
# ────────────────────────────────────────────────────────────────────

def feature_importance_from_model(
    model,
    feature_names: Optional[List[str]] = None,
) -> Dict[str, float]:
    """
    Extract feature importances from a fitted sklearn-compatible model.

    Supports:
      • tree ensembles  (.feature_importances_)
      • linear models   (.coef_)
      • pipelines       (last step)
    """
    if feature_names is None:
        feature_names = CFG.ALL_FEATURES

    estimator = model
    # Unwrap wrapper objects that expose a .pipeline attribute
    if hasattr(estimator, "pipeline"):
        estimator = estimator.pipeline
    # Unwrap sklearn Pipeline
    if hasattr(estimator, "named_steps"):
        step_keys = list(estimator.named_steps.keys())
        estimator = estimator.named_steps[step_keys[-1]]

    if hasattr(estimator, "feature_importances_"):
        imp = estimator.feature_importances_
    elif hasattr(estimator, "coef_"):
        imp = np.abs(estimator.coef_).mean(axis=0) if estimator.coef_.ndim > 1 else np.abs(estimator.coef_)
    else:
        return {}

    n = min(len(feature_names), len(imp))
    return {feature_names[i]: float(imp[i]) for i in range(n)}


def rank_features(
    importances: Dict[str, float],
    top_k: int = 15,
) -> List[Tuple[str, float]]:
    """Return top-k features sorted by importance (descending)."""
    ranked = sorted(importances.items(), key=lambda x: x[1], reverse=True)
    return ranked[:top_k]
