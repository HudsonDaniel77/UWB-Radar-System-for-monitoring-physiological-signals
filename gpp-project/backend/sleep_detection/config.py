"""
sleep_detection/config.py
─────────────────────────
Default configurable parameters for the sleep‐event detection pipeline.
All values can be overridden at runtime via keyword arguments.
"""

# ── Epoch / windowing ───────────────────────────────────────────────
EPOCH_DURATION_SEC = 30          # seconds per analysis window
EPOCH_OVERLAP_FRAC = 0.50       # 50 % overlap between consecutive windows

# ── Baseline estimation ─────────────────────────────────────────────
BASELINE_WINDOW_SEC = 120       # use first N seconds for baseline
BASELINE_PERCENTILE = 75        # percentile of amplitude used as reference

# ── Thresholding ────────────────────────────────────────────────────
AMPLITUDE_DROP_THRESHOLD = 0.30 # ≥ 30 % drop from baseline → abnormal
APNEA_MIN_CONSECUTIVE = 3      # minimum consecutive abnormal epochs → apnea
IRREGULAR_MIN_CONSECUTIVE = 1   # at least 1 abnormal epoch → irregular

# ── Motion masking ──────────────────────────────────────────────────
MOTION_SCORE_THRESHOLD = 0.84   # allow limited true motion while avoiding breathing-driven false positives
MOTION_GUARD_EPOCHS = 0         # do not expand motion mask into neighboring epochs by default

# ── Respiration rate validity ───────────────────────────────────────
RR_MIN_BPM = 4.0               # below this is physiologically suspect
RR_MAX_BPM = 50.0              # above this is too fast

# ── Severity heuristics ─────────────────────────────────────────────
SEVERITY_THRESHOLDS = {         # apnea events per hour
    "Normal":   5,
    "Mild":     15,
    "Moderate": 30,
    # anything above 30 → Severe
}
