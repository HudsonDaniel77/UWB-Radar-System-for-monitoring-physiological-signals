# Sleep Stage Classification Logic - Backend Analysis

## Overview
The sleep stage classification system uses a **rule-based classifier** derived from real radar-measurable physiological signals. The system classifies sleep into four stages: **Wake, REM, Light, and Deep**.

---

## Files Related to Sleep Stage Classification

### Core Classification Files

| File | Purpose |
|------|---------|
| [backend/sleep_staging/predict.py](backend/sleep_staging/predict.py) | **Main classifier** - implements rule-based sleep stage classification logic |
| [backend/api/sleep_api.py](backend/api/sleep_api.py) | **REST API endpoint** - `/api/sleep/analyze` triggers full sleep analysis pipeline |
| [backend/sleep_staging/run_sleep_staging.py](backend/sleep_staging/run_sleep_staging.py) | **CLI entry point** - orchestrates the sleep staging pipeline |
| [backend/sleep_staging/features.py](backend/sleep_staging/features.py) | **Feature extraction** - extracts 56 features from radar waveform data |
| [backend/sleep_staging/config.py](backend/sleep_staging/config.py) | **Configuration** - model types, thresholds, feature definitions |
| [backend/validation/config.py](backend/validation/config.py) | **Validation config** - stage labels and severity thresholds |

---

## Sleep Stage Classification Algorithm

