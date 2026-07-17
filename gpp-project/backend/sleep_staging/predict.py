"""
sleep_staging/predict.py
────────────────────────
Inference pipeline – classify activity states from radar feature data.

Instead of a model trained on synthetic data that cannot be validated,
we use a rule-based classifier derived from real radar-measurable
physiological signals.

Feature vector layout (56 features, from features.py):
  [0]   RR mean BPM                  [2]  RR std
  [10]  HR mean BPM                  [12] HR std
  [40]  RRV sdnn (breathing variability)
  [43]  HRV sdnn (heart-rate variability)
  [46]  motion mean score            [47] motion max
  [50]  fraction_still               [49] motion spike count

Stage classification rules (4 levels, matching frontend labels):
  Wake  – significant motion, OR physiologically elevated HR/RR
  REM   – still body but irregular breathing (high RRV) – closest radar proxy
  Light – calm, normal-range breathing and HR (transitional)
  Deep  – very still, slow regular breathing, low HR
"""

from __future__ import annotations
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from . import config as CFG
from .features import extract_all_features, FEATURE_DIM
from .models_classical import load_model as load_classical
from .models_deep import is_available as tf_available, load_deep_model
from .training import build_sequences

from sklearn.preprocessing import StandardScaler


# ── Feature-vector index constants (from features.py layout) ────────
_I_RR_MEAN    = 0    # mean respiration rate (BPM)
_I_RR_STD     = 2    # RR standard deviation
_I_HR_MEAN    = 10   # mean heart rate (BPM)
_I_BREATH_STD = 32   # breath waveform std → breathing amplitude
_I_RRV_SDNN   = 40   # breathing-rate variability (SDNN)
_I_MOT_MEAN   = 46   # motion score mean
_I_MOT_MAX    = 47   # motion score max
_I_MOT_STD    = 48   # motion score std
_I_MOT_SPIKES = 49   # motion spike count (motion > 0.5)
_I_FRAC_STILL = 50   # fraction-still per epoch

# ── Thresholds (tunable per sensor setup) ───────────────────────────
_WAKE_MOTION     = 0.55   # sustained motion mean needed for Wake
_WAKE_MOTION_SPIKE = 360  # absolute spike count from feature extractor is large; use high cutoff
_WAKE_RR_HIGH    = 23     # RR above this → likely awake
_WAKE_RR_LOW     = 7      # RR below this → sensor noise / awake
_WAKE_HR         = 85     # HR above this → awake
_DEEP_FRAC_STILL = 0.80   # very still for Deep
_DEEP_RR_MAX     = 16     # slow breathing for Deep
_DEEP_RR_MIN     = 7      # not too slow (avoids sensor noise)
_DEEP_RR_STD_MAX = 3.0    # regular breathing for Deep
_DEEP_HR_MAX     = 65     # low HR for Deep (0 = HR unavailable)
_REM_FRAC_STILL  = 0.75   # still body for REM proxy
_REM_RRV_MIN     = 2.0    # very irregular breathing → REM proxy (high threshold)


