"""
sleep_staging/config.py
───────────────────────
Default configurable parameters for the sleep‑stage classification
pipeline.  All values may be overridden at runtime via keyword
arguments.
"""

# ── Epoch / windowing ───────────────────────────────────────────────
EPOCH_DURATION_SEC = 30          # PSG‑standard 30‑second epoch
EPOCH_OVERLAP_FRAC = 0.0        # 0 = no overlap for staging
SAMPLING_RATE      = 20.0       # 20 Hz default (radar)

# ── Sleep‑stage labels ─────────────────────────────────────────────
# Reduced set (default)
STAGE_LABELS_REDUCED = ["Wake", "REM", "Light", "Deep"]
# Full PSG set (optional)
STAGE_LABELS_FULL    = ["Wake", "N1", "N2", "N3", "REM"]

# Which label set to use by default
USE_FULL_STAGES = False

# Integer encoding for reduced set
STAGE_ENCODING_REDUCED = {"Wake": 0, "REM": 1, "Light": 2, "Deep": 3}
STAGE_ENCODING_FULL    = {"Wake": 0, "N1": 1, "N2": 2, "N3": 3, "REM": 4}

# ── Feature extraction ─────────────────────────────────────────────
# Statistical features per signal per epoch
STAT_FEATURES = ["mean", "median", "std", "var", "min", "max",
                 "skew", "kurtosis", "slope", "iqr"]

# HRV features (if HR available)
HRV_FEATURES = ["hrv_sdnn", "hrv_rmssd", "hrv_range"]

# Respiratory variability features
RRV_FEATURES = ["rrv_sdnn", "rrv_rmssd", "rrv_range"]

# Motion features
MOTION_FEATURES = ["motion_mean", "motion_max", "motion_std",
                   "motion_spikes", "motion_fraction_still"]

# Posture features
POSTURE_FEATURES = ["posture_changes", "posture_stability"]

# Event features
EVENT_FEATURES = ["event_count_irregular", "event_count_apnea",
                  "event_count_motion"]

# ── Model defaults ─────────────────────────────────────────────────
DEFAULT_MODEL_TYPE   = "random_forest"   # random_forest | svm | xgboost | lstm | cnn_lstm | tcn
DEFAULT_N_ESTIMATORS = 300
DEFAULT_MAX_DEPTH    = 20
DEFAULT_SVM_C        = 10.0
DEFAULT_SVM_KERNEL   = "rbf"

# XGBoost
XGB_N_ESTIMATORS = 300
XGB_MAX_DEPTH    = 8
XGB_LEARNING_RATE = 0.1

# Deep learning
DL_SEQUENCE_LEN   = 10     # number of past epochs as sequence input
DL_HIDDEN_DIM     = 64
DL_DROPOUT        = 0.3
DL_EPOCHS         = 50
DL_BATCH_SIZE     = 32
DL_LEARNING_RATE  = 1e-3

# ── Training ───────────────────────────────────────────────────────
TEST_SIZE           = 0.20
CV_FOLDS            = 5
RANDOM_SEED         = 42

# ── Synthetic data generation ──────────────────────────────────────
SYNTHETIC_SAMPLES_PER_CLASS = 600
SYNTHETIC_NIGHT_CYCLES      = 4     # typical sleep cycles per night

# ── Model persistence ──────────────────────────────────────────────
MODEL_FILE_TEMPLATE = "sleep_stage_{model_type}.joblib"

# ── Severity / structure thresholds ─────────────────────────────────
SLEEP_EFFICIENCY_THRESHOLDS = {
    "Good":     0.85,      # ≥85 % time asleep
    "Fair":     0.75,
    "Poor":     0.0,
}

# Typical proportions for a healthy adult (reference only)
REFERENCE_STAGE_PROPORTIONS = {
    "Wake":  0.05,
    "REM":   0.20,
    "Light": 0.50,
    "Deep":  0.25,
}
