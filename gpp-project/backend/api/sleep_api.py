"""
backend/api/sleep_api.py
────────────────────────
Flask Blueprint providing RESTful endpoints for the Sleep Pattern page.

Endpoints
─────────
GET  /api/sleep/summary    → sleep summary (latest session)
GET  /api/sleep/events     → sleep event list
GET  /api/sleep/stages     → sleep staging / hypnogram
GET  /api/vitals           → vital sign time series (RR, HR)
GET  /api/motion           → motion / posture timeline
GET  /api/sleep/sessions   → list available sessions
POST /api/sleep/analyze    → trigger full sleep analysis pipeline
"""

from __future__ import annotations
import glob
import json
import os
import subprocess
import sys
from datetime import datetime
import traceback

from flask import Blueprint, jsonify, request

# ────────────────────────────────────────────────────────────────────
#  PATHS
# ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")

# Live sensor data collection script
VITALSIGNS_SCRIPT = os.path.join(BACKEND_DIR, "vitalsigns.py")

SLEEP_DETECTION_SCRIPT = os.path.join(BACKEND_DIR, "sleep_detection", "run_sleep_detection.py")
SLEEP_OUTPUT_DIR = os.path.join(BACKEND_DIR, "sleep_detection", "output")

MOTION_POSTURE_SCRIPT = os.path.join(BACKEND_DIR, "motion_posture", "run_motion_posture.py")
MOTION_OUTPUT_DIR = os.path.join(BACKEND_DIR, "motion_posture", "output")

SLEEP_STAGING_SCRIPT = os.path.join(BACKEND_DIR, "sleep_staging", "run_sleep_staging.py")
STAGING_OUTPUT_DIR = os.path.join(BACKEND_DIR, "sleep_staging", "output")

# This is the CSV that vitalsigns.py writes to — used as input for analysis
DEFAULT_INPUT = os.path.join(BACKEND_DIR, "vital_signs_data_new_tryingsomething.csv")
UPLOAD_DIR = os.path.join(BACKEND_DIR, "test_datasets", "uploaded_sleep_sessions")

# ────────────────────────────────────────────────────────────────────
#  BLUEPRINT
# ────────────────────────────────────────────────────────────────────
sleep_bp = Blueprint("sleep_api", __name__)

# Holds the CSV path from the most recent /api/sleep/collect call so
# /api/sleep/analyze can use it without re-running the sensor.
_last_session_csv: str | None = None
# Holds the most recently analyzed CSV path so /api/sleep/full-session
# can render raw vitals from the exact same file that produced reports.
_last_analyzed_csv: str | None = None


# ────────────────────────────────────────────────────────────────────
#  HELPERS
# ────────────────────────────────────────────────────────────────────
def _latest_json(directory: str, prefix: str) -> str | None:
    """Find the most recently modified JSON report in *directory*."""
    pattern = os.path.join(directory, f"{prefix}*.json")
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    return files[0] if files else None


def _load_json(path: str | None) -> dict:
    if path is None:
        return {}
    with open(path, encoding="utf-8") as f:
        # allow_nan=True so Python can parse files that contain bare NaN
        raw = json.loads(f.read())
    return _sanitize(raw)


def _sanitize(obj):
    """Recursively replace NaN/Inf with None so jsonify produces valid JSON."""
    import math
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def _ok(data: dict, **extra):
    """Standard success envelope."""
    return jsonify({"success": True, **data, **extra})


def _err(msg: str, status: int = 400):
    """Standard error envelope."""
    return jsonify({"success": False, "error": msg}), status


def _run_subprocess(script: str, args: list, timeout: int = 180):
    """Run a Python CLI script and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, script] + args
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _parse_block(stdout: str, begin: str, end: str) -> dict:
    """Extract the JSON block between two sentinel tags."""
    if begin in stdout and end in stdout:
        block = stdout.split(begin, 1)[1].split(end, 1)[0].strip()
        try:
            return json.loads(block)
        except Exception:
            pass
    return {}


def _parse_session_time(value) -> float | None:
    """Parse SessionTime values that may be numeric or HH:MM:SS strings."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        pass
    # Support values like HH:MM or HH:MM:SS(.ms)
    parts = s.split(":")
    if len(parts) in (2, 3):
        try:
            if len(parts) == 2:
                h = 0
                m, sec = parts
            else:
                h, m, sec = parts
            return float(h) * 3600.0 + float(m) * 60.0 + float(sec)
        except Exception:
            return None
    return None