def _classify_epoch(feat: np.ndarray) -> Tuple[str, float]:
    """
    Classify one epoch into Wake / REM / Light / Deep using real radar signals.
    Returns (label, confidence 0-1).
    
    Key improvements:
    - Motion spikes are strong indicators of wakefulness (alert movements)
    - Lower motion threshold catches subtle awake movements (sitting still)
    - Lower HR threshold for better sensitivity to calm wakefulness
    """
    def _f(idx: int) -> float:
        return float(feat[idx]) if len(feat) > idx else 0.0

    rr_mean    = _f(_I_RR_MEAN)
    rr_std     = _f(_I_RR_STD)
    hr_mean    = _f(_I_HR_MEAN)
    rrv_sdnn   = _f(_I_RRV_SDNN)
    mot_mean   = _f(_I_MOT_MEAN)
    mot_max    = _f(_I_MOT_MAX)
    mot_spikes = _f(_I_MOT_SPIKES)
    frac_still = _f(_I_FRAC_STILL)

    # 1. Wake – require strong or combined evidence to avoid "all Wake" bias
    rr_valid   = rr_mean > 0

    wake_spikes = (mot_spikes >= _WAKE_MOTION_SPIKE) and (mot_max >= 0.95) and (mot_mean >= 0.50)
    wake_motion = (mot_mean >= _WAKE_MOTION) and (mot_max >= 0.90 or mot_spikes >= 5)
    wake_rr     = rr_valid and (rr_mean > _WAKE_RR_HIGH or rr_mean < _WAKE_RR_LOW)
    wake_hr     = hr_mean > _WAKE_HR
    wake_combo  = rr_valid and (hr_mean >= 74) and (rr_mean >= 16)

    # Hard wake: very high physiology or strong movement events.
    hard_wake = (wake_spikes and mot_mean >= 0.58) or wake_combo or hr_mean >= 95 or (rr_valid and rr_mean >= 26)

    # Soft wake requires at least two indicators (prevents false positives from noisy motion).
    indicators = sum([wake_motion, wake_rr, wake_hr, wake_combo])
    if hard_wake or indicators >= 2:
        conf = float(np.clip(
            0.35 * min(1.0, mot_mean / max(_WAKE_MOTION, 1e-6)) +
            0.25 * (1.0 if wake_hr else 0.0) +
            0.20 * (1.0 if wake_rr else 0.0) +
            0.20 * (1.0 if wake_spikes else 0.0),
            0.58, 0.96
        ))
        return "Wake", conf

    # 2. Deep – slow regular breathing + low HR (stillness can be noisy in radar)
    rr_in_deep = (not rr_valid) or (_DEEP_RR_MIN <= rr_mean <= _DEEP_RR_MAX)
    rr_regular = rr_std < _DEEP_RR_STD_MAX
    hr_low     = hr_mean == 0 or hr_mean < _DEEP_HR_MAX

    deep_physio = rr_valid and (10.0 <= rr_mean <= 13.2) and (rr_std <= 1.4) and (hr_mean == 0 or hr_mean <= 60.5)

    if (frac_still >= _DEEP_FRAC_STILL and rr_in_deep and rr_regular and hr_low) or deep_physio:
        still_f = (frac_still - _DEEP_FRAC_STILL) / (1.0 - _DEEP_FRAC_STILL)
        reg_f   = max(0.0, 1.0 - rr_std / _DEEP_RR_STD_MAX)
        phys_f  = 1.0 if deep_physio else 0.0
        conf    = float(np.clip(0.2 * still_f + 0.4 * reg_f + 0.4 * phys_f, 0.55, 0.92))
        return "Deep", conf

    # 3. REM proxy – irregular breathing + moderate HR in plausible REM band
    rem_physio = rr_valid and (12.0 <= rr_mean <= 17.5) and (hr_mean >= 62) and (hr_mean <= 74) and (rrv_sdnn >= 0.55)
    if (frac_still >= _REM_FRAC_STILL and rrv_sdnn >= _REM_RRV_MIN) or rem_physio:
        conf = float(np.clip(0.45 + 0.3 * min(1.0, rrv_sdnn / 1.2) + 0.25 * (1.0 if rem_physio else 0.0), 0.50, 0.88))
        return "REM", conf

    # 4. Light – default: low motion, normal physiology (but not fully asleep)
    return "Light", 0.65


# ────────────────────────────────────────────────────────────────────
#  TEMPORAL SMOOTHING (Post-processing)
# ────────────────────────────────────────────────────────────────────

def _apply_temporal_smoothing(
    labels: List[str],
    proba: np.ndarray,
    window_size: int = 3,
) -> List[str]:
    """
    Apply temporal smoothing to reduce isolated misclassifications.
    
    Uses a sliding window majority vote:
    - If an epoch is isolated (different from neighbors), reconsider using confidence
    - Prevents false "Light" classification when surrounded by "Wake"
    - Preserves transitions between sleep stages
    
    Args:
    ─────
    labels       : predicted labels per epoch
    proba        : confidence matrix (n_epochs, 4)
    window_size  : size of smoothing window (default 3)
    
    Returns
    ───────
    smoothed labels with reduced isolated misclassifications
    """
    smoothed = labels.copy()
    label_names = ["Wake", "REM", "Light", "Deep"]
    label_idx = {l: i for i, l in enumerate(label_names)}
    half_window = window_size // 2
    
    for i in range(len(labels)):
        # Get neighbors within window
        start = max(0, i - half_window)
        end = min(len(labels), i + half_window + 1)
        neighbors = labels[start:end]
        
        # Count stage occurrences (excluding current epoch for tie-breaking)
        neighbor_labels = [l for j, l in enumerate(neighbors) if j != (i - start)]
        if not neighbor_labels:
            continue
            
        # Check if current epoch is isolated (different from all neighbors)
        from collections import Counter
        counts = Counter(neighbor_labels)
        most_common_stage, count = counts.most_common(1)[0]
        
        # Reclassify if very different from neighbors AND confidence is low
        current_conf = np.max(proba[i])
        
        # If Wake is the most common around us and we're classified as Light/REM
        # with low confidence, reconsider
        if labels[i] in ["Light", "REM"] and most_common_stage == "Wake":
            min_votes = max(2, half_window + 1)
            if count >= min_votes and current_conf < 0.72:
                smoothed[i] = "Wake"
        
        # Similarly, strong indication of Deep sleep (multiple Deep epochs)
        # overrides isolated Light/REM classifications
        elif labels[i] in ["Light", "REM"] and most_common_stage == "Deep":
            min_votes = max(2, half_window + 1)
            if count >= min_votes and current_conf < 0.68:
                smoothed[i] = "Deep"
    
    return smoothed


