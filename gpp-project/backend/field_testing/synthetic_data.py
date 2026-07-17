"""
field_testing/synthetic_data.py
───────────────────────────────
Generate realistic synthetic field-test recordings so the pipeline
can be developed and tested without real hardware.

Each recording simulates one full-night session and contains:
  • epoch-level RR & HR (radar + ground-truth)
  • sleep event labels (Normal / Apnea-Hypopnea)
  • sleep stage labels (Wake / REM / Light / Deep)
  • motion index + posture labels

Environmental and placement conditions influence the noise
profile, bias, and dropout pattern.
"""

from __future__ import annotations
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

from . import config as CFG


# ── Placement-dependent noise / bias tables ────────────────────────
# (rr_bias, rr_noise_std, hr_bias, hr_noise_std, dropout_rate)
_PLACEMENT_NOISE: Dict[str, Tuple[float, float, float, float, float]] = {
    "bedside_left":      (0.0,  0.8,  0.0,  1.5,  0.02),
    "bedside_right":     (0.0,  0.8,  0.0,  1.5,  0.02),
    "foot_of_bed":       (0.3,  1.5,  0.5,  2.5,  0.05),
    "under_bed_center":  (0.1,  1.0,  0.2,  2.0,  0.03),
    "under_bed_torso":   (0.0,  0.7,  0.1,  1.8,  0.02),
    "corner_left":       (0.5,  2.0,  0.8,  3.5,  0.08),
    "corner_right":      (0.5,  2.0,  0.8,  3.5,  0.08),
    "ceiling_mount":     (0.2,  1.2,  0.3,  2.2,  0.04),
    "headboard":         (0.1,  0.9,  0.2,  1.8,  0.03),
    "nightstand":        (0.2,  1.1,  0.3,  2.0,  0.04),
}

# Bedding attenuation factors (multiplied onto noise std)
_BEDDING_ATTEN: Dict[str, float] = {
    "thin_sheet":       1.0,
    "single_blanket":   1.15,
    "duvet":            1.30,
    "weighted_blanket": 1.50,
    "comforter":        1.40,
}

# Occlusion dropout penalty (additive to base dropout rate)
_OCCLUSION_DROPOUT: Dict[str, float] = {
    "none":             0.00,
    "pillow_adjacent":  0.02,
    "side_table":       0.01,
    "headboard_only":   0.01,
    "partner_present":  0.05,
    "pet_present":      0.04,
    "fan_running":      0.03,
    "multiple_pillows": 0.03,
}


# ────────────────────────────────────────────────────────────────────
#  CORE GENERATOR
# ────────────────────────────────────────────────────────────────────

