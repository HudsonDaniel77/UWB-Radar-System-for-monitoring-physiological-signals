"""
ml_enhanced/config.py
─────────────────────
Default hyper-parameters, feature definitions, and model configuration
for the enhanced ML / DL pipeline.

All values can be overridden at runtime through CLI flags or keyword
arguments.
"""

# ── Feature names ───────────────────────────────────────────────────
# Input feature vector layout (per 30‑s epoch)
RAW_FEATURES = [
    # Respiratory
    "rr_mean", "rr_std", "rr_var", "rr_min", "rr_max",
    "rr_slope", "rr_iqr", "rr_skew", "rr_kurtosis",
    # Heart rate
    "hr_mean", "hr_std", "hr_var", "hr_min", "hr_max",
    "hr_slope", "hr_iqr", "hr_skew", "hr_kurtosis",
    # Motion / posture
    "motion_index", "motion_max", "motion_std",
    "posture_label",        # integer-encoded
    "posture_changes",
    # Sleep context
    "baseline_stage",       # integer-encoded baseline stage prediction
    "event_marker",         # 0 = normal, 1 = irregular, 2 = apnea
]

# Derived / engineered features appended during feature engineering
ENGINEERED_FEATURES = [
    # HRV time-domain
    "hrv_sdnn", "hrv_rmssd", "hrv_range", "hrv_pnn50",
    # HRV frequency-domain
    "hrv_lf_power", "hrv_hf_power", "hrv_lf_hf_ratio",
    # Respiratory dynamics
    "rr_trend_3", "rr_trend_5",           # rolling slope 3 / 5 epochs
    "rr_cv",                               # coefficient of variation
    "rr_delta",                            # epoch-to-epoch change
    # Motion spectral
    "motion_spectral_energy", "motion_dominant_freq",
    # Cross-signal
    "cardiorespiratory_coupling",          # Pearson(HR, RR) over window
]

ALL_FEATURES = RAW_FEATURES + ENGINEERED_FEATURES

FEATURE_DIM = len(ALL_FEATURES)

# ── Label definitions ──────────────────────────────────────────────
# Binary event classification
EVENT_LABELS_BINARY = ["Normal", "Apnea/Hypopnea"]
EVENT_ENCODING_BINARY = {"Normal": 0, "Apnea/Hypopnea": 1}

# Multi-class event classification
EVENT_LABELS_MULTI = ["Normal", "Hypopnea", "Obstructive Apnea",
                      "Central Apnea", "Mixed Apnea"]
EVENT_ENCODING_MULTI = {lbl: i for i, lbl in enumerate(EVENT_LABELS_MULTI)}

# Sleep stage labels
STAGE_LABELS_REDUCED = ["Wake", "REM", "Light", "Deep"]
STAGE_ENCODING_REDUCED = {lbl: i for i, lbl in enumerate(STAGE_LABELS_REDUCED)}

STAGE_LABELS_FULL = ["Wake", "N1", "N2", "N3", "REM"]
STAGE_ENCODING_FULL = {lbl: i for i, lbl in enumerate(STAGE_LABELS_FULL)}

# AHI severity (regression target boundaries)
AHI_SEVERITY = {"Normal": 5.0, "Mild": 15.0, "Moderate": 30.0}

# ── Epoch / windowing ──────────────────────────────────────────────
EPOCH_DURATION_SEC = 30
SAMPLING_RATE      = 20.0      # radar sampling rate (Hz)
SEQUENCE_LEN       = 10        # consecutive epochs for temporal models

# ── Classical ML defaults ──────────────────────────────────────────
RF_N_ESTIMATORS  = 400
RF_MAX_DEPTH     = 20
RF_MIN_SAMPLES   = 4

SVM_C            = 10.0
SVM_KERNEL       = "rbf"
SVM_GAMMA        = "scale"

XGB_N_ESTIMATORS  = 400
XGB_MAX_DEPTH     = 8
XGB_LEARNING_RATE = 0.08
XGB_SUBSAMPLE     = 0.85
XGB_COLSAMPLE     = 0.85
XGB_REG_LAMBDA    = 1.0

# ── Deep learning defaults ─────────────────────────────────────────
DL_HIDDEN_DIM     = 128
DL_DROPOUT        = 0.30
DL_EPOCHS         = 80
DL_BATCH_SIZE     = 64
DL_LEARNING_RATE  = 1e-3
DL_PATIENCE       = 10        # early-stopping patience

# Transformer
TF_N_HEADS        = 4
TF_FF_DIM         = 256
TF_N_LAYERS       = 2

# ── Training ───────────────────────────────────────────────────────
TEST_SIZE           = 0.20
CV_FOLDS            = 5
RANDOM_SEED         = 42

# ── Hyperparameter tuning ──────────────────────────────────────────
TUNING_METHOD       = "grid"       # "grid" | "bayesian"
TUNING_CV_FOLDS     = 3
TUNING_N_ITER       = 30           # for Bayesian search

# ── Synthetic data ─────────────────────────────────────────────────
SYNTHETIC_N_SUBJECTS       = 20
SYNTHETIC_EPOCHS_PER_SUBJ  = 240    # ~2 hr at 30 s epochs
SYNTHETIC_APNEA_RATE       = 0.15

# ── Persistence ────────────────────────────────────────────────────
MODEL_FILE_TEMPLATE = "ml_enhanced_{task}_{model_type}.joblib"
DL_MODEL_TEMPLATE   = "ml_enhanced_{task}_{model_type}.keras"

# ── Visualisation (Dark Radarix theme) ─────────────────────────────
DARK_BG        = "#0f172a"
DARK_CARD      = "#1e293b"
DARK_TEXT       = "#e2e8f0"
ACCENT_PRIMARY = "#22d3ee"
ACCENT_GOOD    = "#4ade80"
ACCENT_WARN    = "#f59e0b"
ACCENT_BAD     = "#ef4444"
ACCENT_COLORS  = ["#22d3ee", "#4ade80", "#f59e0b", "#ef4444",
                  "#a78bfa", "#f472b6", "#38bdf8", "#fbbf24"]