# ────────────────────────────────────────────────────────────────────
#  GET  /api/sleep/summary
# ────────────────────────────────────────────────────────────────────
@sleep_bp.route("/api/sleep/summary", methods=["GET"])
def sleep_summary():
    """Return the high-level sleep pattern summary from the latest session."""
    try:
        # Gather latest reports from all three pipelines
        sleep_path = _latest_json(SLEEP_OUTPUT_DIR, "sleep_report_")
        staging_path = _latest_json(STAGING_OUTPUT_DIR, "sleep_staging_report_")
        motion_path = _latest_json(MOTION_OUTPUT_DIR, "motion_posture_report_")

        sleep_data = _load_json(sleep_path)
        staging_data = _load_json(staging_path)
        motion_data = _load_json(motion_path)

        summary = sleep_data.get("summary", {})
        sleep_structure = staging_data.get("sleep_structure", {})
        session_stats = motion_data.get("session_stats", {})

        return _ok({
            "summary": {
                "generated_at": sleep_data.get("generated_at", ""),
                "total_duration_sec": summary.get("total_duration_sec", 0),
                "total_epochs": summary.get("total_epochs", 0),
                "severity": summary.get("severity", "Unknown"),
                "apnea_events_per_hour": summary.get("apnea_events_per_hour", 0),
                "event_counts": summary.get("event_counts", {}),
                "event_time_sec": summary.get("event_time_sec", {}),
                "baseline_amplitude": summary.get("baseline_amplitude", 0),
            },
            "sleep_structure": {
                "total_duration_min": sleep_structure.get("total_duration_min", 0),
                "sleep_efficiency_pct": sleep_structure.get("sleep_efficiency_pct", 0),
                "efficiency_rating": sleep_structure.get("efficiency_rating", ""),
                "time_per_stage_sec": sleep_structure.get("time_per_stage_sec", {}),
                "pct_per_stage": sleep_structure.get("pct_per_stage", {}),
                "stage_counts": sleep_structure.get("stage_counts", {}),
                "sleep_onset_latency_sec": sleep_structure.get("sleep_onset_latency_sec", 0),
                "rem_episodes": sleep_structure.get("rem_episodes", 0),
            },
            "motion_stats": {
                "posture_distribution_pct": session_stats.get("posture_distribution_pct", {}),
                "motion_epoch_counts": session_stats.get("motion_epoch_counts", {}),
            },
        })
    except Exception as e:
        return _err(str(e), 500)


# ────────────────────────────────────────────────────────────────────
#  GET  /api/sleep/events
# ────────────────────────────────────────────────────────────────────
@sleep_bp.route("/api/sleep/events", methods=["GET"])
def sleep_events():
    """Return the list of per-epoch sleep event records."""
    try:
        path = _latest_json(SLEEP_OUTPUT_DIR, "sleep_report_")
        data = _load_json(path)
        events = data.get("events", [])
        summary = data.get("summary", {})
        return _ok({
            "events": events,
            "event_counts": summary.get("event_counts", {}),
            "severity": summary.get("severity", "Unknown"),
            "total_epochs": len(events),
        })
    except Exception as e:
        return _err(str(e), 500)


# ────────────────────────────────────────────────────────────────────
#  GET  /api/sleep/stages
# ────────────────────────────────────────────────────────────────────
@sleep_bp.route("/api/sleep/stages", methods=["GET"])
def sleep_stages():
    """Return sleep staging epoch records and structure summary."""
    try:
        path = _latest_json(STAGING_OUTPUT_DIR, "sleep_staging_report_")
        data = _load_json(path)
        return _ok({
            "epoch_records": data.get("epoch_records", []),
            "sleep_structure": data.get("sleep_structure", {}),
            "metrics": data.get("metrics", {}),
        })
    except Exception as e:
        return _err(str(e), 500)


