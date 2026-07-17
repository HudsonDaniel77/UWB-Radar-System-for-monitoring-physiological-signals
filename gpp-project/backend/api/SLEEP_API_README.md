# Sleep Pattern REST API

## Overview

The Sleep Pattern API exposes RESTful endpoints for the Radarix Sleep Pattern dashboard.
It is implemented as a Flask Blueprint (`sleep_bp`) registered on the existing pipeline
server (port **5002**).

---

## Base URL

```
http://localhost:5002
```

---

## Endpoints

### 1. `GET /api/sleep/summary`

Returns the high-level sleep summary aggregated from all three analysis pipelines.

**Response (200):**

```json
{
  "success": true,
  "summary": {
    "generated_at": "2025-02-28T09:02:04",
    "total_duration_sec": 28800,
    "total_epochs": 960,
    "severity": "Mild",
    "apnea_events_per_hour": 7.5,
    "event_counts": { "normal": 800, "apnea": 80, "hypopnea": 80 },
    "event_time_sec": { "normal": 24000, "apnea": 2400, "hypopnea": 2400 },
    "baseline_amplitude": 0.42
  },
  "sleep_structure": {
    "total_duration_min": 480,
    "sleep_efficiency_pct": 88.5,
    "efficiency_rating": "Good",
    "time_per_stage_sec": { "Wake": 3600, "Light": 14400, "Deep": 5400, "REM": 5400 },
    "pct_per_stage": { "Wake": 12.5, "Light": 50.0, "Deep": 18.75, "REM": 18.75 },
    "stage_counts": { "Wake": 120, "Light": 480, "Deep": 180, "REM": 180 },
    "sleep_onset_latency_sec": 600,
    "rem_episodes": 4
  },
  "motion_stats": {
    "posture_distribution_pct": { "supine": 60, "lateral_left": 25, "lateral_right": 15 },
    "motion_epoch_counts": { "still": 800, "minor_movement": 120, "major_movement": 40 }
  }
}
```

---

### 2. `GET /api/sleep/events`

Returns per-epoch sleep event records from the latest sleep detection report.

**Response (200):**

```json
{
  "success": true,
  "events": [
    {
      "epoch_index": 0,
      "event_type": "normal",
      "RR_mean": 16.2,
      "HR_mean": 62.5,
      "duration_sec": 30,
      "timestamp_start": 0
    }
  ],
  "event_counts": { "normal": 800, "apnea": 80, "hypopnea": 80 },
  "severity": "Mild",
  "total_epochs": 960
}
```

---

### 3. `GET /api/sleep/stages`

Returns sleep staging epoch records and structure summary.

**Response (200):**

```json
{
  "success": true,
  "epoch_records": [
    { "epoch": 0, "stage": "Wake", "time_label": "0:00" }
  ],
  "sleep_structure": { "..." },
  "metrics": { "accuracy": 0.87, "kappa": 0.79 }
}
```

---

### 4. `GET /api/vitals`

Returns RR and HR time series extracted from sleep events.

**Response (200):**

```json
{
  "success": true,
  "timestamps": [0, 30, 60],
  "rr_bpm": [16.2, 15.8, 16.0],
  "hr_bpm": [62.5, 63.1, 61.8],
  "total_epochs": 960
}
```

---

### 5. `GET /api/motion`

Returns motion / posture timeline and session statistics.

**Response (200):**

```json
{
  "success": true,
  "timeline": [
    { "epoch": 0, "posture": "supine", "motion_level": "still", "time_label": "0:00" }
  ],
  "session_stats": {
    "posture_distribution_pct": { "supine": 60 },
    "motion_epoch_counts": { "still": 800 }
  },
  "total_epochs": 960
}
```

---

### 6. `GET /api/sleep/sessions`

Lists all available session output files.

**Response (200):**

```json
{
  "success": true,
  "sessions": [
    {
      "session_id": "20260228_090204",
      "source_file": "/path/to/sleep_report_20260228_090204.json",
      "module": "sleep_detection",
      "modified": 1740736924.5
    }
  ]
}
```

---

### 7. `GET /api/sleep/full-session`

Returns all data aggregated from the three pipelines in a single call.
This is the primary endpoint used by the Sleep Pattern dashboard on page load.

**Response (200):**

```json
{
  "success": true,
  "summary": { "..." },
  "events": [ "..." ],
  "vitals": { "timestamps": [], "rr_bpm": [], "hr_bpm": [] },
  "sleep_structure": { "..." },
  "staging_metrics": { "..." },
  "stage_epochs": [ "..." ],
  "motion_timeline": [ "..." ],
  "motion_stats": { "..." }
}
```

---

### 8. `POST /api/sleep/analyze`

Triggers the full sleep analysis pipeline (sleep detection → motion/posture → sleep staging).

**Request body (JSON):**

| Field        | Type   | Default                | Description                           |
| ------------ | ------ | ---------------------- | ------------------------------------- |
| inputFile    | string | (default CSV)          | Path to input CSV                     |
| format       | string | `"pipeline"`           | `"pipeline"` or `"live"`              |
| userEmail    | string | `""`                   | User identifier                       |
| trainModel   | bool   | `true`                 | Train staging model first             |
| modelType    | string | `"random_forest"`      | `"random_forest"` or `"xgboost"`     |

**Response (200):**

```json
{
  "success": true,
  "message": "Sleep analysis pipeline completed successfully",
  "results": {
    "sleep_summary": { "severity": "Mild", "total_epochs": 960 },
    "motion_summary": { "..." },
    "sleep_structure": { "sleep_efficiency_pct": 88.5 },
    "staging_metrics": { "accuracy": 0.87 }
  }
}
```

---

## Error Envelope

All endpoints return errors in a consistent format:

```json
{
  "success": false,
  "error": "Descriptive error message"
}
```

---

## Setup

```bash
cd backend
pip install -r requirements.txt
cd api
python pipeline.py          # starts on port 5002
```

The frontend Sleep Pattern page is available at `/sleep-pattern` after starting the Vite dev server:

```bash
npm run dev
```

---

## Frontend Pages

| Route                | Component              | Description                                    |
| -------------------- | ---------------------- | ---------------------------------------------- |
| `/run-sensor-sleep`  | `RunSensorSleep.jsx`   | Trigger sleep detection sensor and run analysis |
| `/sleep-pattern`     | `SleepPattern.jsx`     | Full sleep pattern analysis dashboard           |
