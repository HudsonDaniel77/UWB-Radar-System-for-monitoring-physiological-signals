"""
validation/config.py
────────────────────
Default parameters for the validation & benchmarking pipeline.

Clinical references
───────────────────
AHI severity cutoffs per AASM (American Academy of Sleep Medicine):
    Normal  : AHI <  5
    Mild    : 5 ≤ AHI < 15
    Moderate: 15 ≤ AHI < 30
    Severe  : AHI ≥ 30

Event-matching uses a tolerance window: a predicted event is counted as
a true positive if it overlaps ≥ OVERLAP_THRESHOLD with any reference
event, or if the midpoints are within MATCH_TOLERANCE_SEC.
"""

# ── AHI severity cutoffs ───────────────────────────────────────────
AHI_SEVERITY_CUTOFFS = {
    "Normal":   5.0,
    "Mild":    15.0,
    "Moderate": 30.0,
    # ≥ 30 → Severe
}

AHI_SEVERITY_LABELS = ["Normal", "Mild", "Moderate", "Severe"]

# ── Clinical screening thresholds ──────────────────────────────────
CLINICAL_AHI_CUTOFFS = [5.0, 15.0, 30.0]
DEFAULT_SCREENING_CUTOFF = 15.0   # used for sens/spec computation

# ── Event matching ─────────────────────────────────────────────────
MATCH_TOLERANCE_SEC = 15.0        # max time difference for event alignment
OVERLAP_THRESHOLD   = 0.30        # ≥ 30 % IoU to count as matching pair
MIN_EVENT_DURATION_SEC = 10.0     # AASM: apnea ≥ 10 s

# ── Sleep-stage labels ─────────────────────────────────────────────
STAGE_LABELS_REDUCED = ["Wake", "REM", "Light", "Deep"]
STAGE_LABELS_FULL    = ["Wake", "N1", "N2", "N3", "REM"]
EVENT_LABELS         = ["Normal", "Irregular", "Apnea"]

# ── Bland–Altman ───────────────────────────────────────────────────
BLAND_ALTMAN_CI = 1.96            # z-score for 95 % limits of agreement

# ── Visualisation ──────────────────────────────────────────────────
DARK_BG        = "#0f172a"
DARK_CARD      = "#1e293b"
DARK_TEXT       = "#e2e8f0"
ACCENT_PRIMARY = "#22d3ee"
ACCENT_GOOD    = "#4ade80"
ACCENT_WARN    = "#f59e0b"
ACCENT_BAD     = "#ef4444"

# ── Reporting ──────────────────────────────────────────────────────
REPORT_PREFIX = "validation_report"

# ── ICC ────────────────────────────────────────────────────────────
ICC_MODEL = "ICC(2,1)"            # two-way random, single measures
