# Sleep Stage Classification - Quick Code Reference

## Key Files by Purpose

### 1. Main Classification Logic
**File**: [backend/sleep_staging/predict.py](backend/sleep_staging/predict.py)

**Key Function**: `_classify_epoch()` (lines 54-120)
- Implements the 4-stage classification rule engine
- Takes a 56-feature vector, returns (stage_label, confidence_score)
- Uses physical thresholds, not ML models

**Main Public Function**: `predict_sleep_stages()` (lines 123-155)
- Batch prediction for all epochs in a session
- Returns list of stage labels + (n_epochs × 4) confidence matrix

---

### 2. REST API Sleep Analysis Endpoint
**File**: [backend/api/sleep_api.py](backend/api/sleep_api.py)

**Endpoint**: `POST /api/sleep/analyze` (lines 460-550)
- Triggers full 3-pipeline sleep analysis
- Takes user email, CSV path, model type
- Returns sleep structure with stage distributions

**Other Important Routes**:
- `GET /api/sleep/summary` - High-level summary
- `GET /api/sleep/stages` - Hypnogram (stage timeline)
- `GET /api/sleep/events` - Sleep event list
- `GET /api/vitals` - RR and HR time series

---

### 3. Sleep Staging Pipeline Entry Point
**File**: [backend/sleep_staging/run_sleep_staging.py](backend/sleep_staging/run_sleep_staging.py)

**Main Function**: `_run()` (lines 145-230+)
- Orchestrates feature extraction → training (optional) → prediction
- Loads optional sleep event and posture context
- Generates hypnogram visualization
- Saves JSON report with stage classifications

**Usage Example**:
```bash
python -m backend.sleep_staging.run_sleep_staging \
    --input backend/vital_signs_data_new.csv \
    --output backend/sleep_staging/output \
    --train-model --model-type random_forest
```

---

### 4. Feature Extraction
**File**: [backend/sleep_staging/features.py](backend/sleep_staging/features.py)

**Main Function**: `extract_all_features()` (lines 243-300)
- Extracts 56-feature vector from CSV waveform data
- Processes in 30-second epochs
- Features: respiration stats (10) + heart rate stats (10) + breathing stats (10) + chest stats (10) + HRV (3) + RRV (3) + motion (5) + posture (2) + events (3)

**Key Sub-functions**:
- `_variability_features()` - SDNN, RMSSD, range from BPM signal
- `_motion_features()` - motion mean, max, std, spikes, fraction_still
- `_posture_features()` - posture changes, stability
- `_event_features()` - event counts (irregular, apnea, motion)

---

### 5. Configuration Files

#### Model Configuration
**File**: [backend/sleep_staging/config.py](backend/sleep_staging/config.py)

```python
# Sleep-Stage Labels
STAGE_LABELS_REDUCED = ["Wake", "REM", "Light", "Deep"]  # Default
STAGE_LABELS_FULL = ["Wake", "N1", "N2", "N3", "REM"]    # Alternative

# Model Types (see lines 50-72)
DEFAULT_MODEL_TYPE = "random_forest"    # random_forest | svm | xgboost | lstm | cnn_lstm | tcn

# Deep Learning Config
DL_SEQUENCE_LEN = 10        # Use 10 consecutive epochs as context
DL_HIDDEN_DIM = 64
DL_DROPOUT = 0.3
DL_EPOCHS = 50
DL_BATCH_SIZE = 32
DL_LEARNING_RATE = 1e-3
```

#### Validation & Stage Labels
**File**: [backend/validation/config.py](backend/validation/config.py)

```python
# Stage Labels (line 39-40)
STAGE_LABELS_REDUCED = ["Wake", "REM", "Light", "Deep"]
STAGE_LABELS_FULL = ["Wake", "N1", "N2", "N3", "REM"]

# AHI Severity (for apnea context)
AHI_SEVERITY_CUTOFFS = {
    "Normal": 5.0,
    "Mild": 15.0,
    "Moderate": 30.0,
}
```

#### Sleep Detection Context
**File**: [backend/sleep_detection/config.py](backend/sleep_detection/config.py)

```python
# Thresholds used to calculate event features (lines 15-22)
AMPLITUDE_DROP_THRESHOLD = 0.30       # ≥30% drop → abnormal event
MOTION_SCORE_THRESHOLD = 0.55         # motion > this → artifact
RR_MIN_BPM = 4.0                       # Below this = suspect
RR_MAX_BPM = 50.0                      # Above this = too fast
```

---

## Classification Algorithm Flow

### Stage Classification Order (Decision Tree)

```
Input: 56-feature vector from one 30-second epoch

1. CHECK WAKE
   IF motion >= 0.25 OR RR > 22 OR RR < 6 OR HR > 78
   → WAKE (conf: 0.55-1.0)

2. CHECK DEEP
   IF frac_still >= 0.80 AND 7 ≤ RR ≤ 16 AND RR_std < 3.0 AND HR < 65
   → DEEP (conf: 0.55-0.95)

3. CHECK REM
   IF frac_still >= 0.85 AND RRV_SDNN >= 2.0
   → REM (conf: 0.50-0.85)

4. DEFAULT
   → LIGHT (conf: 0.65)
```

---

## Threshold Deep Dive