# ────────────────────────────────────────────────────────────────────
#  GET  /api/vitals
# ────────────────────────────────────────────────────────────────────
@sleep_bp.route("/api/vitals", methods=["GET"])
def vitals():
    """Return vital sign time series (RR, HR) from the sleep event data."""
    try:
        path = _latest_json(SLEEP_OUTPUT_DIR, "sleep_report_")
        data = _load_json(path)
        events = data.get("events", [])

        timestamps = []
        rr_series = []
        hr_series = []

        for e in events:
            ts_start = e.get("timestamp_start", 0)
            timestamps.append(ts_start)
            rr_series.append(e.get("RR_mean"))
            hr_series.append(e.get("HR_mean"))

        return _ok({
            "timestamps": timestamps,
            "rr_bpm": rr_series,
            "hr_bpm": hr_series,
            "total_epochs": len(events),
        })
    except Exception as e:
        return _err(str(e), 500)


# ────────────────────────────────────────────────────────────────────
#  GET  /api/motion
# ────────────────────────────────────────────────────────────────────
@sleep_bp.route("/api/motion", methods=["GET"])
def motion():
    """Return motion / posture context timeline."""
    try:
        path = _latest_json(MOTION_OUTPUT_DIR, "motion_posture_report_")
        data = _load_json(path)
        timeline = data.get("combined_timeline", [])
        stats = data.get("session_stats", {})
        return _ok({
            "timeline": timeline,
            "session_stats": stats,
            "total_epochs": len(timeline),
        })
    except Exception as e:
        return _err(str(e), 500)


# ────────────────────────────────────────────────────────────────────
#  GET  /api/sleep/sessions
# ────────────────────────────────────────────────────────────────────
@sleep_bp.route("/api/sleep/sessions", methods=["GET"])
def list_sessions():
    """List all available sessions with timestamps."""
    try:
        sessions = []

        # Scan sleep_detection output
        pattern = os.path.join(SLEEP_OUTPUT_DIR, "sleep_report_*.json")
        for fp in sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True):
            name = os.path.basename(fp)
            # Extract timestamp from filename: sleep_report_20260228_090204.json
            parts = name.replace("sleep_report_", "").replace(".json", "")
            sessions.append({
                "session_id": parts,
                "source_file": fp,
                "module": "sleep_detection",
                "modified": os.path.getmtime(fp),
            })

        return _ok({"sessions": sessions})
    except Exception as e:
        return _err(str(e), 500)