# ────────────────────────────────────────────────────────────────────
#  PREDICT (RULE-BASED)
# ────────────────────────────────────────────────────────────────────

def predict_sleep_stages(
    X: np.ndarray,
    model: Optional[Any] = None,
    model_type: str = CFG.DEFAULT_MODEL_TYPE,
    use_full_stages: bool = CFG.USE_FULL_STAGES,
) -> Tuple[List[str], np.ndarray]:
    """
    Rule-based activity-state classification from radar feature vectors.

    `model`, `model_type`, `use_full_stages` kept for API compatibility only.
    Classification is driven entirely by physical radar measurements via
    `_classify_epoch()`.

    Returns
    ───────
    labels      : list[str]  one of {Wake, REM, Light, Deep} per epoch
    confidences : (n_epochs, 4) soft probability matrix
    """
    label_names = ["Wake", "REM", "Light", "Deep"]
    label_idx   = {l: i for i, l in enumerate(label_names)}
    n_classes   = len(label_names)

    labels: List[str] = []
    proba = np.zeros((len(X), n_classes), dtype=float)

    for i, feat in enumerate(X):
        lbl, conf = _classify_epoch(feat)
        labels.append(lbl)
        row = np.full(n_classes, (1.0 - conf) / max(n_classes - 1, 1))
        row[label_idx[lbl]] = conf
        proba[i] = row

    return labels, proba


# ────────────────────────────────────────────────────────────────────
#  PREDICT (DEEP)  — falls back to rule-based when TF unavailable
# ────────────────────────────────────────────────────────────────────

def predict_sleep_stages_deep(
    X: np.ndarray,
    model: Optional[Any] = None,
    model_type: str = "lstm",
    scaler: Optional[StandardScaler] = None,
    use_full_stages: bool = CFG.USE_FULL_STAGES,
) -> Tuple[List[str], np.ndarray]:
    """
    Predict sleep stages using a deep learning model.

    Parameters
    ──────────
    X           : (n_epochs, FEATURE_DIM) feature matrix
    model       : trained Keras model (loads from disk if None)
    model_type  : model name for loading
    scaler      : fitted StandardScaler (applies before sequence building)
    use_full_stages : label set

    Returns
    ───────
    labels      : list[str]
    confidences : (n_epochs, n_classes) after aligning back to epoch count
    """
    if not tf_available():
        # Rule-based fallback (always available)
        return predict_sleep_stages(X, use_full_stages=use_full_stages)

    label_names = CFG.STAGE_LABELS_FULL if use_full_stages else CFG.STAGE_LABELS_REDUCED

    if model is None:
        model = load_deep_model(model_type)

    if scaler is not None:
        X_scaled = scaler.transform(X)
    else:
        sc = StandardScaler()
        X_scaled = sc.fit_transform(X)

    seq_len = CFG.DL_SEQUENCE_LEN
    X_seq, _ = build_sequences(X_scaled, np.zeros(len(X_scaled), dtype=int), seq_len)

    proba = model.predict(X_seq, verbose=0)
    pred_ids = np.argmax(proba, axis=1)

    # The first (seq_len - 1) epochs don't have predictions → pad with first prediction
    n_original = X.shape[0]
    n_predicted = len(pred_ids)
    pad_count = n_original - n_predicted

    if pad_count > 0:
        padded_ids = np.concatenate([np.full(pad_count, pred_ids[0]), pred_ids])
        padded_proba = np.vstack([np.tile(proba[0], (pad_count, 1)), proba])
    else:
        padded_ids = pred_ids
        padded_proba = proba

    labels = [label_names[pid] for pid in padded_ids[:n_original]]
    return labels, padded_proba[:n_original]


# ────────────────────────────────────────────────────────────────────
#  FULL PREDICTION PIPELINE
# ────────────────────────────────────────────────────────────────────

