# Sleep Stage Classification & Sleep Structure Prediction

Radar-based sleep-stage classification module for the **Radarix** pipeline.
Predicts sleep stages (Wake / REM / Light / Deep) from IWR6843 vital-sign
data and produces hypnogram visualisations, sleep-structure summaries, and
comprehensive evaluation metrics.

---

## Quick Start

```bash
# From the backend/ directory
# Train on synthetic data + predict on a CSV
python -m sleep_staging.run_sleep_staging \
    --input vital_signs_data_new.csv \
    --output sleep_staging/output \
    --train-model

# Compare Random Forest vs XGBoost
python -m sleep_staging.run_sleep_staging \
    --input vital_signs_data_new.csv \
    --output sleep_staging/output \
    --train-model --compare random_forest,xgboost
```

---

## Module Structure

```
sleep_staging/
├── __init__.py            # Package marker
├── config.py              # All tuneable parameters
├── features.py            # 56-dim epoch feature extraction
├── models_classical.py    # RF / SVM / XGBoost factory (sklearn Pipeline)
├── models_deep.py         # LSTM / CNN+LSTM / TCN (optional TensorFlow)
├── training.py            # Synthetic data generator, train + CV
├── predict.py             # Inference + sleep structure computation
├── evaluate.py            # Accuracy, F1, Kappa, ROC AUC, confusion matrix
├── visualize.py           # Hypnogram, feature trends, ROC, pie chart
├── io_utils.py            # CSV / JSON loaders & report writers
├── run_sleep_staging.py   # CLI entry point
├── README.md              # This file
└── tests/
    ├── __init__.py
    └── test_sleep_staging.py   # 63 unit tests
```

---

## Features (56-dim per 30 s epoch)

| Group                 | Count | Details |
|-----------------------|------:|---------|
| RR BPM statistics     |    10 | mean, median, std, var, min, max, skew, kurtosis, slope, IQR |
| HR BPM statistics     |    10 | same as RR |
| Chest displacement    |    10 | same as RR |
| Breath waveform       |    10 | same as RR |
| RR variability (RRV)  |     3 | SDNN, RMSSD, range |
| HR variability (HRV)  |     3 | SDNN, RMSSD, range |
| Motion                |     5 | mean, max, std, spike count, fraction still |
| Posture               |     2 | changes, stability |
| Sleep events          |     3 | irregular, apnea, motion event counts |
| **Total**             | **56** | |

---

## Sleep Stages

### Reduced (default, 4 classes)
| Label | Description |
|-------|-------------|
| Wake  | Eyes open / body active |
| REM   | Rapid Eye Movement sleep |
| Light | N1 + N2 combined |
| Deep  | N3 / slow-wave sleep |

### Full PSG (optional, 5 classes)
Wake, N1, N2, N3, REM — enabled with `--full-stages`.

---

## Supported Models

### Classical (sklearn Pipeline: StandardScaler → Classifier)
| Model         | Key Defaults |
|---------------|-------------|
| `random_forest` | 300 trees, depth 20 |
| `svm`          | RBF kernel, C=10, probability=True |
| `xgboost`      | 300 trees, depth 8, lr 0.1 |

### Deep Learning (optional, requires TensorFlow)
| Model      | Architecture |
|------------|-------------|
| `lstm`     | 2-layer LSTM → Dense(softmax) |
| `cnn_lstm` | Conv1D → BN → Conv1D → MaxPool → LSTM → Dense |
| `tcn`      | Dilated causal convolution residual blocks |

> Deep learning models gracefully return `None` if TensorFlow is not installed.

---

## CLI Reference

```
python -m sleep_staging.run_sleep_staging [OPTIONS]

Options:
  --input FILE           Input CSV (pipeline or live format)
  --output DIR           Output directory (default: sleep_staging/output)
  --format FMT           "pipeline" | "live"  (default: pipeline)
  --user EMAIL           User identifier
  --model-type TYPE      random_forest | svm | xgboost | lstm | cnn_lstm | tcn
  --train-model          Train a new model before prediction
  --compare M1,M2,...    Compare multiple models (comma-separated)
  --full-stages          Use 5-class PSG labels instead of 4
  --sleep-json FILE      Sleep detection JSON for event features
  --posture-json FILE    Posture report JSON for posture features
  --epoch SEC            Epoch duration (default: 30)
  --sampling-rate HZ     Sampling rate (default: 20)
  --no-plots             Skip plot generation
```

---

## API Endpoint

```
POST /sleep-staging
Content-Type: application/json

{
  "userEmail":   "user@example.com",
  "inputFile":   "path/to/vital_signs.csv",
  "format":      "pipeline",
  "modelType":   "random_forest",
  "trainModel":  true,
  "fullStages":  false,
  "sleepJson":   "",
  "postureJson": ""
}
```

**Response:**
```json
{
  "success": true,
  "sleep_structure": { ... },
  "metrics": { ... },
  "epoch_records": [ ... ],
  "output_dir": "backend/sleep_staging/output"
}
```

---

## Output Files

| File | Contents |
|------|----------|
| `sleep_staging_report_*.csv` | Per-epoch predictions with probabilities |
| `sleep_staging_report_*.json` | Full JSON report (structure + metrics + epochs) |
| `hypnogram.png` | Stepped stage timeline |
| `feature_trends.png` | RR / HR / motion trends with stage background |
| `roc_curves.png` | Multi-class one-vs-rest ROC |
| `confusion_matrix.png` | Annotated heatmap |
| `sleep_structure.png` | Pie chart with efficiency rating |

---

## Evaluation Metrics

- **Accuracy** — overall correct predictions
- **Precision / Recall / F1** — macro-averaged and per-class
- **Cohen's Kappa** — agreement beyond chance
- **ROC AUC** — one-vs-rest, macro and per-class
- **Confusion Matrix** — full N×N matrix
- **Cross-Validation** — stratified k-fold (default k=5)

---

## Key Parameters (config.py)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `EPOCH_DURATION_SEC` | 30 | PSG-standard epoch length |
| `SAMPLING_RATE` | 20.0 | Radar frame rate (Hz) |
| `SYNTHETIC_SAMPLES_PER_CLASS` | 600 | Training data per stage |
| `CV_FOLDS` | 5 | Cross-validation folds |
| `TEST_SIZE` | 0.20 | Train/test split ratio |
| `DL_SEQUENCE_LEN` | 10 | Epoch sequence for recurrent models |
| `DL_EPOCHS` | 50 | Training epochs for deep models |
| `SLEEP_EFFICIENCY_THRESHOLDS` | Good ≥ 85%, Fair ≥ 75% | Rating cutoffs |

---

## Running Tests

```bash
cd backend
python -m unittest sleep_staging.tests.test_sleep_staging -v
```

63 tests covering: config, epoch indexing, feature extraction (all sub-functions),
model building, synthetic data, sequence building, training, persistence,
prediction, sleep structure, evaluation metrics, I/O, and end-to-end flow.

---

## Dependencies

- **Required:** numpy, scipy, scikit-learn, xgboost, matplotlib, joblib
- **Optional:** tensorflow (for LSTM / CNN+LSTM / TCN models)