# ────────────────────────────────────────────────────────────────────
#  GET  /api/sleep/full-session
# ────────────────────────────────────────────────────────────────────
@sleep_bp.route("/api/sleep/full-session", methods=["GET"])
def full_session():
    """Return aggregated data from all three pipelines for the latest session."""
    global _last_analyzed_csv
    try:
        explicit_session_path = request.args.get("sessionCsvPath", "").strip()
        sleep_path = _latest_json(SLEEP_OUTPUT_DIR, "sleep_report_")
        staging_path = _latest_json(STAGING_OUTPUT_DIR, "sleep_staging_report_")
        motion_path = _latest_json(MOTION_OUTPUT_DIR, "motion_posture_report_")

        sleep_data = _load_json(sleep_path)
        staging_data = _load_json(staging_path)
        motion_data = _load_json(motion_path)

        events = sleep_data.get("events", [])

        # ── Dense vitals: read raw RR/HR from the analyzed CSV if available ──
        # Epoch-level events give only 1 point per 30 s; the raw CSV has one
        # row per radar frame (~20 fps) which produces a smooth, readable chart.
        import csv as _csv
        dense_vitals = None
        csv_duration_sec = None
        try:
            source_csv = explicit_session_path or _last_analyzed_csv
            if not source_csv or not os.path.isfile(source_csv):
                # Prefer uploaded analysis inputs before short live-session captures.
                uploaded_pattern = os.path.join(UPLOAD_DIR, "*.csv")
                uploaded_files = sorted(glob.glob(uploaded_pattern), key=os.path.getmtime)
                if uploaded_files:
                    source_csv = uploaded_files[-1]
                else:
                    live_pattern = os.path.join(BACKEND_DIR, "vital_signs_session_*.csv")
                    live_files = sorted(glob.glob(live_pattern), key=os.path.getmtime)
                    source_csv = live_files[-1] if live_files else None

            if source_csv and os.path.isfile(source_csv):
                ts_list, rr_list, hr_list = [], [], []
                with open(source_csv, newline="", encoding="utf-8",
                          errors="replace") as f:
                    reader = _csv.DictReader(f)
                    for row in reader:
                        try:
                            t = _parse_session_time(row.get("SessionTime", ""))
                            if t is None:
                                continue
                            rr = float(row.get("RespirationRate_BPM", ""))
                            hr = float(row.get("HeartRate_BPM", ""))
                            ts_list.append(round(t,  2))
                            rr_list.append(round(rr, 2))
                            hr_list.append(round(hr, 2))
                        except (ValueError, TypeError):
                            continue
                if len(ts_list) > 1:
                    # Ensure monotonically increasing timeline for chart axis.
                    trio = sorted(zip(ts_list, rr_list, hr_list), key=lambda x: x[0])
                    ts_list = [x[0] for x in trio]
                    rr_list = [x[1] for x in trio]
                    hr_list = [x[2] for x in trio]
                    csv_duration_sec = max(0.0, ts_list[-1] - ts_list[0])
                    dense_vitals = {
                        "timestamps": ts_list,
                        "rr_bpm":     rr_list,
                        "hr_bpm":     hr_list,
                    }
        except Exception:
            pass

        # Fall back to epoch-level averages when no session CSV is found
        if dense_vitals is None:
            dense_vitals = {
                "timestamps": [e.get("timestamp_start", 0) for e in events],
                "rr_bpm":     [e.get("RR_mean") for e in events],
                "hr_bpm":     [e.get("HR_mean") for e in events],
            }

        summary = dict(sleep_data.get("summary", {}))
        if csv_duration_sec and csv_duration_sec > 0:
            summary["total_duration_sec"] = round(csv_duration_sec, 2)

        return _ok({
            "summary": summary,
            "events": events,
            "vitals": dense_vitals,
            "source_csv": source_csv,
            "sleep_structure": staging_data.get("sleep_structure", {}),
            "staging_metrics": staging_data.get("metrics", {}),
            "stage_epochs": staging_data.get("epoch_records", []),
            "motion_timeline": motion_data.get("combined_timeline", []),
            "motion_stats": motion_data.get("session_stats", {}),
        })
    except Exception as e:
        return _err(str(e), 500)


