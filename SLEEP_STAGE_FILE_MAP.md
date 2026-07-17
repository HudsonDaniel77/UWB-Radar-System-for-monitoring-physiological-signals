# Sleep Stage Classification - File Directory & Contents Map

## Directory Structure

```
gpp-project/backend/
├── sleep_staging/                    # Sleep stage classification pipeline
│   ├── predict.py                   # ⭐ MAIN: Rule-based classifier
│   ├── run_sleep_staging.py          # CLI entry point + orchestration
│   ├── features.py                   # Feature extraction (56 features)
│   ├── config.py                     # Configuration & hyperparameters
│   ├── training.py                   # Model training (classical/deep)
│   ├── models_classical.py           # RF, SVM, XGBoost implementations
│   ├── models_deep.py                # LSTM, CNN-LSTM, TCN architectures
│   ├── evaluate.py                   # Metrics computation
│   ├── visualize.py                  # Hypnogram plots & reports
│   ├── io_utils.py                   # CSV/JSON I/O utilities
│   ├── __init__.py
│   └── output/                       # Generated reports & plots
│       ├── sleep_staging_report_*.json
│       └── sleep_staging_plot_*.png
│
├── api/
│   ├── sleep_api.py                  # ⭐ REST API Blueprint
│   ├── pipeline.py                   # Flask app + routing
│   └── __init__.py
│
├── sleep_detection/                  # Sleep event detection (context)
│   ├── config.py                     # Thresholds for event detection
│   ├── run_sleep_detection.py        # Event detection pipeline
│   └── output/
│       └── sleep_report_*.json       # Event list & timeline
│
├── motion_posture/                   # Motion/posture analysis (context)
│   ├── run_motion_posture.py         # Motion pipeline
│   └── output/
│       └── motion_posture_report_*.json
│
├── validation/                       # Validation & comparison
│   ├── config.py                     # Stage labels & severity thresholds
│   └── ...
│
└── vital_signs_data_new.csv          # Sample input data

```

---

## File-by-File Breakdown

### Core Classification Files

#### 1. **predict.py** ⭐ PRIMARY CLASSIFIER
Location: `backend/sleep_staging/predict.py`

**Functions**:
| Function | Lines | Purpose |
|----------|-------|---------|
| `_classify_epoch()` | 54-120 | Single epoch → stage + confidence |
| `predict_sleep_stages()` | 123-155 | Batch rule-based prediction |
| `predict_sleep_stages_deep()` | 158-220 | ML model prediction (with fallback) |
| `run_prediction()` | 225-280+ | End-to-end pipeline |

**Key Constants** (lines 38-53):
- `_I_RR_MEAN = 0`, `_I_WAKE_MOTION = 0.25`, `_DEEP_FRAC_STILL = 0.80`, etc.

**Algorithm**: Lines 54-120
- Lines 54-75: WAKE decision
- Lines 77-90: DEEP decision
- Lines 92-94: REM decision
- Line 97: LIGHT default

---

#### 2. **run_sleep_staging.py** CLI & ORCHESTRATION
Location: `backend/sleep_staging/run_sleep_staging.py`

**Functions**:
| Function | Lines | Purpose |
|----------|-------|---------|
| `main()` | 77-88 | Parse CLI arguments |
| `_run()` | 145-230+ | Main orchestration |
| `_compare_models()` | 240+ | Train & compare multiple models |

**Key Arguments** (lines 79-102):
- `--input`: CSV path
- `--model-type`: random_forest | svm | xgboost | lstm | cnn_lstm | tcn
- `--train-model`: Train before prediction
- `--sleep-json`: Optional event context
- `--posture-json`: Optional motion context

**Pipeline Steps** (lines 180-230):
1. Load data
2. Extract features
3. Train model (optional)
4. Predict stages
5. Compute metrics
6. Visualize
7. Save report

---

#### 3. **features.py** FEATURE EXTRACTION
Location: `backend/sleep_staging/features.py`

**Functions**:
| Function | Lines | Purpose |
|----------|-------|---------|
| `_stat_features()` | 46-75 | 10 statistical features |
| `_variability_features()` | 79-92 | HRV/RRV (SDNN, RMSSD, range) |
| `_motion_features()` | 97-112 | 5 motion features |
| `_posture_features()` | 116-140 | 2 posture features |
| `_event_features()` | 147-175 | 3 event features |
| `extract_epoch_features()` | 194-240 | Single epoch → 56 features |
| `extract_all_features()` | 243-300+ | Batch feature extraction |