def generate_recording(
    test_config: Dict[str, Any],
    n_epochs: Optional[int] = None,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Generate a single synthetic recording based on a test config.

    Returns dict with keys:
        test_id, subject_id, config,
        rr_radar, rr_truth, hr_radar, hr_truth,
        event_pred, event_truth,
        stage_pred, stage_truth,
        motion_index, posture_pred, posture_truth
    """
    if seed is None:
        seed = abs(hash(test_config.get("test_id", ""))) % (2**31)
    rng = np.random.RandomState(seed)

    if n_epochs is None:
        dur = test_config.get("duration_sec", CFG.DEFAULT_RECORDING_DURATION_SEC)
        n_epochs = max(dur // CFG.EPOCH_DURATION_SEC, 120)

    placement = test_config.get("placement", "bedside_right")
    bedding   = test_config.get("bedding", "duvet")
    occlusions = test_config.get("occlusions", ["none"])

    rr_bias, rr_noise, hr_bias, hr_noise, dropout = _PLACEMENT_NOISE.get(
        placement, (0.2, 1.0, 0.3, 2.0, 0.04),
    )

    bed_atten = _BEDDING_ATTEN.get(bedding, 1.2)
    rr_noise *= bed_atten
    hr_noise *= bed_atten

    occ_drop = sum(_OCCLUSION_DROPOUT.get(o, 0.02) for o in occlusions)
    dropout += occ_drop

    # ── Ground-truth vital signs ───────────────────────────────────
    rr_truth = _generate_rr_truth(n_epochs, rng)
    hr_truth = _generate_hr_truth(n_epochs, rng)

    # ── Radar measurements (truth + bias + noise + dropout) ────────
    rr_radar = rr_truth + rr_bias + rng.normal(0, rr_noise, n_epochs)
    hr_radar = hr_truth + hr_bias + rng.normal(0, hr_noise, n_epochs)

    drop_mask = rng.random(n_epochs) < dropout
    rr_radar[drop_mask] = np.nan
    hr_radar[drop_mask] = np.nan

    # ── Sleep events ───────────────────────────────────────────────
    event_truth = _generate_events(n_epochs, rng)
    event_pred  = _corrupt_labels(event_truth, n_classes=2,
                                   error_rate=0.08 + dropout, rng=rng)

    # ── Sleep stages ───────────────────────────────────────────────
    stage_truth = _generate_stages(n_epochs, rng)
    stage_pred  = _corrupt_labels(stage_truth, n_classes=4,
                                   error_rate=0.12 + dropout, rng=rng)

    # ── Motion / posture ───────────────────────────────────────────
    motion_index = _generate_motion(n_epochs, stage_truth, rng)
    posture_truth = _generate_posture(n_epochs, rng)
    posture_pred  = _corrupt_labels(posture_truth, n_classes=4,
                                     error_rate=0.06 + dropout * 0.5,
                                     rng=rng)

    return {
        "test_id":       test_config.get("test_id", ""),
        "subject_id":    test_config.get("subject_id", ""),
        "config":        test_config,
        "n_epochs":      int(n_epochs),
        "rr_radar":      rr_radar,
        "rr_truth":      rr_truth,
        "hr_radar":      hr_radar,
        "hr_truth":      hr_truth,
        "event_pred":    event_pred,
        "event_truth":   event_truth,
        "stage_pred":    stage_pred,
        "stage_truth":   stage_truth,
        "motion_index":  motion_index,
        "posture_pred":  posture_pred,
        "posture_truth": posture_truth,
    }


def generate_batch(
    configs: List[Dict],
    seed: int = CFG.RANDOM_SEED,
    n_epochs: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Generate recordings for a list of configs."""
    recordings = []
    for i, cfg in enumerate(configs):
        rec = generate_recording(cfg, n_epochs=n_epochs,
                                 seed=seed + i)
        recordings.append(rec)
    return recordings


# ────────────────────────────────────────────────────────────────────
#  INTERNAL HELPERS
# ────────────────────────────────────────────────────────────────────

def _generate_rr_truth(n: int, rng: np.random.RandomState) -> np.ndarray:
    """Simulate ground-truth RR with ultradian variation."""
    base = 15.0
    # Slow drift (ultradian)
    t = np.arange(n)
    drift = 2.0 * np.sin(2 * np.pi * t / (90 * 2))  # ~90 min cycle
    noise = rng.normal(0, 0.5, n)
    rr = base + drift + noise
    return np.clip(rr, CFG.RR_NORMAL_RANGE[0], CFG.RR_NORMAL_RANGE[1])


def _generate_hr_truth(n: int, rng: np.random.RandomState) -> np.ndarray:
    """Simulate ground-truth HR with ultradian variation."""
    base = 62.0
    t = np.arange(n)
    drift = 5.0 * np.sin(2 * np.pi * t / (90 * 2) + 0.5)
    noise = rng.normal(0, 1.5, n)
    hr = base + drift + noise
    return np.clip(hr, CFG.HR_NORMAL_RANGE[0], CFG.HR_NORMAL_RANGE[1])


def _generate_events(n: int, rng: np.random.RandomState) -> np.ndarray:
    """Generate event labels with clustered apnea bursts."""
    events = np.zeros(n, dtype=int)
    i = 0
    while i < n:
        if rng.random() < 0.03:  # ~3 % chance of starting a burst
            burst_len = rng.randint(3, 12)
            end = min(i + burst_len, n)
            events[i:end] = 1
            i = end
        else:
            i += 1
    return events


def _generate_stages(n: int, rng: np.random.RandomState) -> np.ndarray:
    """
    Generate realistic sleep-stage hypnogram.

    Uses a simple Markov chain to produce realistic cycling.
    """
    # Transition matrix:  Wake(0) → REM(1) → Light(2) → Deep(3)
    P = np.array([
        [0.85, 0.03, 0.10, 0.02],  # Wake
        [0.05, 0.70, 0.20, 0.05],  # REM
        [0.04, 0.08, 0.72, 0.16],  # Light
        [0.02, 0.03, 0.20, 0.75],  # Deep
    ])

    stages = np.zeros(n, dtype=int)
    stages[0] = 0  # start awake
    for i in range(1, n):
        stages[i] = rng.choice(4, p=P[stages[i - 1]])
    return stages


def _generate_motion(
    n: int,
    stages: np.ndarray,
    rng: np.random.RandomState,
) -> np.ndarray:
    """Motion index depends on sleep stage."""
    motion = np.zeros(n)
    stage_motion = {0: 0.4, 1: 0.08, 2: 0.03, 3: 0.01}
    for i in range(n):
        base = stage_motion.get(int(stages[i]), 0.05)
        motion[i] = max(0, base + rng.normal(0, base * 0.5))
    return motion


def _generate_posture(n: int, rng: np.random.RandomState) -> np.ndarray:
    """Posture changes every ~30-90 min block."""
    posture = np.zeros(n, dtype=int)
    current = rng.randint(4)
    i = 0
    while i < n:
        block = rng.randint(60, 180)
        end = min(i + block, n)
        posture[i:end] = current
        current = rng.randint(4)
        i = end
    return posture


def _corrupt_labels(
    truth: np.ndarray,
    n_classes: int,
    error_rate: float,
    rng: np.random.RandomState,
) -> np.ndarray:
    """Flip a fraction of labels to simulate prediction errors."""
    pred = truth.copy()
    n = len(pred)
    n_flip = int(n * min(error_rate, 0.40))
    flip_idx = rng.choice(n, size=n_flip, replace=False)
    for idx in flip_idx:
        wrong = rng.randint(0, n_classes - 1)
        if wrong >= pred[idx]:
            wrong += 1
        pred[idx] = wrong % n_classes
    return pred