### Location
[backend/sleep_staging/predict.py](backend/sleep_staging/predict.py#L54-L120)

### Classification Logic (Rule-Based)

The system classifies each 30-second epoch using a hierarchical rule-based approach:

#### Features Used (from 56-feature vector)

| Feature Index | Feature Name | Purpose |
|---|---|---|
| 0 | RR mean (BPM) | Mean respiration rate |
| 2 | RR std | Respiration rate variance |
| 10 | HR mean (BPM) | Mean heart rate |
| 32 | Breath STD | Breathing amplitude |
| 40 | RRV SDNN | Respiratory Rate Variability |
| 46 | Motion mean | Average motion score |
| 50 | Fraction still | Percentage of epoch with minimal motion |

#### Classification Thresholds

```python
# Wake Detection Thresholds
_WAKE_MOTION     = 0.25   # motion above this → Wake
_WAKE_RR_HIGH    = 22     # RR above this → likely awake
_WAKE_RR_LOW     = 6      # RR below this → sensor noise / awake
_WAKE_HR         = 78     # HR above this → awake

# Deep Sleep Thresholds
_DEEP_FRAC_STILL = 0.80   # must be very still (≥80% time motionless)
_DEEP_RR_MAX     = 16     # slow breathing (max 16 BPM)
_DEEP_RR_MIN     = 7      # not too slow (min 7 BPM)
_DEEP_RR_STD_MAX = 3.0    # regular breathing (std < 3.0)
_DEEP_HR_MAX     = 65     # low heart rate (< 65 BPM)

# REM Sleep Thresholds
_REM_FRAC_STILL  = 0.85   # extremely still (≥85% time motionless)
_REM_RRV_MIN     = 2.0    # highly irregular breathing (RRV ≥ 2.0)

# Light Sleep (default)
# Low motion, normal physiology (used when other stages don't match)
```

### Classification Decision Tree

#### **Stage 1: WAKE Detection**
```python
if (motion >= 0.25) OR 
   (RR > 22 or RR < 6) OR 
   (HR > 78):
    → WAKE (confidence: 0.55-1.0)
```

**Reasoning**: Detectable from motion, elevated HR, or abnormal respiration patterns

---

#### **Stage 2: DEEP SLEEP Detection**
```python
if (frac_still >= 0.80) AND 
   (7 ≤ RR ≤ 16) AND 
   (RR_std < 3.0) AND 
   (HR < 65 or HR = 0):
    → DEEP (confidence: 0.55-0.95)
```

**Reasoning**: Very still body, slow & regular breathing, low heart rate

**Confidence Calculation**:
- 60% based on stillness fraction
- 40% based on breathing regularity

---

#### **Stage 3: REM SLEEP Detection**
```python
if (frac_still >= 0.85) AND 
   (RRV_SDNN >= 2.0):
    → REM (confidence: 0.50-0.85)
```

**Reasoning**: Still body BUT irregular breathing (high respiratory variability is a radar proxy for REM)

**Confidence Calculation**:
- 50% base score
- +30% based on RRV intensity
- +20% based on stillness

---

#### **Stage 4: LIGHT SLEEP (Default)**
```python
else:
    → LIGHT (confidence: 0.65)
```

**Reasoning**: Default state when other criteria not met; represents transitional/light sleep

---

## API Endpoint: `/api/sleep/analyze`

### Location
[backend/api/sleep_api.py](backend/api/sleep_api.py#L460-L550)

### Endpoint Details

**Method**: `POST`  
**Path**: `/api/sleep/analyze`

### Request Body
```json
{
  "userEmail": "user@example.com",          // REQUIRED
  "sessionCsvPath": "/path/to/file.csv",   // Optional: CSV with vital signs
  "format": "pipeline",                     // "pipeline" or "live"
  "trainModel": true,                       // Train new model before prediction
  "modelType": "random_forest"              // Model type for training
}
```

### Pipeline (3-Step Process)

The endpoint orchestrates three sequential analysis pipelines:

#### **Step 1: Sleep Event Detection**
- Script: `backend/sleep_detection/run_sleep_detection.py`
- Output: `backend/sleep_detection/output/sleep_report_*.json`
- Identifies apnea/irregular breathing events

#### **Step 2: Motion/Posture Analysis**
- Script: `backend/motion_posture/run_motion_posture.py`
- Output: `backend/motion_posture/output/motion_posture_report_*.json`
- Provides context for sleep staging

#### **Step 3: Sleep Stage Classification**
- Script: `backend/sleep_staging/run_sleep_staging.py`
- Output: `backend/sleep_staging/output/sleep_staging_report_*.json`
- Classifies each epoch into Wake/REM/Light/Deep
- Returns predictions with confidence scores

### Response
```json
{
  "success": true,
  "sleep_summary": { ... },
  "motion_summary": { ... },
  "sleep_structure": {
    "total_duration_min": 480,
    "sleep_efficiency_pct": 85.5,
    "time_per_stage_sec": { "Wake": 300, "REM": 1200, "Light": 2400, "Deep": 1200 },
    "pct_per_stage": { "Wake": 4.2, "REM": 16.7, "Light": 33.3, "Deep": 16.7 },
    "rem_episodes": 4
  },
  "staging_metrics": { ... }
}
```

---

## Sleep Stage Labels

### Reduced Set (Default)
```python
STAGE_LABELS_REDUCED = ["Wake", "REM", "Light", "Deep"]
```

### Full PSG Set (Alternative)
```python
STAGE_LABELS_FULL = ["Wake", "N1", "N2", "N3", "REM"]
```

**Stage Encoding**:
- Wake: 0
- REM/N1: 1 (reduced) / 1 (full)
- Light/N2: 2 (reduced) / 2 (full)
- Deep/N3: 3 (reduced) / 3 (full)

---

## Feature Extraction

### Location
[backend/sleep_staging/features.py](backend/sleep_staging/features.py)

### Feature Vector (56 Total Features)

| Category | Count | Features |
|----------|-------|----------|
| RR Stats | 10 | mean, median, std, var, min, max, skew, kurtosis, slope, iqr |
| HR Stats | 10 | same statistical features |
| Chest Stats | 10 | same statistical features |
| Breath Stats | 10 | same statistical features |
| RRV (Respiratory Variability) | 3 | SDNN, RMSSD, range |
| HRV (Heart Rate Variability) | 3 | SDNN, RMSSD, range |
| Motion Features | 5 | mean, max, std, spikes, fraction_still |
| Posture Features | 2 | changes, stability |
| Event Features | 3 | event_count_irregular, event_count_apnea, event_count_motion |
| **TOTAL** | **56** | |

### Key Feature Calculation

**Fraction Still** (critical for stage classification):
- Calculated as percentage of samples in epoch with motion < 0.10 threshold
- High values (0.80-0.85) indicate Deep or REM sleep
- Low values indicate Wake or Light sleep

---

## Model Training & Inference

### Supported Model Types

#### Classical ML Models
```python
DEFAULT_MODEL_TYPE = "random_forest"   # Most common
# Also supported: "svm", "xgboost"
```

**Configuration**:
```python
DEFAULT_N_ESTIMATORS = 300           # Random Forest
DEFAULT_MAX_DEPTH    = 20
XGB_N_ESTIMATORS     = 300           # XGBoost
XGB_MAX_DEPTH        = 8
XGB_LEARNING_RATE    = 0.1
```

#### Deep Learning Models
```python
# Supported: "lstm", "cnn_lstm", "tcn"
DL_SEQUENCE_LEN     = 10             # Context window (10 consecutive epochs)
DL_HIDDEN_DIM       = 64
DL_DROPOUT          = 0.3
DL_EPOCHS           = 50
DL_BATCH_SIZE       = 32
DL_LEARNING_RATE    = 1e-3
```

### Fallback Logic

If deep learning model unavailable:
1. Falls back to rule-based classifier
2. Rule-based classifier always available
3. No model file required for basic functionality

---

## Additional Configuration

### Epoch Configuration
[backend/sleep_staging/config.py](backend/sleep_staging/config.py)

```python
EPOCH_DURATION_SEC = 30      # PSG standard (matches clinical standards)
EPOCH_OVERLAP_FRAC = 0.0     # No overlap for staging
SAMPLING_RATE      = 20.0    # 20 Hz radar
```

### Sleep Efficiency Thresholds
```python
SLEEP_EFFICIENCY_THRESHOLDS = {
    "Good":  0.85,    # ≥85% time asleep
    "Fair":  0.75,
    "Poor":  0.0,
}
```

### Reference Stage Proportions (Healthy Adult)
```python
REFERENCE_STAGE_PROPORTIONS = {
    "Wake":  0.05,    # 5%
    "REM":   0.20,    # 20%
    "Light": 0.50,    # 50%
    "Deep":  0.25,    # 25%
}
```

---

## Sleep Event Detection Context

### Location
[backend/sleep_detection/config.py](backend/sleep_detection/config.py)

These thresholds inform feature calculation for staging:

```python
AMPLITUDE_DROP_THRESHOLD = 0.30  # ≥30% drop → abnormal event
MOTION_SCORE_THRESHOLD   = 0.55  # motion above this → artifact
RR_MIN_BPM              = 4.0    # physiological minimum
RR_MAX_BPM              = 50.0   # physiological maximum
```

---

## Validation & Severity Classification

### Location
[backend/validation/config.py](backend/validation/config.py)

### AHI Severity Thresholds
```python
AHI_SEVERITY_CUTOFFS = {
    "Normal":    5.0,     # AHI < 5
    "Mild":      15.0,    # 5 ≤ AHI < 15
    "Moderate":  30.0,    # 15 ≤ AHI < 30
    # ≥30 → Severe
}
```

---

## Prediction Output Example

### Epoch Record Format
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

### Sleep Structure Summary
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
  "stage_counts": {
    "Wake": 10,
    "REM": 40,
    "Light": 80,
    "Deep": 40
  },
  "sleep_onset_latency_sec": 45,
  "rem_episodes": 4
}
```

---

## Summary

### Key Characteristics

1. **Rule-Based Classification**: No complex ML model required; uses physiological thresholds derived from radar signals
2. **Four-Stage System**: Wake → REM → Light → Deep
3. **Confidence Scoring**: Each prediction includes confidence (0-1)
4. **Feature-Rich**: 56 features derived from respiration, heart rate, motion
5. **Hierarchical Decision Tree**: Sequential elimination through stages
6. **Fallback Support**: Deep learning optional; rule-based always available

### Critical Thresholds for Stage Distinction

| Threshold | Value | Purpose |
|-----------|-------|---------|
| Motion for Wake | ≥ 0.25 | Detect movement |
| RR for Wake | > 22 or < 6 | Detect abnormal breathing |
| HR for Wake | > 78 | Detect elevated heart rate |
| Stillness for Deep | ≥ 0.80 | Must be very still |
| RR range for Deep | 7-16 BPM | Slow, stable breathing |
| RR regularity for Deep | STD < 3.0 | No breathing variation |
| HR for Deep | < 65 | Low heart rate |
| Stillness for REM | ≥ 0.85 | Extremely still |
| RRV for REM | ≥ 2.0 | Highly irregular breathing |

