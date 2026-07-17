# Field Testing & Deployment Evaluation

**Phase 7** of the Radarix sleep-monitoring pipeline — real-world
field testing and deployment readiness evaluation.

## Overview

This module evaluates how the radar-based sleep system performs
across multiple deployment scenarios:

| Dimension        | What it tests                           |
|------------------|-----------------------------------------|
| **Placement**    | 10 radar mounting positions             |
| **Mattress**     | Spring, foam, latex, hybrid, air        |
| **Bedding**      | Thin sheet → weighted blanket           |
| **Occlusions**   | Pillows, furniture, partner, pet, fan   |
| **Room size**    | Small (<10 m²), medium, large (>20 m²) |

For each configuration the pipeline measures:

* **RR accuracy** – MAE vs. ground-truth respiration rate
* **HR accuracy** – MAE vs. ground-truth heart rate
* **Event detection** – F1 for apnea / hypopnea events
* **Sleep staging** – Cohen's κ against reference hypnogram
* **Motion / posture** – Accuracy of posture classification

Results are aggregated into a single **robustness score** (0–1)
with five tiers: Excellent, Good, Acceptable, Poor, Failing.

## Module Structure

```
backend/field_testing/
├── __init__.py               # Package docstring
├── config.py                 # Constants, thresholds, dark theme
├── test_config.py            # Generate / save / load test configs
├── synthetic_data.py         # Realistic synthetic recordings
├── field_runner.py           # Run individual field tests
├── metrics.py                # Aggregate metrics + CI
├── robustness.py             # Robustness scoring & tiers
├── visualize.py              # Dark-themed plots (Radarix)
├── reports.py                # Deployment recommendation reports
├── run_field_testing.py      # CLI entry-point
├── tests/
│   ├── __init__.py
│   └── test_field_testing.py # Comprehensive test suite
└── README.md                 # This file
```

## Quick Start

### CLI

```bash
cd backend

# Demo with synthetic data (default 12 subjects × 4 placements)
python -m field_testing.run_field_testing --demo

# Fewer subjects, faster
python -m field_testing.run_field_testing --demo --subjects 4 --placements 2 --epochs 120

# Skip plots
python -m field_testing.run_field_testing --demo --no-plots

# Custom output directory
python -m field_testing.run_field_testing --demo --output my_results
```

### API

```
POST /field-testing/run
Content-Type: application/json

{
    "demo": true,
    "subjects": 6,
    "placements": 3,
    "epochs": 120,
    "no_plots": false,
    "seed": 42
}
```

Response:
```json
{
    "success": true,
    "result": {
        "overall_score": 0.62,
        "overall_tier": "Good",
        "best_placement": "bedside_right",
        "worst_placement": "corner_left",
        ...
    }
}
```

### Python

```python
from field_testing.test_config import generate_test_configs
from field_testing.synthetic_data import generate_batch
from field_testing.field_runner import run_field_tests
from field_testing.metrics import evaluate_field_results
from field_testing.robustness import aggregate_robustness
from field_testing.reports import report_deployment_recommendations

configs    = generate_test_configs(n_subjects=6, seed=42)
recordings = generate_batch(configs, seed=42, n_epochs=120)
results    = run_field_tests(recordings)
evaluation = evaluate_field_results(results)
robustness = aggregate_robustness(evaluation)
report     = report_deployment_recommendations(robustness, evaluation)
print(report)
```

## CLI Flags

| Flag            | Default | Description                        |
|-----------------|---------|------------------------------------|
| `--demo`        | off     | Use synthetic data                 |
| `--output`      | output/ | Output directory                   |
| `--subjects`    | 12      | Number of synthetic subjects       |
| `--placements`  | 4       | Number of placement types          |
| `--epochs`      | auto    | Epochs per recording               |
| `--no-plots`    | off     | Skip plot generation               |
| `--no-report`   | off     | Skip deployment report             |
| `--configs`     | —       | Path to pre-existing configs JSON  |
| `--input`       | —       | Path to pre-recorded data JSON     |
| `--seed`        | 42      | Random seed for reproducibility    |

## Output Files

| File                          | Description                      |
|-------------------------------|----------------------------------|
| `field_test_configs.json`     | Test configuration matrix        |
| `field_testing_summary.json`  | Structured results summary       |
| `deployment_report.txt`       | Human-readable recommendations   |
| `field_placement_rr.png`      | RR MAE by placement bar chart    |
| `field_placement_hr.png`      | HR MAE by placement bar chart    |
| `field_error_boxplots.png`    | Error distribution boxplots      |
| `field_robustness_radar.png`  | Spider chart of 5 dimensions     |
| `field_env_heatmap.png`       | Environment × metric heatmap     |

## Robustness Scoring

Scores are computed per-metric and then combined with weights:

| Metric         | Weight | Excellent | Good | Acceptable | Poor  |
|----------------|--------|-----------|------|------------|-------|
| RR MAE (bpm)   | 0.25   | ≤1.0      | ≤2.0 | ≤3.0       | ≤5.0  |
| HR MAE (bpm)   | 0.25   | ≤2.0      | ≤4.0 | ≤6.0       | ≤10.0 |
| Event F1       | 0.20   | ≥0.90     | ≥0.80| ≥0.65      | ≥0.50 |
| Stage Kappa    | 0.15   | ≥0.80     | ≥0.60| ≥0.40      | ≥0.20 |
| Motion Acc     | 0.15   | ≥0.92     | ≥0.85| ≥0.75      | ≥0.60 |

**Tiers:** Excellent (≥0.875), Good (≥0.625), Acceptable (≥0.375),
Poor (≥0.125), Failing (<0.125).

## Recommended Hardware Placements

| Priority | Placement          | Distance  | Expected quality |
|----------|--------------------|-----------|------------------|
| 1        | Bedside (L/R)      | 0.5 m     | Excellent        |
| 2        | Under-bed (torso)  | 0.3 m     | Excellent        |
| 3        | Headboard          | 0.95 m    | Good             |
| 4        | Under-bed (center) | 0.15 m    | Good             |
| 5        | Nightstand         | 0.85 m    | Good             |
| 6        | Ceiling mount      | 2.4 m     | Acceptable       |
| 7        | Foot of bed        | 0.95 m    | Acceptable       |
| 8        | Corner (L/R)       | 1.6 m     | Poor             |

## Running Tests

```bash
cd backend
python -m pytest field_testing/tests/test_field_testing.py -v
```

## Dependencies

* Python ≥ 3.10
* numpy
* scipy (optional, for advanced CI)
* matplotlib
* pytest (test only)