def run_prediction(
    data: Dict[str, np.ndarray],
    model: Optional[Any] = None,
    model_type: str = CFG.DEFAULT_MODEL_TYPE,
    use_full_stages: bool = CFG.USE_FULL_STAGES,
    sleep_events: Optional[List[Dict]] = None,
    posture_epoch_map: Optional[Dict[int, str]] = None,
    sampling_rate: float = CFG.SAMPLING_RATE,
    epoch_duration_sec: float = CFG.EPOCH_DURATION_SEC,
    epoch_overlap_frac: float = CFG.EPOCH_OVERLAP_FRAC,
) -> Dict:
    """
    End‑to‑end prediction: data → features → predict → structured output.

    Returns dict with:
        "epoch_records", "labels", "confidences", "epoch_centers",
        "sleep_structure"
    """
    # Rule-based: always uses 4 labels regardless of use_full_stages
    label_names = ["Wake", "REM", "Light", "Deep"]

    X, indices, epoch_centers = extract_all_features(
        data, sampling_rate, epoch_duration_sec, epoch_overlap_frac,
        sleep_events=sleep_events,
        posture_epoch_map=posture_epoch_map,
    )

    if X.shape[0] == 0:
        return {
            "epoch_records": [],
            "labels": [],
            "confidences": np.empty((0, len(label_names))),
            "epoch_centers": np.array([]),
            "sleep_structure": _empty_structure(label_names),
        }

    # Always use rule-based classifier (works without any trained model)
    labels, proba = predict_sleep_stages(X)
    
    # Apply temporal smoothing to reduce false positives/negatives
    labels = _apply_temporal_smoothing(labels, proba)

    # Build epoch records
    timestamps = data["timestamps"]
    n = len(timestamps)
    records: List[Dict] = []

    for k, (s, e) in enumerate(indices):
        ts_s = float(timestamps[s])
        ts_e = float(timestamps[min(e - 1, n - 1)])
        rec = {
            "epoch_index": k,
            "timestamp_start": round(ts_s, 3),
            "timestamp_end": round(ts_e, 3),
            "predicted_stage": labels[k],
            "confidence": round(float(np.max(proba[k])), 4),
            "probabilities": {label_names[c]: round(float(proba[k, c]), 4)
                              for c in range(proba.shape[1])},
        }
        records.append(rec)

    # Sleep structure summary
    structure = _compute_sleep_structure(labels, epoch_duration_sec, label_names)

    return {
        "epoch_records": records,
        "labels": labels,
        "confidences": proba,
        "epoch_centers": epoch_centers,
        "sleep_structure": structure,
    }


# ────────────────────────────────────────────────────────────────────
#  SLEEP STRUCTURE
# ────────────────────────────────────────────────────────────────────

def _compute_sleep_structure(
    labels: List[str],
    epoch_sec: float,
    label_names: List[str],
) -> Dict:
    """Aggregate sleep architecture statistics."""
    from collections import Counter

    total_epochs = len(labels)
    total_sec = total_epochs * epoch_sec

    counts = Counter(labels)
    time_per_stage = {s: counts.get(s, 0) * epoch_sec for s in label_names}
    pct_per_stage = {s: round(100 * counts.get(s, 0) / max(total_epochs, 1), 1)
                     for s in label_names}

    # Sleep efficiency: time asleep / total time
    sleep_stages = [s for s in label_names if s != "Wake"]
    sleep_epoch_count = sum(counts.get(s, 0) for s in sleep_stages)
    sleep_efficiency = sleep_epoch_count / max(total_epochs, 1)

    # Sleep onset latency: epochs until first non-Wake
    sol_epochs = 0
    for lbl in labels:
        if lbl == "Wake":
            sol_epochs += 1
        else:
            break

    # Sleep cycles (approximate: transitions Wake/REM→Deep→Light→REM)
    n_rem_episodes = 0
    in_rem = False
    for lbl in labels:
        if lbl == "REM" and not in_rem:
            n_rem_episodes += 1
            in_rem = True
        elif lbl != "REM":
            in_rem = False

    # Efficiency rating
    efficiency_label = "Poor"
    for rating, thresh in sorted(CFG.SLEEP_EFFICIENCY_THRESHOLDS.items(),
                                  key=lambda x: -x[1]):
        if sleep_efficiency >= thresh:
            efficiency_label = rating
            break

    return {
        "total_epochs": total_epochs,
        "total_duration_sec": round(total_sec, 1),
        "total_duration_min": round(total_sec / 60, 1),
        "time_per_stage_sec": time_per_stage,
        "pct_per_stage": pct_per_stage,
        "stage_counts": dict(counts),
        "sleep_efficiency": round(sleep_efficiency, 4),
        "sleep_efficiency_pct": round(sleep_efficiency * 100, 1),
        "efficiency_rating": efficiency_label,
        "sleep_onset_latency_sec": sol_epochs * epoch_sec,
        "rem_episodes": n_rem_episodes,
    }


def _empty_structure(label_names: List[str]) -> Dict:
    return {
        "total_epochs": 0,
        "total_duration_sec": 0,
        "total_duration_min": 0,
        "time_per_stage_sec": {s: 0 for s in label_names},
        "pct_per_stage": {s: 0 for s in label_names},
        "stage_counts": {},
        "sleep_efficiency": 0,
        "sleep_efficiency_pct": 0,
        "efficiency_rating": "N/A",
        "sleep_onset_latency_sec": 0,
        "rem_episodes": 0,
    }