# ────────────────────────────────────────────────────────────────────
#  POST  /api/sleep/collect   – Step 1: run the sensor only
# ────────────────────────────────────────────────────────────────────
@sleep_bp.route("/api/sleep/collect", methods=["POST"])
def collect():
    """
    Collect live radar data via vitalsigns.py (~30 s).
    Returns the same payload as /run-sensor so the frontend can show
    a waveform + stats popup.

    Body:
        userEmail     : str  – user identifier  (REQUIRED)
        configuration : int  – 0 = Front, 1 = Back  (REQUIRED)
    """
    global _last_session_csv

    try:
        body = request.get_json(force=True) if request.data else {}

        user_email    = body.get("userEmail", "")
        config_number = body.get("configuration")
        duration      = int(body.get("duration", 120))   # seconds to collect

        if not user_email:
            return _err("Missing userEmail", 400)
        if config_number is None:
            return _err("Missing configuration (0=Front, 1=Back)", 400)

        collect_cmd = [sys.executable, VITALSIGNS_SCRIPT,
                       user_email, str(config_number), str(duration)]
        # MPLBACKEND=Agg prevents plt.show() from blocking in headless mode
        collect_env = {**os.environ, "MPLBACKEND": "Agg"}

        proc_timeout = duration + 60   # allow 60 s overhead on top of collection
        try:
            proc = subprocess.Popen(
                collect_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=collect_env,
            )
            out, err = proc.communicate(timeout=proc_timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            return _err(f"Sensor data collection timed out ({proc_timeout} s)", 504)

        if proc.returncode != 0:
            error_detail = "\n".join(filter(None, [
                err.strip(), out.strip(),
            ])) or "No output from sensor script."
            return _err(f"Sensor data collection failed:\n{error_detail}", 500)

        # ── Parse CSV path (CSV_PATH_BEGIN / CSV_PATH_END) ─────────
        session_csv = DEFAULT_INPUT
        if "CSV_PATH_BEGIN" in out and "CSV_PATH_END" in out:
            parsed = (
                out.split("CSV_PATH_BEGIN", 1)[1]
                   .split("CSV_PATH_END",   1)[0]
                   .strip()
            )
            if parsed and os.path.isfile(parsed):
                session_csv = parsed

        # Remember it for the subsequent /api/sleep/analyze call
        _last_session_csv = session_csv

        # ── Parse waveform + stats (STATS_BEGIN / STATS_END) ───────
        stats_text = ""
        waveform   = {}
        if "STATS_BEGIN" in out and "STATS_END" in out:
            raw = (
                out.split("STATS_BEGIN", 1)[1]
                   .split("STATS_END",   1)[0]
                   .strip()
            )
            try:
                payload = json.loads(raw)
                stats_text = payload.get("stats_text", "")
                waveform   = payload.get("waveform",   {})
            except json.JSONDecodeError:
                stats_text = raw  # surface raw text if JSON is malformed

        return _ok({
            "stats_text":   stats_text,
            "waveform":     waveform,
            "session_csv":  session_csv,
        })

    except Exception as e:
        return _err(str(e), 500)


# ────────────────────────────────────────────────────────────────────
#  POST  /api/sleep/analyze   – Step 2: run the analysis pipeline
# ────────────────────────────────────────────────────────────────────
@sleep_bp.route("/api/sleep/analyze", methods=["POST"])
def analyze():
    """
    Run the three-step sleep analysis pipeline on already-collected data.
      1. Sleep event detection
      2. Motion / posture context
      3. Sleep stage classification

    Body:
        userEmail      : str  – user identifier  (optional)
        sessionCsvPath : str  – path returned by /api/sleep/collect
                                (falls back to last collected file, then
                                 DEFAULT_INPUT)
        format         : str  – "pipeline" | "live"  (optional)
        trainModel     : bool – train staging model first (default true)
        modelType      : str  – "random_forest" | "xgboost" (default rf)
    """
    global _last_session_csv, _last_analyzed_csv

    try:
        body = request.get_json(force=True) if request.data else {}

        user_email   = body.get("userEmail", "")
        csv_format   = body.get("format", "pipeline")
        train_model  = body.get("trainModel", True)
        model_type   = body.get("modelType", "random_forest")
        explicit_session_path = (
            body.get("sessionCsvPath")
            or body.get("session_csv_path")
            or body.get("session_csv")
            or body.get("sessionCsv")
        )
        disable_user_filter = bool(body.get("disableUserFilter", False))

        # Resolve which CSV to analyze:
        # 1. explicit path from body
        # 2. last path stored by /api/sleep/collect
        # 3. master DEFAULT_INPUT as fallback
        input_file = (
            explicit_session_path
            or _last_session_csv
            or DEFAULT_INPUT
        )
        if not os.path.isfile(input_file):
            return _err(f"Input CSV not found: {input_file}. "
                        "Run the sensor first.", 404)

        _last_analyzed_csv = input_file

        results = {}

        # ── Step 1: Sleep event detection ──────────────────────────
        args = ["--input", input_file, "--output", SLEEP_OUTPUT_DIR,
                "--format", csv_format]
        # For explicitly uploaded files, avoid filtering by logged-in user
        # unless the caller explicitly asks for it.
        if explicit_session_path and os.path.abspath(explicit_session_path).startswith(os.path.abspath(UPLOAD_DIR)):
            apply_user_filter = False
        else:
            apply_user_filter = bool(user_email and not explicit_session_path and not disable_user_filter)
        if apply_user_filter:
            args += ["--user", user_email]

        rc, stdout, stderr = _run_subprocess(SLEEP_DETECTION_SCRIPT, args)
        if rc != 0 and apply_user_filter and "No rows found" in (stderr or ""):
            # Uploaded/shared datasets often contain a different user email.
            # Retry once without user filtering instead of failing hard.
            retry_args = ["--input", input_file, "--output", SLEEP_OUTPUT_DIR,
                          "--format", csv_format]
            rc, stdout, stderr = _run_subprocess(SLEEP_DETECTION_SCRIPT, retry_args)
        if rc != 0:
            return _err(f"Sleep detection failed: {stderr}", 500)

        sleep_result = _parse_block(stdout, "SLEEP_RESULT_BEGIN", "SLEEP_RESULT_END")
        results["sleep_summary"] = sleep_result.get("summary", {})

        sleep_json = _latest_json(SLEEP_OUTPUT_DIR, "sleep_report_") or ""

        # ── Step 2: Motion / posture context ───────────────────────
        args2 = ["--input", input_file, "--output", MOTION_OUTPUT_DIR,
                 "--format", csv_format]
        if apply_user_filter:
            args2 += ["--user", user_email]
        if sleep_json:
            args2 += ["--sleep-json", sleep_json]

        rc2, stdout2, stderr2 = _run_subprocess(MOTION_POSTURE_SCRIPT, args2)
        if rc2 != 0:
            return _err(f"Motion/posture failed: {stderr2}", 500)

        mp_result = _parse_block(stdout2, "MOTION_POSTURE_RESULT_BEGIN",
                                 "MOTION_POSTURE_RESULT_END")
        results["motion_summary"] = mp_result.get("summary", {})

        posture_json = _latest_json(MOTION_OUTPUT_DIR, "motion_posture_report_") or ""

        # ── Step 3: Sleep staging ──────────────────────────────────
        args3 = ["--input", input_file, "--output", STAGING_OUTPUT_DIR,
                 "--format", csv_format, "--model-type", model_type]
        if apply_user_filter:
            args3 += ["--user", user_email]
        if train_model:
            args3.append("--train-model")
        if sleep_json:
            args3 += ["--sleep-json", sleep_json]
        if posture_json:
            args3 += ["--posture-json", posture_json]

        rc3, stdout3, stderr3 = _run_subprocess(SLEEP_STAGING_SCRIPT, args3,
                                                timeout=300)
        if rc3 != 0:
            return _err(f"Sleep staging failed: {stderr3}", 500)

        staging_result = _parse_block(stdout3, "SLEEP_STAGING_RESULT_BEGIN",
                                      "SLEEP_STAGING_RESULT_END")
        results["sleep_structure"]  = staging_result.get("sleep_structure", {})
        results["staging_metrics"]  = staging_result.get("metrics", {})

        return _ok({
            "message": "Sleep analysis pipeline completed successfully",
            "results": results,
        })

    except subprocess.TimeoutExpired:
        return _err("Analysis timed out — try a smaller input file", 504)
    except Exception as e:
        return _err(str(e), 500)


# ────────────────────────────────────────────────────────────────────
#  POST  /api/sleep/upload-session  – upload CSV/XLSX for analysis
# ────────────────────────────────────────────────────────────────────
@sleep_bp.route("/api/sleep/upload-session", methods=["POST"])
def upload_session():
    """Upload a sleep-session CSV/XLSX and return normalized CSV path."""
    global _last_session_csv

    try:
        if "file" not in request.files:
            return _err("No file uploaded. Expected form-data field 'file'.", 400)

        file = request.files["file"]
        if not file or not file.filename:
            return _err("Uploaded file is empty.", 400)

        original_name = os.path.basename(file.filename)
        safe_name = "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in original_name)
        ext = os.path.splitext(safe_name)[1].lower()
        if ext not in (".csv", ".xlsx", ".xls"):
            return _err("Unsupported file type. Use .csv, .xlsx, or .xls", 400)

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.splitext(safe_name)[0]
        original_path = os.path.join(UPLOAD_DIR, f"{base}_{stamp}{ext}")
        file.save(original_path)

        csv_path = original_path
        if ext in (".xlsx", ".xls"):
            import pandas as pd

            df = pd.read_excel(original_path)
            csv_path = os.path.join(UPLOAD_DIR, f"{base}_{stamp}.csv")
            df.to_csv(csv_path, index=False)

        _last_session_csv = csv_path

        return _ok({
            "message": "Session dataset uploaded successfully",
            "session_csv_path": csv_path,
            "original_file": original_path,
        })
    except Exception as e:
        return _err(f"Upload failed: {str(e)}", 500)