### Critical Thresholds in predict.py (lines 45-53)

```python
# WAKE Thresholds
_WAKE_MOTION     = 0.25    # Motion score for detecting awake state
_WAKE_RR_HIGH    = 22      # RR above this = abnormal (awake)
_WAKE_RR_LOW     = 6       # RR below this = suspect (awake/noise)
_WAKE_HR         = 78      # HR above this = elevated (awake)

# DEEP Thresholds
_DEEP_FRAC_STILL = 0.80    # Must be ≥80% motionless
_DEEP_RR_MAX     = 16      # Max RR for deep sleep (slow breathing)
_DEEP_RR_MIN     = 7       # Min RR (not too slow)
_DEEP_RR_STD_MAX = 3.0     # Max breathing variation (regular)
_DEEP_HR_MAX     = 65      # Max HR for deep sleep

# REM Thresholds
_REM_FRAC_STILL  = 0.85    # Extremely still (≥85%)
_REM_RRV_MIN     = 2.0     # Very irregular breathing
```

---

## Integration Points

### How Sleep Stages Flow Through the System

```
1. DATA COLLECTION
   ↓
   vitalsigns.py → radar waveform → vital_signs_session_*.csv

2. EVENT DETECTION
   ↓
   sleep_detection/run_sleep_detection.py
   → identifies apnea/irregular events
   → sleep_report_*.json

3. MOTION CONTEXT
   ↓
   motion_posture/run_motion_posture.py
   → identifies posture, motion patterns
   → motion_posture_report_*.json

4. FEATURE EXTRACTION
   ↓
   extract_all_features() in features.py
   → 56 features per epoch

5. STAGE CLASSIFICATION
   ↓
   predict_sleep_stages() in predict.py
   → 4-stage labels + confidence scores
   
6. STRUCTURE ANALYSIS
   ↓
   Calculates sleep efficiency, REM episodes, stage percentages
   → sleep_staging_report_*.json

7. API RESPONSE
   ↓
   /api/sleep/stages endpoint
   → Frontend hypnogram visualization
```

---

## Optional: Deep Learning Models

### Model Architectures
**File**: [backend/sleep_staging/models_deep.py](backend/sleep_staging/models_deep.py)

Supported architectures:
1. **LSTM** - Long Short-Term Memory (captures temporal patterns)
2. **CNN-LSTM** - Convolutional features + temporal context
3. **TCN** - Temporal Convolutional Network

**Input Shape**: (batch_size, sequence_len=10, n_features=56)
- Each sample = 10 consecutive 30-second epochs
- Total context window = 5 minutes

### Classical Models
**File**: [backend/sleep_staging/models_classical.py](backend/sleep_staging/models_classical.py)

Supported:
1. **Random Forest** (default) - 300 estimators, max_depth=20
2. **SVM** - RBF kernel, C=10.0
3. **XGBoost** - 300 estimators, max_depth=8, learning_rate=0.1

---

## Output Format

### Per-Epoch Records
```json
{
  "epoch_idx": 0,
  "timestamp_start": 0.0,
  "timestamp_end": 30.0,
  "stage": "Wake",
  "confidence": 0.87,
  "RR_mean": 16.5,
  "HR_mean": 72.3,
  "motion_mean": 0.28,
  "frac_still": 0.42
}
```

### Session Summary
```json
{
  "total_duration_min": 480,
  "sleep_efficiency_pct": 85.5,
  "efficiency_rating": "Good",
  "time_per_stage_sec": {
    "Wake": 300,
    "REM": 1200,
    "Light": 2400,
    "Deep": 1200
  },
  "pct_per_stage": {
    "Wake": 4.2,
    "REM": 16.7,
    "Light": 33.3,
    "Deep": 16.7
  },
  "rem_episodes": 4,
  "sleep_onset_latency_sec": 45
}
```

---

## How to Run Sleep Staging

### Option 1: Via REST API
```bash
POST /api/sleep/analyze
{
  "userEmail": "test@example.com",
  "trainModel": true,
  "modelType": "random_forest"
}
```

### Option 2: Direct Python CLI
```bash
cd /path/to/project
python -m backend.sleep_staging.run_sleep_staging \
    --input backend/vital_signs_data_new.csv \
    --output backend/sleep_staging/output \
    --train-model \
    --model-type random_forest
```

### Option 3: With Optional Context
```bash
python -m backend.sleep_staging.run_sleep_staging \
    --input backend/vital_signs_data_new.csv \
    --output backend/sleep_staging/output \
    --sleep-json backend/sleep_detection/output/sleep_report_20260315_001235.json \
    --posture-json backend/motion_posture/output/motion_posture_report_20260315_001235.json
```

---

## Rule vs. ML Comparison

### Rule-Based Classification (Current Default)
- **Pros**: Interpretable, no training needed, always available, based on physiology
- **Cons**: Less flexible, may miss complex patterns
- **Location**: `predict_sleep_stages()` in predict.py

### ML Classification (Optional)
- **Pros**: Can learn from data, potentially higher accuracy
- **Cons**: Requires training, slower, needs model file
- **Location**: `predict_sleep_stages_deep()` and classical models

**Fallback**: If ML model unavailable → automatically uses rule-based classifier

