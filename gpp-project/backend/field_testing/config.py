"""
field_testing/config.py
───────────────────────
Constants, type definitions, scoring thresholds, and the Dark Radarix
theme for the field-testing pipeline.
"""

from __future__ import annotations

# ── Radar placement types ──────────────────────────────────────────
PLACEMENT_TYPES = [
    "bedside_left",
    "bedside_right",
    "foot_of_bed",
    "under_bed_center",
    "under_bed_torso",
    "corner_left",
    "corner_right",
    "ceiling_mount",
    "headboard",
    "nightstand",
]

PLACEMENT_COORDS_DEFAULT: dict[str, tuple[float, float, float]] = {
    # (x_m, y_m, z_m) relative to bed centre
    "bedside_left":      (-0.50,  0.00,  0.70),
    "bedside_right":     ( 0.50,  0.00,  0.70),
    "foot_of_bed":       ( 0.00, -0.95,  0.70),
    "under_bed_center":  ( 0.00,  0.00, -0.15),
    "under_bed_torso":   ( 0.00,  0.30, -0.15),
    "corner_left":       (-1.20, -1.00,  1.40),
    "corner_right":      ( 1.20, -1.00,  1.40),
    "ceiling_mount":     ( 0.00,  0.00,  2.40),
    "headboard":         ( 0.00,  0.95,  0.90),
    "nightstand":        (-0.60, -0.60,  0.55),
}

# ── Environment types ──────────────────────────────────────────────
MATTRESS_TYPES = ["spring", "foam", "latex", "hybrid", "air"]
BEDDING_TYPES  = ["thin_sheet", "single_blanket", "duvet",
                  "weighted_blanket", "comforter"]

OCCLUSION_TYPES = [
    "none",
    "pillow_adjacent",
    "side_table",
    "headboard_only",
    "partner_present",
    "pet_present",
    "fan_running",
    "multiple_pillows",
]

ROOM_SIZES = ["small", "medium", "large"]  # < 10 m², 10-20, > 20

# ── Recording defaults ─────────────────────────────────────────────
DEFAULT_RECORDING_DURATION_SEC = 8 * 3600   # 8 hours
MIN_RECORDING_DURATION_SEC     = 1 * 3600   # 1 hour
EPOCH_DURATION_SEC             = 30
SAMPLING_RATE_HZ               = 20.0

# ── Vital-sign reference ranges ───────────────────────────────────
RR_NORMAL_RANGE = (10.0, 22.0)   # breaths per minute
HR_NORMAL_RANGE = (45.0, 100.0)  # beats per minute

# ── Performance thresholds (clinically meaningful) ─────────────────
RR_MAE_EXCELLENT  = 1.0   # breaths/min
RR_MAE_GOOD       = 2.0
RR_MAE_ACCEPTABLE = 3.0
RR_MAE_POOR       = 5.0

HR_MAE_EXCELLENT  = 2.0   # beats/min
HR_MAE_GOOD       = 4.0
HR_MAE_ACCEPTABLE = 6.0
HR_MAE_POOR       = 10.0

EVENT_F1_EXCELLENT  = 0.90
EVENT_F1_GOOD       = 0.80
EVENT_F1_ACCEPTABLE = 0.65
EVENT_F1_POOR       = 0.50

STAGE_KAPPA_EXCELLENT  = 0.80
STAGE_KAPPA_GOOD       = 0.60
STAGE_KAPPA_ACCEPTABLE = 0.40
STAGE_KAPPA_POOR       = 0.20

MOTION_ACC_EXCELLENT  = 0.92
MOTION_ACC_GOOD       = 0.85
MOTION_ACC_ACCEPTABLE = 0.75
MOTION_ACC_POOR       = 0.60

# ── Robustness scoring weights ─────────────────────────────────────
METRIC_WEIGHTS = {
    "rr_score":      0.25,
    "hr_score":      0.25,
    "event_score":   0.20,
    "stage_score":   0.15,
    "motion_score":  0.15,
}

# ── Confidence interval ───────────────────────────────────────────
CI_LEVEL = 0.95
BOOTSTRAP_N = 1000

# ── Synthetic data defaults ───────────────────────────────────────
SYNTHETIC_N_SUBJECTS    = 12
SYNTHETIC_N_PLACEMENTS  = 4
SYNTHETIC_N_ENVS        = 3
SYNTHETIC_EPOCHS_PER_SESSION = 960   # ~8 hours at 30 s

# ── Seed ───────────────────────────────────────────────────────────
RANDOM_SEED = 42

# ── Sleep event / stage labels ─────────────────────────────────────
EVENT_LABELS  = ["Normal", "Apnea/Hypopnea"]
STAGE_LABELS  = ["Wake", "REM", "Light", "Deep"]
POSTURE_LABELS = ["supine", "left", "right", "prone"]

# ── File patterns ──────────────────────────────────────────────────
CONFIG_FILE_TEMPLATE   = "field_test_config_{test_id}.json"
RESULTS_FILE_TEMPLATE  = "field_test_results_{test_id}.json"
REPORT_FILE_TEMPLATE   = "field_test_report_{test_id}.txt"

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
