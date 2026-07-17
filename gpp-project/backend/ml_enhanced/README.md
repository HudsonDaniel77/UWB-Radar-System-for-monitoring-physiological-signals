# ML-Enhanced Pipeline

**Phase 6** of the RespirationHealth radar-based vital-signs project.  
Trains advanced ML and DL models on processed features (RR, HR, motion, posture, sleep stages) to produce enhanced predictions for **sleep apnea / hypopnea detection**, **refined sleep-stage classification**, and **AHI severity estimation**.

---

## Module Structure

```
backend/ml_enhanced/
├── __init__.py                  # Package docstring
├── config.py                    # Features, labels, model defaults, theme
├── feature_engineering.py       # HRV, RR dynamics, spectral features, scaler
├── dataset.py                   # Synthetic data generators, sequence builder
├── training.py                  # Multi-model orchestration & cross-validation
├── evaluation.py                # Classification / regression metrics, comparison
├── hyperparameter_tuning.py     # Grid search & Bayesian HPO
├── inference.py                 # Save / load / predict helpers
├── visualize.py                 # Dark-themed plots (Radarix style)
├── run_training.py              # CLI entry point
├── models/
│   ├── __init__.py
│   ├── base.py                  # BaseModel ABC
│   ├── classical.py             # RF, SVM, XGBoost wrappers
│   ├── cnn.py                   # 1-D CNN classifier
│   ├── cnn_lstm.py              # CNN + Bi-LSTM classifier
│   └── transformer.py           # Multi-head Transformer classifier
└── tests/
    ├── __init__.py
    └── test_ml_enhanced.py      # 50+ unit & integration tests
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install numpy scipy scikit-learn joblib matplotlib xgboost
pip install tensorflow            # for deep models (optional)
pip install scikit-optimize       # for Bayesian HPO (optional)
```

### 2. Run demo training (CLI)

```bash
cd backend
python -m ml_enhanced.run_training --task event --demo --skip-deep
```

### 3. Run tests

```bash
cd backend
python -m pytest ml_enhanced/tests/test_ml_enhanced.py -v
```

---

## CLI Reference

```
python -m ml_enhanced.run_training [OPTIONS]

Options:
  --task {event,stage,ahi}   Classification task (default: event)
  --demo                     Use synthetic data for quick demo
  --input PATH               Path to real CSV data file
  --output DIR               Output directory (default: ml_enhanced_output/)
  --models M [M ...]         Models to train (default: all)
  --skip-deep                Skip deep-learning models
  --full-stages              Use 5-stage sleep labels instead of 4
  --no-plots                 Disable plot generation
  --tune                     Run hyperparameter tuning before training
  --tune-model MODEL         Which model to tune (default: random_forest)
  --tune-method {grid,bayes} Tuning method (default: grid)
  --seed INT                 Random seed (default: 42)
```

### Example commands

```bash
# Full classical + deep pipeline on synthetic event data
python -m ml_enhanced.run_training --task event --demo

# Stage classification with only RF and SVM
python -m ml_enhanced.run_training --task stage --demo --models random_forest svm --skip-deep

# Event detection with grid-search tuning on RF
python -m ml_enhanced.run_training --task event --demo --tune --tune-model random_forest --skip-deep

# Train on real CSV data
python -m ml_enhanced.run_training --task event --input ../data.csv --skip-deep
```

---

## API Route

**POST** `/ml-enhanced/train`

Send JSON body:

```json
{
  "task": "event",
  "demo": true,
  "models": ["random_forest", "svm"],
  "skip_deep": true,
  "no_plots": false,
  "tune": false
}
```

The API runs the training pipeline via subprocess and returns the structured result JSON.

---

## Feature Vector (40 dimensions)

| Group | Features | Count |
|-------|----------|-------|
| **RR raw** | rr_mean, rr_std, rr_var, rr_min, rr_max, rr_slope, rr_iqr, rr_skew, rr_kurtosis | 9 |
| **HR raw** | hr_mean, hr_std, hr_var, hr_min, hr_max, hr_slope, hr_iqr, hr_skew, hr_kurtosis | 9 |
| **Motion** | motion_index, motion_max, motion_std | 3 |
| **Context** | posture_label, posture_changes, baseline_stage, event_marker | 4 |
| **Spare** | spare_1 | 1 |
| **HRV time** | hrv_sdnn, hrv_rmssd, hrv_range, hrv_pnn50 | 4 |
| **HRV freq** | hrv_lf_power, hrv_hf_power, hrv_lf_hf_ratio | 3 |
| **RR dynamics** | rr_trend_3, rr_trend_5, rr_cv, rr_delta | 4 |
| **Motion spectral** | motion_spectral_energy, motion_dominant_freq | 2 |
| **Coupling** | cardiorespiratory_coupling | 1 |
| | **Total** | **40** |

---

## Models

### Classical

| Model | Key Params |
|-------|-----------|
| **Random Forest** | 400 estimators, max_depth 20, balanced weights |
| **SVM** | C=10, RBF kernel, probability=True |
| **XGBoost** | 400 estimators, depth 8, lr 0.08 (falls back to GradientBoosting) |

### Deep Learning (requires TensorFlow)

| Model | Architecture |
|-------|-------------|
| **1-D CNN** | Conv1D(128,5) → BN → Conv1D(128,5) → BN → Pool → Conv1D(256,3) → BN → GAP → Dense |
| **CNN+LSTM** | Conv1D → BN → Conv1D → BN → Pool → Conv1D → BN → BiLSTM(64) → Dense |
| **Transformer** | Dense proj → Positional Enc → N × (MHA + FFN + LN) → GAP → Dense |

All deep models use early stopping, learning-rate scheduling, and dropout.

---

## Tasks

| Task | Description | Labels |
|------|------------|--------|
| `event` | Binary apnea/hypopnea detection | Normal, Apnea/Hypopnea |
| `stage` | Sleep stage classification | Wake, Light, Deep, REM (or 5-class with `--full-stages`) |
| `ahi` | AHI severity estimation | Regression → 4-class severity |

---

## Output

After training, the output directory contains:

```
ml_enhanced_output/
├── training_summary.json     # Full results with metrics for every model
├── event_random_forest.joblib  # Saved best model
├── event_random_forest_meta.json
├── plots/
│   ├── confusion_matrix_*.png
│   ├── model_comparison_*.png
│   └── feature_importance_*.png
```

---

## Dark Radarix Theme

All plots use the project's unified dark theme:

- Background: `#0f172a`
- Card: `#1e293b`
- Text: `#e2e8f0`
- Primary accent: `#22d3ee` (cyan)
- Good: `#4ade80`, Warn: `#f59e0b`, Bad: `#ef4444`
