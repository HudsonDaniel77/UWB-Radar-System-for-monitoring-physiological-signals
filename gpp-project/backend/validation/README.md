# Validation & Benchmarking Pipeline

> Compare radar-based sleep diagnostics against PSG (polysomnography) reference standards.

## Module Structure

```
backend/validation/
├── __init__.py                 # package marker
├── config.py                   # clinical thresholds, matching params, theme
├── io_utils.py                 # PSG / system data loaders, report writer
├── event_metrics.py            # event matching (IoU / midpoint), P/R/F1
├── ahi.py                      # AHI computation, severity, comparison
├── agreement.py                # Bland–Altman, ICC(2,1), confusion matrix, κ
├── staging_validation.py       # stage accuracy, kappa, per-class breakdown
├── threshold_optimization.py   # ROC curves, confidence threshold tuning
├── visualize.py                # 7 publication-ready dark-theme plots
├── reporting.py                # JSON / CSV / Markdown report generation
├── run_validation.py           # CLI entry-point
├── tests/
│   ├── __init__.py
│   └── test_validation.py      # 70+ unit tests
└── output/                     # generated reports & plots (gitignored)
```

## Quick Start

### Demo run (synthetic data)

```bash
cd backend
python -m validation.run_validation --demo --output validation/output
```

### Real data

```bash
python -m validation.run_validation \
    --system-events  path/to/system_events.json \
    --psg-events     path/to/psg_events.csv \
    --psg-ahi        path/to/psg_ahi.csv \
    --system-stages  path/to/system_stages.json \
    --psg-stages     path/to/psg_stages.csv \
    --output         validation/output
```

### Flags

| Flag | Description |
|------|-------------|
| `--system-events` | System event detections (JSON) |
| `--psg-events` | PSG reference events (CSV) |
| `--system-stages` | System sleep-stage predictions (JSON) |
| `--psg-stages` | PSG reference stages (CSV) |
| `--psg-ahi` | PSG AHI per subject (CSV) |
| `--output` | Output directory (default: `validation/output`) |
| `--no-plots` | Skip plot generation |
| `--demo` | Run with synthetic demo data |

## API Endpoint

```
POST /validate
```

**Request body** (JSON):

```json
{
  "demo": true,
  "no_plots": false,
  "system_events": "path/to/events.json",
  "psg_events": "path/to/psg.csv"
}
```

**Response** (JSON):

```json
{
  "success": true,
  "validation": {
    "event_metrics": { "tp": 10, "fp": 2, "fn": 3, "precision": 0.833, ... },
    "ahi_comparison": { ... },
    "bland_altman": { ... },
    "staging_validation": { ... },
    "roc_curve": { ... }
  },
  "output_dir": "backend/validation/output"
}
```

## Input File Formats

### PSG Events CSV

```csv
start,end,event_type
10.0,25.0,apnea
60.0,80.0,hypopnea
120.0,145.0,obstructive_apnea
```

### PSG Stages CSV

```csv
epoch,stage
0,Wake
1,N1
2,N2
3,N3
4,REM
```

### PSG AHI CSV (multi-subject)

```csv
subject_id,ahi
subj_001,12.5
subj_002,28.3
```

### System Events JSON

```json
{
  "events": [
    {"start": 10.0, "end": 25.0, "event_type": "Apnea", "confidence": 0.9},
    {"start": 61.0, "end": 79.0, "event_type": "Hypopnea", "confidence": 0.7}
  ]
}
```

### System Stages JSON

```json
{
  "epoch_records": [
    {"predicted_stage": "Wake", "confidence": 0.85},
    {"predicted_stage": "Light", "confidence": 0.72}
  ]
}
```

## Computed Metrics

### Event Detection
- **True Positives / False Positives / False Negatives**
- **Precision, Recall (Sensitivity), F1-score**
- **Per event type** (Apnea, Hypopnea, Irregular)
- **Duration error** (MAE, RMSE, bias)
- **Epoch-level** binary classification (sensitivity, specificity)

### AHI Comparison
- **Per-subject** system vs PSG AHI
- **Errors**: MAE, RMSE, bias
- **Correlation**: Pearson r, Spearman ρ
- **AASM Severity Classification**: Normal (<5), Mild (5–15), Moderate (15–30), Severe (≥30)
- **Severity agreement** rate

### Agreement Statistics
- **Bland–Altman**: bias, 95% limits of agreement, % within LoA
- **ICC(2,1)**: two-way random, single measures
- **Cohen's Kappa**: inter-rater agreement

### Screening Performance
- Binary screening at AHI cutoffs (5, 15, 30)
- Sensitivity, Specificity, PPV, NPV per cutoff

### ROC Analysis
- AUC for AHI-based screening
- Optimal threshold via Youden's J statistic

### Sleep Stage Validation
- Overall accuracy, Cohen's κ
- Per-stage precision, recall, F1, support
- Macro-averaged metrics
- Transition agreement rate

## Visualizations

All plots use the **Radarix dark theme** (BG: `#0f172a`, Primary: `#22d3ee`).

| Plot | Description |
|------|-------------|
| Bland–Altman | Scatter of differences vs means with LoA lines |
| AHI Scatter | System vs PSG with regression line |
| AHI Error Histogram | Distribution of AHI errors |
| Confusion Matrix | Annotated heatmap (severity or stages) |
| ROC Curve | Sensitivity vs 1-Specificity with optimal point |
| Event Timeline | Side-by-side PSG vs System event bars |
| Threshold Curve | F1/Precision/Recall vs confidence threshold |

## Running Tests

```bash
cd backend
python -m pytest validation/tests/test_validation.py -v
```

Expected: **70+ tests pass**, covering:
- Config constants
- I/O loading & saving
- Event matching (IoU, midpoint)
- Metric computation (P/R/F1, duration errors)
- AHI computation & severity classification
- Agreement statistics (Bland–Altman, ICC, Kappa)
- Sleep stage validation
- Threshold optimization & ROC
- Visualization generation
- Report generation (JSON, CSV, Markdown)
- End-to-end demo pipeline
- Edge cases (empty data, boundary values, stress tests)

## Clinical Standards

This module follows **AASM (American Academy of Sleep Medicine)** guidelines:

- **Minimum apnea duration**: 10 seconds
- **AHI severity thresholds**: Normal <5, Mild 5–15, Moderate 15–30, Severe ≥30
- **Event matching**: IoU ≥ 0.30 or midpoint distance ≤ 15 s
- **Bland–Altman**: 95% limits of agreement (z = 1.96)
- **ICC model**: ICC(2,1) – two-way random, single measures
