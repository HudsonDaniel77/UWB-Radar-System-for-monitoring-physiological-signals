"""
motion_posture/posture.py
─────────────────────────
Body-state classification from real radar measurements.

Instead of fake ML trained on synthetic data (which cannot reliably
distinguish Supine/Left/Right/Prone from a forward-pointing radar),
we use a rule-based classifier on quantities the radar actually measures:

    Feature vector indices used:
      [1]  chest_disp std      – breathing amplitude variation
      [7]  breath_wave std     – breath waveform variation
      [30] motion_score (mean) – composite body movement
      [31] rr_bpm (mean)       – respiration rate
      [33] epoch_energy        – overall signal power (RMS)

Body-state labels:
    Active                  – significant body movement
    Restless                – minor / moderate movement
    Still – Normal Breathing  – calm, healthy breath signal detected
    Still – Shallow Breathing – calm, very weak breath signal
    Still – Irregular         – calm, RR outside normal range
"""

from __future__ import annotations
import os, joblib
import numpy as np
from typing import Dict, List, Optional, Tuple

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix

from . import config as CFG
from .features import FEATURE_DIM

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


# ────────────────────────────────────────────────────────────────────
#  SYNTHETIC DATA GENERATOR  (for training when no labelled data)
# ────────────────────────────────────────────────────────────────────

