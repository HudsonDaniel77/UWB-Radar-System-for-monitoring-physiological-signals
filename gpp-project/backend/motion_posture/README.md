# Motion & Posture Context Pipeline

Classifies body **motion type** and **sleep posture** from radar vital-sign
data, then fuses the results with sleep-event detections (optional) to
produce contextual annotations.

## Quick start

### CLI

```bash
# From project root
python -m backend.motion_posture.run_motion_posture \
    --input backend/vital_signs_data_new.csv \
    --output backend/motion_posture/output

# Live-session format (allframes.py output)
python -m backend.motion_posture.run_motion_posture \
    --input vital_signs_data/vital_signs_live_session.csv \
    --format live \
    --output backend/motion_posture/output

# With sleep-event JSON for context fusion
python -m backend.motion_posture.run_motion_posture \
    --input backend/vital_signs_data_new.csv \
    --sleep-json backend/sleep_detection/output/sleep_report.json \
    --output backend/motion_posture/output

# Train posture model only
python -m backend.motion_posture.run_motion_posture --train-model
```

### Flask API

```
POST /motion-posture
Content-Type: application/json

{
  "userEmail": "user@example.com",
  "inputFile": "backend/vital_signs_data_new.csv",
  "format": "pipeline",
  "sleepJson": "backend/sleep_detection/output/sleep_report.json"
}
```

Response:

```json
{
  "success": true,
  "summary": { "posture_distribution_pct": { ... }, "motion_epoch_counts": { ... } },
  "epochs": [ ... ],
  "output_dir": "backend/motion_posture/output"
}
```

### Python API

```python
from backend.motion_posture.io_utils import load_pipeline_csv
from backend.motion_posture.features import extract_all_features
from backend.motion_posture.motion import classify_motion_segments
from backend.motion_posture.posture import predict_posture
from backend.motion_posture.context import align_context_with_events

data = load_pipeline_csv("backend/vital_signs_data_new.csv")
X, indices = extract_all_features(data)

motion = classify_motion_segments(
    data["motion_scores"], data["chest_disp"], data["timestamps"])

labels, confs = predict_posture(X)

posture_records = [
    {"epoch_index": k, "timestamp_start": data["timestamps"][s],
     "timestamp_end": data["timestamps"][e-1],
     "posture_label": labels[k], "posture_confidence": float(confs[k])}
    for k, (s, e) in enumerate(indices)
]

result = align_context_with_events(motion["epoch_records"], posture_records)
print(result["session_stats"])
```

## Module structure

```
backend/motion_posture/
├── __init__.py
├── config.py             # All tuneable parameters
├── features.py           # 34-dim epoch feature extraction
├── motion.py             # Threshold-based motion classification
├── posture.py            # RF posture classifier + heuristic fallback
├── context.py            # Context fusion with sleep events
├── io_utils.py           # CSV/JSON loaders and writers
├── visualize.py          # Timeline & summary plots
├── run_motion_posture.py # CLI entry point
├── README.md
└── tests/
    └── test_motion_posture.py   # 30 unit tests
```

## Parameters (config.py)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `EPOCH_DURATION_SEC` | 15 | Seconds per analysis window |
| `EPOCH_OVERLAP_FRAC` | 0.50 | Overlap fraction between epochs |
| `MOTION_STILL_MAX` | 0.10 | Score ≤ this → "Still" |
| `MOTION_MINOR_MAX` | 0.35 | Score ≤ this → "Minor Movement" |
| `MOTION_MAJOR_MAX` | 0.65 | Score ≤ this → "Major Movement" |
| `POSTURE_CONFIDENCE_MIN` | 0.35 | Below this → "Unknown" |
| `EVENT_LOOK_BACK_SEC` | 30 | Seconds before event to scan |
| `EVENT_LOOK_AHEAD_SEC` | 10 | Seconds after event to scan |

## Motion labels

| Label | Composite score range | Description |
|-------|----------------------|-------------|
| Still | 0.00 – 0.10 | Negligible movement |
| Minor Movement | 0.10 – 0.35 | Small limb/postural shifts |
| Major Movement | 0.35 – 0.65 | Rolling, sitting up |
| Turning | > 0.65 | Large body rotation |

## Posture labels

| Label | Radar signature |
|-------|-----------------|
| Supine | High chest amplitude, symmetric breathing, moderate range |
| Left Lateral | Negative chest skew, asymmetric signal |
| Right Lateral | Positive chest skew, asymmetric signal |
| Prone | Reduced breath amplitude, higher heart variability, closer range |
| Unknown | Low confidence or ambiguous pattern |

## Feature vector (34 dimensions)

- **30 stats**: `(mean, std, min, max, skew, kurtosis)` × 5 signals (chest displacement, breath waveform, heart waveform, combined signal, range)
- **4 extras**: mean motion score, mean RR BPM, mean HR BPM, epoch energy (RMS of combined)

## Output files

| File | Contents |
|------|----------|
| `motion_posture_report_<ts>.csv` | Per-epoch combined timeline |
| `motion_posture_report_<ts>.json` | Full structured report |
| `motion_timeline.png` | Motion type over time |
| `posture_timeline.png` | Posture label over time |
| `combined_context.png` | 3-panel: RR+events / posture / motion |
| `session_summary.png` | Pie + bar charts |

## Tests

```bash
python -m unittest backend.motion_posture.tests.test_motion_posture -v
```

30 tests covering: feature extraction, motion classification, posture
ML + heuristic, context fusion, I/O, and end-to-end integration.

## Dependencies

numpy, scipy, scikit-learn, pandas, matplotlib, joblib (all already
installed for the existing pipeline).
