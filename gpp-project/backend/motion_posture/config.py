"""
motion_posture/config.py
────────────────────────
Default configurable parameters for the motion & posture context
pipeline.  All values can be overridden at runtime via keyword
arguments.
"""

# ── Epoch / windowing ───────────────────────────────────────────────
EPOCH_DURATION_SEC = 15          # seconds per analysis window
EPOCH_OVERLAP_FRAC = 0.50       # 50 % overlap

# ── Motion classification thresholds ─────────────────────────────────
# Normalised motion score ranges  (0 = perfectly still, 1 = max motion)
MOTION_STILL_MAX       = 0.10   # ≤ this → "Still"
MOTION_MINOR_MAX       = 0.35   # ≤ this → "Minor Movement"
MOTION_MAJOR_MAX       = 0.65   # ≤ this → "Major Movement"
# above MOTION_MAJOR_MAX         → "Turning"

MOTION_LABELS = ["Still", "Minor Movement", "Major Movement", "Turning"]

# ── Body-state classification (what radar can actually measure) ─────
# Labels derived from motion score + breathing amplitude — no ML model needed.
POSTURE_LABELS = [
    "Active",                  # significant body movement
    "Restless",                # minor/moderate movement
    "Still – Normal Breathing", # calm, good breathing signal
    "Still – Shallow Breathing",# calm but very weak breath signal
    "Still – Irregular",       # calm but RR out of normal range
]
POSTURE_MODEL_FILE = "posture_model.joblib"  # kept for compatibility
POSTURE_CONFIDENCE_MIN = 0.35    # unused (rule-based), kept for imports

# ── Feature extraction ──────────────────────────────────────────────
# Number of statistical features extracted per window for posture model
#  (mean, std, min, max, skew, kurtosis) × (chest_disp, breath_wave,
#   heart_wave, combined, range_m)  = 6 × 5 = 30 features + extras
N_FEATURE_SIGNALS = 5
N_STAT_FEATURES   = 6
EXTRA_FEATURES    = 4            # motion_score, rr_bpm, hr_bpm, epoch_energy

# ── Context fusion ──────────────────────────────────────────────────
EVENT_LOOK_BACK_SEC  = 30        # seconds before an event to look for motion
EVENT_LOOK_AHEAD_SEC = 10        # seconds after an event to look for motion

# ── Severity heuristics ─────────────────────────────────────────────
# Apnea-risk weighting by body state (rule-based labels)
POSTURE_RISK = {
    "Active":                   0.3,  # moving → unlikely sustained apnea
    "Restless":                 0.4,
    "Still – Normal Breathing": 0.5,
    "Still – Shallow Breathing": 0.9, # low breath amplitude → higher risk
    "Still – Irregular":        0.8,
}