**Feature Layout** (lines 180-192): Total 56 features
- RR stats: 10
- HR stats: 10
- Chest stats: 10
- Breath stats: 10
- RRV: 3
- HRV: 3
- Motion: 5
- Posture: 2
- Event: 3

---

#### 4. **config.py** CONFIGURATION
Location: `backend/sleep_staging/config.py`

**Key Sections**:
| Section | Lines | Contents |
|---------|-------|----------|
| Epoch setup | 8-10 | EPOCH_DURATION_SEC=30, SAMPLING_RATE=20 |
| Stage labels | 13-22 | STAGE_LABELS_REDUCED/FULL, encoding dicts |
| Features | 26-50 | STAT_FEATURES, HRV/RRV, MOTION, POSTURE, EVENT lists |
| Model defaults | 54-72 | DEFAULT_MODEL_TYPE, DL_SEQUENCE_LEN, etc. |
| Training | 75-77 | TEST_SIZE, CV_FOLDS, RANDOM_SEED |
| Synthetic data | 80-82 | SYNTHETIC_SAMPLES_PER_CLASS |
| Thresholds | 88-97 | SLEEP_EFFICIENCY_THRESHOLDS, REFERENCE_STAGE_PROPORTIONS |

---

#### 5. **sleep_api.py** REST API
Location: `backend/api/sleep_api.py`

**Routes**:
| Route | Method | Lines | Purpose |
|-------|--------|-------|---------|
| `/api/sleep/summary` | GET | 115-165 | High-level summary |
| `/api/sleep/events` | GET | 169-189 | Sleep event list |
| `/api/sleep/stages` | GET | 193-209 | Hypnogram (stages) |
| `/api/vitals` | GET | 213-236 | RR/HR time series |
| `/api/motion` | GET | 240-259 | Motion timeline |
| `/api/sleep/sessions` | GET | 263-283 | List sessions |
| `/api/sleep/full-session` | GET | 287-405 | Aggregated data |
| `/api/sleep/collect` | POST | 410-455 | Collect sensor data |
| `/api/sleep/analyze` | POST | 460-550 | **MAIN: Run analysis pipeline** |

**Pipeline Orchestration** (lines 460-550):
1. Parse request body
2. Step 1: Sleep event detection (SLEEP_DETECTION_SCRIPT)
3. Step 2: Motion/posture (MOTION_POSTURE_SCRIPT)
4. Step 3: Sleep staging (SLEEP_STAGING_SCRIPT)
5. Parse outputs, merge results
6. Return combined response

---

### Supporting Files

#### 6. **training.py** MODEL TRAINING
Location: `backend/sleep_staging/training.py`

**Functions**:
| Function | Purpose |
|----------|---------|
| `train_classical()` | Train RF/SVM/XGBoost |
| `train_deep()` | Train LSTM/CNN-LSTM/TCN |
| `generate_synthetic_sleep_data()` | Create synthetic training data |
| `build_sequences()` | Convert epoch features → sequences (for DL) |

---

#### 7. **models_classical.py** CLASSICAL ML
Location: `backend/sleep_staging/models_classical.py`

**Models**:
- Random Forest (300 estimators, max_depth=20)
- SVM (RBF kernel, C=10.0)
- XGBoost (300 estimators, max_depth=8)

**Load Function**: `load_model(model_type)`

---

#### 8. **models_deep.py** DEEP LEARNING
Location: `backend/sleep_staging/models_deep.py`

**Architectures**:
- LSTM
- CNN-LSTM
- TCN (Temporal Convolution)

**Input Shape**: (batch_size, seq_len=10, n_features=56)

---

#### 9. **evaluate.py** METRICS
Location: `backend/sleep_staging/evaluate.py`

**Computes**:
- Accuracy, Precision, Recall, F1
- Confusion matrix
- Per-class metrics
- Optional Kappa coefficient (if reference available)

---

#### 10. **visualize.py** VISUALIZATION
Location: `backend/sleep_staging/visualize.py`

**Generates**:
- Hypnogram (stage timeline)
- Confusion matrix heatmap
- Feature importance plots
- Sleep structure pie charts
- Training history (for DL models)

---

#### 11. **io_utils.py** I/O UTILITIES
Location: `backend/sleep_staging/io_utils.py`

