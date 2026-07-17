# Sleep Detection Pipeline – Integration Guide

## Overview

The **Sleep Detection** module analyses time-aligned respiration amplitude
and motion signals from the existing Radarix vital-signs pipeline to
produce **labelled sleep events**:

| Label        | Meaning |
|-------------|---------|
| **Normal**  | Respiration amplitude is stable relative to baseline |
| **Irregular** | Amplitude drops ≥ 30 % from baseline for a short period |
| **Apnea**   | Prolonged amplitude drop (≥ 3 consecutive epochs) |
| **Motion**  | Body motion artefact – breathing analysis is unreliable |

The module **does not** re-process raw radar frames. It consumes the CSV
files already produced by `vitalsigns.py` (or `allframes.py`) and extends
them with sleep-event labelling.

---

## File Structure

```
backend/sleep_detection/
├── __init__.py                 # package marker
├── config.py                   # configurable defaults
├── core.py                     # detect_sleep_events(), compute_baseline_rr(), mask_motion_segments()
├── io_utils.py                 # CSV / JSON loaders & writers
├── visualize.py                # matplotlib plots
├── run_sleep_detection.py      # standalone CLI entry-point
└── tests/
    ├── __init__.py
    └── test_sleep_detection.py # unit tests
```

---

## Quick Start

### 1. Prerequisites

```bash
pip install numpy pandas matplotlib scipy
```

(These are the same libraries already used by the existing pipeline.)

### 2. Run from Command Line

```bash
# From project root
cd "C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project"

# Using a pipeline CSV (vital_signs_data_new*.csv)
python -m backend.sleep_detection.run_sleep_detection \
  --input  backend/vital_signs_data_new.csv \
  --output backend/sleep_detection/output \
  --user   kevin2310172@ssn.edu.in

# Using a live-session CSV (vital_signs_live_session.csv)
python -m backend.sleep_detection.run_sleep_detection \
  --input  vital_signs_data/vital_signs_live_session.csv \
  --format live \
  --output backend/sleep_detection/output
```

### 3. Use as a Python Module

```python
from backend.sleep_detection.core import detect_sleep_events
from backend.sleep_detection.io_utils import load_pipeline_csv, save_sleep_report
from backend.sleep_detection.visualize import save_all_plots

# Load data from existing pipeline CSV
data = load_pipeline_csv("backend/vital_signs_data_new.csv",
                         user_email="user@example.com")

# Run detection
result = detect_sleep_events(
    rr_amplitude=data["rr_amplitude"],
    timestamps=data["timestamps"],
    motion_scores=data["motion_scores"],
    hr_values=data["hr_bpm"],
    sampling_rate=20.0,
)

# Save report (CSV + JSON)
paths = save_sleep_report(result, "backend/sleep_detection/output")

# Save plots (PNG)
plot_paths = save_all_plots(
    data["rr_amplitude"], data["timestamps"], result,
    motion_scores=data["motion_scores"],
    output_dir="backend/sleep_detection/output",
)

# Inspect summary
print(result["summary"])
# → { "severity": "Normal", "apnea_events_per_hour": 0, ... }
```

### 4. Call from the Flask API Pipeline

The module is integrated into `backend/api/pipeline.py` via the
`/sleep-detect` endpoint:

```bash
curl -X POST http://localhost:5002/sleep-detect \
  -H "Content-Type: application/json" \
  -d '{"userEmail": "user@example.com", "inputFile": "backend/vital_signs_data_new.csv"}'
```

Response:
```json
{
  "success": true,
  "summary": {
    "severity": "Normal",
    "apnea_events_per_hour": 0,
    "event_counts": {"Normal": 5, "Irregular": 0, "Apnea": 0, "Motion": 0}
  },
  "output_dir": "backend/sleep_detection/output",
  "events": [ ... ]
}
```

---

## Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `epoch_duration_sec` | 30 | Analysis window length (seconds) |
| `epoch_overlap_frac` | 0.50 | Overlap between consecutive windows |
| `baseline_window_sec` | 120 | Seconds of initial data used for baseline |
| `baseline_percentile` | 75 | Percentile of amplitude to set baseline |
| `amplitude_drop_threshold` | 0.30 | ≥ 30 % drop from baseline → abnormal |
| `apnea_min_consecutive` | 3 | Consecutive abnormal epochs → Apnea label |
| `motion_threshold` | 0.55 | Normalized motion score above this → artefact |
| `motion_guard_epochs` | 1 | Extra epochs masked around motion spikes |

All values can be overridden via CLI flags or keyword arguments to
`detect_sleep_events()`.

---

## Output Files

Each run creates timestamped files in the output directory:

| File | Contents |
|------|----------|
| `sleep_report_YYYYMMDD_HHMMSS.csv` | Per-epoch event table |
| `sleep_report_YYYYMMDD_HHMMSS.json` | Events + summary in JSON |
| `sleep_events_timeline.png` | Respiration amplitude with event bands |
| `sleep_summary_report.png` | Bar chart + pie chart of event distribution |

### CSV Columns

| Column | Type | Description |
|--------|------|-------------|
| `epoch_index` | int | Sequential epoch number |
| `timestamp_start` | float | Epoch start time (seconds) |
| `timestamp_end` | float | Epoch end time (seconds) |
| `event_type` | str | Normal / Irregular / Apnea / Motion |
| `RR_mean` | float | Mean respiration amplitude in epoch |
| `RR_std` | float | Std dev of respiration amplitude |
| `amplitude` | float | Peak-to-peak amplitude of epoch |
| `motion_score_mean` | float | Mean motion score in epoch |
| `HR_mean` | float | Mean heart rate (if available) |

---

## Severity Classification (AHI)

The **Apnea–Hypopnea Index** (events per hour) maps to severity:

| AHI Range | Severity |
|-----------|----------|
| 0 – 5 | Normal |
| 5 – 15 | Mild |
| 15 – 30 | Moderate |
| > 30 | Severe |

---

## Algorithm Summary

1. **Epoch windowing** – Signal is divided into 30 s windows with 50 %
   overlap.
2. **Baseline estimation** – The 75th percentile of absolute respiration
   amplitude from the first 120 s of low-motion data serves as the
   reference.
3. **Amplitude thresholding** – Any epoch whose peak-to-peak amplitude
   drops ≥ 30 % below baseline is flagged as abnormal.
4. **Motion masking** – Epochs where the motion score exceeds 0.55 are
   labelled "Motion" and are **never** classified as Apnea.
5. **Event merging** – Consecutive abnormal epochs (≥ 3) are upgraded
   from "Irregular" to "Apnea".

---

## Running Unit Tests

```bash
python -m pytest backend/sleep_detection/tests/ -v
```

All tests use synthetic sinusoidal data (no hardware required).

---

## Integration with RunSensor Frontend

The React `RunSensor.jsx` can call the `/sleep-detect` endpoint after the
normal sensor run completes. The returned `summary` and `events` arrays
can be displayed on the Sleep Detection page using the same chart
components already used for vital-signs waveforms.