def _generate_synthetic_posture_data(
    n_per_class: int = 500,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic feature vectors that mimic radar‑derived
    posture signatures.

    Each posture class has characteristic patterns:
      * **Supine** – larger chest displacement amplitude, symmetric
        breathing, moderate range (~0.3–0.5 m)
      * **Left Lateral** – asymmetric chest signal (left shift bias),
        slightly reduced breath amplitude, range shifted
      * **Right Lateral** – mirror of left lateral
      * **Prone** – reduced breath amplitude, higher heart signal
        variability, shorter range
      * **Unknown** – high noise / no clear pattern

    Returns (X, y) with X shape (n_per_class*5, FEATURE_DIM).
    """
    rng = np.random.RandomState(seed)
    X_parts, y_parts = [], []

    label_map = {0: "Supine", 1: "Left Lateral", 2: "Right Lateral",
                 3: "Prone", 4: "Unknown"}

    for cls_id in range(5):
        n = n_per_class
        feats = np.zeros((n, FEATURE_DIM))

        # ── Base statistics (30 features: 6 stats × 5 signals) ─────
        #  Index layout per signal: [mean, std, min, max, skew, kurt]
        #  Signals: chest_disp(0‑5), breath(6‑11), heart(12‑17),
        #           combined(18‑23), range(24‑29)

        if cls_id == 0:  # SUPINE
            feats[:, 0]  = rng.normal(0.0, 0.05, n)        # chest mean ~0
            feats[:, 1]  = rng.uniform(0.5, 1.0, n)         # chest std high
            feats[:, 4]  = rng.normal(0.0, 0.3, n)          # chest skew ~0
            feats[:, 6]  = rng.normal(0.0, 0.05, n)         # breath mean
            feats[:, 7]  = rng.uniform(0.4, 0.9, n)         # breath std
            feats[:, 12] = rng.normal(0.0, 0.05, n)         # heart mean
            feats[:, 13] = rng.uniform(0.2, 0.5, n)         # heart std
            feats[:, 24] = rng.uniform(0.3, 0.5, n)         # range mean
            feats[:, 25] = rng.uniform(0.01, 0.05, n)       # range std

        elif cls_id == 1:  # LEFT LATERAL
            feats[:, 0]  = rng.normal(-0.15, 0.08, n)       # chest bias left
            feats[:, 1]  = rng.uniform(0.3, 0.7, n)
            feats[:, 4]  = rng.normal(-0.5, 0.3, n)         # negative skew
            feats[:, 6]  = rng.normal(-0.05, 0.05, n)
            feats[:, 7]  = rng.uniform(0.3, 0.6, n)
            feats[:, 12] = rng.normal(0.0, 0.08, n)
            feats[:, 13] = rng.uniform(0.15, 0.4, n)
            feats[:, 24] = rng.uniform(0.35, 0.6, n)        # range shifted
            feats[:, 25] = rng.uniform(0.02, 0.07, n)

        elif cls_id == 2:  # RIGHT LATERAL
            feats[:, 0]  = rng.normal(0.15, 0.08, n)        # chest bias right
            feats[:, 1]  = rng.uniform(0.3, 0.7, n)
            feats[:, 4]  = rng.normal(0.5, 0.3, n)          # positive skew
            feats[:, 6]  = rng.normal(0.05, 0.05, n)
            feats[:, 7]  = rng.uniform(0.3, 0.6, n)
            feats[:, 12] = rng.normal(0.0, 0.08, n)
            feats[:, 13] = rng.uniform(0.15, 0.4, n)
            feats[:, 24] = rng.uniform(0.35, 0.6, n)
            feats[:, 25] = rng.uniform(0.02, 0.07, n)

        elif cls_id == 3:  # PRONE
            feats[:, 0]  = rng.normal(0.0, 0.03, n)
            feats[:, 1]  = rng.uniform(0.15, 0.4, n)        # reduced chest
            feats[:, 4]  = rng.normal(0.0, 0.2, n)
            feats[:, 6]  = rng.normal(0.0, 0.03, n)
            feats[:, 7]  = rng.uniform(0.15, 0.35, n)       # reduced breath
            feats[:, 12] = rng.normal(0.0, 0.1, n)
            feats[:, 13] = rng.uniform(0.3, 0.7, n)         # heart more variable
            feats[:, 24] = rng.uniform(0.2, 0.38, n)        # closer range
            feats[:, 25] = rng.uniform(0.01, 0.04, n)

        else:  # UNKNOWN (noisy / ambiguous)
            feats[:, :30] = rng.normal(0, 0.3, (n, 30))
            feats[:, 24]  = rng.uniform(0.1, 0.8, n)

        # ── Fill remaining stat slots with noise ────────────────────
        for sig_start in range(0, 30, 6):
            # min, max (indices 2, 3)
            feats[:, sig_start + 2] += feats[:, sig_start] - np.abs(rng.normal(0, 0.3, n))
            feats[:, sig_start + 3] += feats[:, sig_start] + np.abs(rng.normal(0, 0.3, n))
            # kurtosis (index 5)
            feats[:, sig_start + 5] = rng.normal(0, 1.5, n)

        # ── Extra features (indices 30‑33) ──────────────────────────
        feats[:, 30] = rng.uniform(0, 0.15, n)              # motion score (low = sleep)
        feats[:, 31] = rng.uniform(10, 22, n)               # RR BPM
        feats[:, 32] = rng.uniform(55, 90, n)               # HR BPM
        feats[:, 33] = rng.uniform(0.1, 0.8, n)             # epoch energy

        X_parts.append(feats)
        y_parts.append(np.full(n, cls_id, dtype=int))

    X = np.vstack(X_parts)
    y = np.concatenate(y_parts)

    # add global noise
    X += rng.normal(0, 0.02, X.shape)

    return X, y


# ────────────────────────────────────────────────────────────────────
#  TRAIN POSTURE CLASSIFIER
# ────────────────────────────────────────────────────────────────────

def train_posture_classifier(
    X: Optional[np.ndarray] = None,
    y: Optional[np.ndarray] = None,
    save_path: Optional[str] = None,
    n_estimators: int = 200,
    seed: int = 42,
    test_size: float = 0.2,
) -> Dict:
    """
    Train a Random Forest posture classifier.

    If X/y are None, synthetic data is generated automatically.

    Parameters
    ──────────
    X          : feature matrix (n_samples, FEATURE_DIM)
    y          : integer labels 0–4
    save_path  : path to save the joblib model (default: module dir)
    n_estimators, seed, test_size : RF hyperparameters

    Returns
    ───────
    result : dict with "model", "accuracy", "report", "confusion"
    """
    if X is None or y is None:
        X, y = _generate_synthetic_posture_data(seed=seed)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=seed, stratify=y,
    )

    clf = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=15,
        min_samples_leaf=5,
        random_state=seed,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    report = classification_report(
        y_test, y_pred,
        target_names=CFG.POSTURE_LABELS,
        output_dict=True,
    )
    cm = confusion_matrix(y_test, y_pred)

    if save_path is None:
        save_path = os.path.join(MODULE_DIR, CFG.POSTURE_MODEL_FILE)
    joblib.dump(clf, save_path)

    return {
        "model": clf,
        "accuracy": acc,
        "report": report,
        "confusion": cm.tolist(),
        "model_path": save_path,
    }


# ────────────────────────────────────────────────────────────────────
#  LOAD MODEL
# ────────────────────────────────────────────────────────────────────

def load_posture_model(path: Optional[str] = None) -> RandomForestClassifier:
    """Load a previously trained posture model from disk."""
    if path is None:
        path = os.path.join(MODULE_DIR, CFG.POSTURE_MODEL_FILE)
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Posture model not found at {path}. "
            "Run train_posture_classifier() first."
        )
    return joblib.load(path)


# ────────────────────────────────────────────────────────────────────
#  PREDICT POSTURE
# ────────────────────────────────────────────────────────────────────

# ── Feature-vector index constants (from features.py layout) ────────
_I_CHEST_STD  = 1   # chest displacement std  → breathing amplitude
_I_BREATH_STD = 7   # breath waveform std     → breath variation
_I_MOTION     = 30  # composite motion score  → body movement
_I_RR_BPM     = 31  # mean respiration rate   → breathing rate
_I_ENERGY     = 33  # epoch RMS energy        → overall signal power

# ── Thresholds (tunable) ─────────────────────────────────────────────
_ACTIVE_MOTION    = 0.35   # motion ≥ this → Active
_RESTLESS_MOTION  = 0.10   # motion ≥ this → Restless
_SHALLOW_BREATH   = 0.03   # breath_std below this → shallow signal
_SHALLOW_ENERGY   = 0.05   # epoch energy below this → shallow signal
_RR_LOW           = 6      # BPM < this while still → irregular (or 0 = no reading)
_RR_HIGH          = 30     # BPM > this while still → irregular


def predict_posture(
    X: np.ndarray,
    model=None,                          # kept for API compatibility; unused
    confidence_min: float = CFG.POSTURE_CONFIDENCE_MIN,
) -> Tuple[List[str], np.ndarray]:
    """
    Rule-based body-state classification from real radar features.

    Uses the actual measured values in the feature vector — no ML model
    or synthetic data involved. The radar physically cannot distinguish
    lateral/supine/prone postures from a standard forward-facing setup,
    so we report what it *can* reliably measure.

    Parameters
    ──────────
    X    : (n_epochs, 34) feature matrix from extract_all_features()
    model, confidence_min : kept for API compatibility; ignored

    Returns
    ───────
    labels      : list[str] body-state label per epoch
    confidences : (n_epochs,) float array, 0–1 rule confidence
    """
    labels: List[str] = []
    confs:  List[float] = []

    for feat in X:
        motion    = float(feat[_I_MOTION])     if len(feat) > _I_MOTION  else 0.0
        rr_bpm    = float(feat[_I_RR_BPM])     if len(feat) > _I_RR_BPM  else 0.0
        breath_std= float(feat[_I_BREATH_STD]) if len(feat) > _I_BREATH_STD else 0.0
        energy    = float(feat[_I_ENERGY])     if len(feat) > _I_ENERGY   else 0.0

        if motion >= _ACTIVE_MOTION:
            labels.append("Active")
            confs.append(min(1.0, motion / 0.65))  # scales with how active

        elif motion >= _RESTLESS_MOTION:
            labels.append("Restless")
            confs.append(0.75)

        else:
            # Body is still — classify by breathing signal quality
            rr_valid = rr_bpm > 0  # 0 means sensor had no reading
            breath_weak = (breath_std < _SHALLOW_BREATH) and (energy < _SHALLOW_ENERGY)
            rr_irregular = rr_valid and (rr_bpm < _RR_LOW or rr_bpm > _RR_HIGH)

            if breath_weak:
                labels.append("Still \u2013 Shallow Breathing")
                confs.append(0.80)
            elif rr_irregular:
                labels.append("Still \u2013 Irregular")
                confs.append(0.70)
            else:
                labels.append("Still \u2013 Normal Breathing")
                confs.append(0.85)

    return labels, np.array(confs, dtype=float)


# ────────────────────────────────────────────────────────────────────
#  HEURISTIC FALLBACK  (no ML)
# ────────────────────────────────────────────────────────────────────

def heuristic_posture(
    chest_disp: np.ndarray,
    breath_wave: np.ndarray,
    range_m: np.ndarray,
    start: int,
    end: int,
) -> str:
    """
    Simple rule‑based posture estimate as a fallback when the ML
    model is not available or confidence is too low.

    Rules:
        • High chest amplitude + symmetric skew → Supine
        • Negative chest skew → Left Lateral
        • Positive chest skew → Right Lateral
        • Low breath amplitude + close range → Prone
        • Otherwise → Unknown
    """
    cd = chest_disp[start:end]
    bw = breath_wave[start:end]
    rn = range_m[start:end]

    if len(cd) < 10:
        return "Unknown"

    from scipy.stats import skew as sk
    chest_skew = float(sk(cd, nan_policy="omit"))
    chest_amp = float(np.std(cd))
    breath_amp = float(np.std(bw))
    avg_range = float(np.mean(rn))

    # Prone: low breath + close range
    if breath_amp < 0.2 and avg_range < 0.35:
        return "Prone"

    # Lateral: asymmetric chest
    if chest_skew < -0.5:
        return "Left Lateral"
    if chest_skew > 0.5:
        return "Right Lateral"

    # Supine: high chest amplitude, symmetric
    if chest_amp > 0.3 and abs(chest_skew) < 0.4:
        return "Supine"

    return "Unknown"