**Functions**:
- `load_pipeline_csv()` - Parse vital signs CSV
- `load_live_session_csv()` - Parse live sensor format
- `load_sleep_events_json()` - Load event context
- `load_posture_json()` - Load posture context
- `save_staging_report()` - Write JSON report

---

### Context Files (Sleep Events & Motion)

#### 12. **sleep_detection/config.py** EVENT THRESHOLDS
Location: `backend/sleep_detection/config.py`

**Key Thresholds** (used for event features):
```python
AMPLITUDE_DROP_THRESHOLD = 0.30   # Detect abnormal breathing
MOTION_SCORE_THRESHOLD = 0.55     # Detect motion artifacts
RR_MIN_BPM = 4.0, RR_MAX_BPM = 50.0  # Valid respiration range
```

---

#### 13. **validation/config.py** VALIDATION CONFIG
Location: `backend/validation/config.py`

**Key Defines**:
```python
STAGE_LABELS_REDUCED = ["Wake", "REM", "Light", "Deep"]
STAGE_LABELS_FULL = ["Wake", "N1", "N2", "N3", "REM"]
AHI_SEVERITY_CUTOFFS = {"Normal": 5.0, "Mild": 15.0, "Moderate": 30.0}
```

---

## Data Flow Diagram

```
INPUT CSV
(vital_signs_session_*.csv)
         ↓
    [extract_all_features]
    (features.py, lines 243-300)
         ↓
  FEATURE MATRIX
  (n_epochs × 56)
         ↓
    [Optional: Train ML Model]
    (training.py)
         ↓
    [predict_sleep_stages]
    (predict.py, lines 123-155)
         ↓
  PREDICTIONS
  (stage labels + confidence)
         ↓
    [Compute Sleep Structure]
    (efficiency, stage durations, REM episodes)
         ↓
OUTPUT JSON
(sleep_staging_report_*.json)
         ↓
  [API Response]
  (/api/sleep/analyze)
         ↓
FRONTEND
(Sleep Pattern page)
```

---

## Search Quick Reference

| What You're Looking For | File | Lines |
|------------------------|------|-------|
| Classification algorithm | predict.py | 54-120 |
| Threshold values | predict.py | 45-53 |
| REST API endpoint | sleep_api.py | 460-550 |
| Feature names | features.py | 180-192 |
| Stage labels | config.py | 13-22 |
| Model types | config.py | 54-72 |
| Sleep efficiency formula | visualize.py | 200+ |
| Hypnogram generation | visualize.py | 250+ |
| Event threshold | sleep_detection/config.py | 16-22 |
| Severity classification | validation/ahi.py | 91+ |

---

## Key Code Locations for Each Requirement

### 1. Sleep Stage Classification (Deep/Light/REM/Wake)
- **Rule Logic**: [predict.py](backend/sleep_staging/predict.py#L54-L120) lines 54-120
- **API Endpoint**: [sleep_api.py](backend/api/sleep_api.py#L460-L550) lines 460-550
- **Pipeline**: [run_sleep_staging.py](backend/sleep_staging/run_sleep_staging.py#L145-L230) lines 145-230

### 2. Algorithm/Model Determination
- **Rule-Based**: [predict.py](backend/sleep_staging/predict.py#L54-L120) (always available)
- **Classical ML**: [models_classical.py](backend/sleep_staging/models_classical.py) (RF/SVM/XGBoost)
- **Deep Learning**: [models_deep.py](backend/sleep_staging/models_deep.py) (LSTM/CNN-LSTM/TCN)

### 3. Threshold Values
- **Classification Thresholds**: [predict.py](backend/sleep_staging/predict.py#L45-L53) lines 45-53
- **Event Detection Thresholds**: [sleep_detection/config.py](backend/sleep_detection/config.py#L16-L22) lines 16-22
- **Wake/Light Distinction**: `_WAKE_MOTION=0.25`, `_REM_RRV_MIN=2.0`

### 4. Sleep Analysis Endpoint
- **Primary Endpoint**: [sleep_api.py](backend/api/sleep_api.py#L460-L550) `POST /api/sleep/analyze`
- **Sub-endpoints**: [sleep_api.py](backend/api/sleep_api.py#L115-L550)
  - `/api/sleep/stages` - hypnogram
  - `/api/sleep/summary` - overview
  - `/api/sleep/events` - event list

