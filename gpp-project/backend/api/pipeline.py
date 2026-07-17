from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import subprocess
import sys
import io
import csv
import os
import traceback
import json

# ------------------------------------------------------------
# UTF-8 FIX
# ------------------------------------------------------------
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

app = Flask(__name__)
CORS(app)

# Register Sleep Pattern REST API Blueprint
try:
    from sleep_api import sleep_bp
except ImportError:
    from api.sleep_api import sleep_bp
app.register_blueprint(sleep_bp)

# ------------------------------------------------------------
# BASE PATHS
# The correct path: pipeline.py is in gpp-project/backend/api/
# So we need to go up 3 levels to get to gpp-project/ (the project root)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE_DIR = PROJECT_ROOT
BACKEND_DIR = os.path.join(BASE_DIR, "backend")

VITALSIGNS_SCRIPT = os.path.join(BACKEND_DIR, "vitalsigns.py")
CLEAN_SCRIPT = os.path.join(BASE_DIR, "data_analysis", "cleaning_data.py")
CALIBRATION_SCRIPT = os.path.join(BASE_DIR, "data_analysis", "calibration.py")
MODEL_SCRIPT = os.path.join(BASE_DIR, "data_analysis", "predict_with_model.py")

USERS_FILE = os.path.join(BACKEND_DIR, "users.csv")

# ------------------------------------------------------------
# BEHIND-WALL PATHS
# ------------------------------------------------------------
BW_VITALSIGNS_SCRIPT = os.path.join(BASE_DIR, "backend", "behindwall", "vitalsigns.py")
BW_CLEAN_SCRIPT = os.path.join(BASE_DIR, "data_analysis", "behindwall", "cleaning_data.py")
BW_MODEL_SCRIPT = os.path.join(BASE_DIR, "data_analysis", "behindwall", "predict_with_model.py")
BW_MASTER_FILE = os.path.join(BASE_DIR, "backend", "vital_signs_data_new.csv")

# ------------------------------------------------------------
# USER CHECK
# ------------------------------------------------------------
def user_exists(email):
    if not os.path.exists(USERS_FILE):
        return False

    with open(USERS_FILE, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if row and row[0].strip().lower() == email.lower():
                return True
    return False


# ------------------------------------------------------------
# RUN SENSOR PIPELINE
# ------------------------------------------------------------
@app.post("/run-sensor")
def run_sensor():
    try:
        data = request.get_json()
        user_email = data.get("userEmail")
        config_number = data.get("configuration")

        if not user_email or config_number is None:
            return jsonify({
                "success": False,
                "error": "Missing userEmail or configuration"
            })

        if not user_exists(user_email):
            return jsonify({
                "success": False,
                "error": "User does not exist. Please sign up first."
            })

        # ----------------------------------------------------
        # 1️⃣ RUN VITAL SIGNS (DATA COLLECTION)
        # ----------------------------------------------------
        process = subprocess.Popen(
            [sys.executable, VITALSIGNS_SCRIPT, user_email, str(config_number)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        stdout, stderr = process.communicate()

        if process.returncode != 0:
            return jsonify({
                "success": False,
                "error": stderr or stdout
            })

        # ----------------------------------------------------
        # 2️⃣ EXTRACT STATS TEXT (ROBUST)
        # ----------------------------------------------------
        stats_text = "No stats returned."
        waveform_data = {}

        if "STATS_BEGIN" in stdout and "STATS_END" in stdout:
            try:
                block = stdout.split("STATS_BEGIN", 1)[1]
                block = block.split("STATS_END", 1)[0].strip()
                stats_json = json.loads(block)
                stats_text = stats_json.get("stats_text", stats_text)
                waveform_data = stats_json.get("waveform", {})
            except Exception as e:
                stats_text = f"Stats parsing failed: {str(e)}"

        # ----------------------------------------------------
        # 3️⃣ CLEANING (FRAME-LEVEL)
        # ----------------------------------------------------
        subprocess.run(
            [sys.executable, CLEAN_SCRIPT],
            check=True
        )

        # ----------------------------------------------------
        # 4️⃣ CALIBRATION (RUN-LEVEL → FINAL STATS CSV)
        # ----------------------------------------------------
        subprocess.run(
            [sys.executable, CALIBRATION_SCRIPT],
            check=True
        )

        # ----------------------------------------------------
        # 5️⃣ ML INFERENCE
        # ----------------------------------------------------
        raw_output = subprocess.check_output(
            [sys.executable, MODEL_SCRIPT],
            text=True
        ).strip()

        try:
            ml_results = json.loads(raw_output)
        except Exception:
            ml_results = {"raw_output": raw_output}

        # ----------------------------------------------------
        # FINAL RESPONSE
        # ----------------------------------------------------
        return jsonify({
            "success": True,
            "stats_text": stats_text,
            "ml_results": ml_results,
            "waveform": waveform_data
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "trace": traceback.format_exc()
        })


# ------------------------------------------------------------
# MANUAL PIPELINE (UPLOAD → CLEAN → CALIBRATE → ML)
# ------------------------------------------------------------
@app.post("/run_pipeline")
def run_pipeline():
    try:
        subprocess.run([sys.executable, CLEAN_SCRIPT], check=True)
        subprocess.run([sys.executable, CALIBRATION_SCRIPT], check=True)

        raw_output = subprocess.check_output(
            [sys.executable, MODEL_SCRIPT],
            text=True
        ).strip()

        try:
            ml_results = json.loads(raw_output)
        except:
            ml_results = {"raw_output": raw_output}

        return jsonify({
            "message": "Pipeline completed successfully",
            "ml_results": ml_results
        })

    except Exception as e:
        return jsonify({
            "error": "Pipeline error",
            "details": str(e),
            "trace": traceback.format_exc()
        })


# ============================================================
# BEHIND-WALL ROUTES (merged from port 5005)
# ============================================================

@app.post("/bw/run-sensor")
def bw_run_sensor():
    try:
        data = request.get_json()
        user_email = data.get("userEmail")
        config_number = data.get("configuration")

        if not user_email or config_number is None:
            return jsonify({"success": False, "error": "Missing userEmail or configuration"})

        if not user_exists(user_email):
            return jsonify({"success": False, "error": "User does not exist. Please sign up first."})

        # RUN BEHIND-WALL SENSOR SCRIPT
        process = subprocess.Popen(
            [sys.executable, BW_VITALSIGNS_SCRIPT, user_email, str(config_number)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        stdout, stderr = process.communicate()

        if process.returncode != 0:
            return jsonify({"success": False, "error": stderr or stdout})

        # EXTRACT STATS BLOCK (includes waveform data)
        stats_text = "No stats returned."
        waveform_data = {}
        collecting = False
        json_buffer = ""

        for line in stdout.splitlines():
            if "STATS_BEGIN" in line:
                collecting = True
                continue
            if "STATS_END" in line:
                break
            if collecting:
                json_buffer += line

        try:
            stats_json = json.loads(json_buffer)
            stats_text = stats_json.get("stats_text", "No stats found.")
            waveform_data = stats_json.get("waveform", {})
        except:
            pass

        # RUN BEHIND-WALL CLEANING
        subprocess.run([sys.executable, BW_CLEAN_SCRIPT], check=True)

        # RUN BEHIND-WALL ML MODEL
        raw_output = subprocess.check_output(
            [sys.executable, BW_MODEL_SCRIPT], text=True
        ).strip()

        try:
            ml_results = json.loads(raw_output)
        except:
            ml_results = {"raw_output": raw_output}

        return jsonify({
            "success": True,
            "stats_text": stats_text,
            "ml_results": ml_results,
            "waveform": waveform_data
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "trace": traceback.format_exc()
        })


@app.post("/bw/upload")
def bw_upload_csv():
    try:
        file = request.files.get("file")
        if file is None:
            return jsonify({"error": "No file uploaded"}), 400

        df = pd.read_csv(file)
        df.to_csv(BW_MASTER_FILE, mode="a", header=False, index=False)

        return jsonify({"message": "File received and appended!"})

    except Exception as e:
        return jsonify({"error": str(e), "trace": traceback.format_exc()})


@app.post("/bw/run_pipeline")
def bw_run_pipeline():
    try:
        subprocess.run([sys.executable, BW_CLEAN_SCRIPT], check=True)

        raw_output = subprocess.check_output(
            [sys.executable, BW_MODEL_SCRIPT], text=True
        ).strip()

        try:
            ml_results = json.loads(raw_output)
        except:
            ml_results = {"raw_output": raw_output}

        return jsonify({
            "message": "Behind-wall pipeline completed",
            "ml_results": ml_results
        })

    except Exception as e:
        return jsonify({
            "error": "Pipeline error",
            "details": str(e),
            "trace": traceback.format_exc()
        })


# ------------------------------------------------------------
# SLEEP DETECTION
# ------------------------------------------------------------
SLEEP_DETECTION_SCRIPT = os.path.join(BASE_DIR, "backend", "sleep_detection", "run_sleep_detection.py")
SLEEP_OUTPUT_DIR = os.path.join(BASE_DIR, "backend", "sleep_detection", "output")

@app.post("/sleep-detect")
def sleep_detect():
    """Run the sleep‑event detection pipeline on an existing CSV."""
    try:
        data = request.get_json() or {}
        user_email = data.get("userEmail")
        input_file = data.get("inputFile")
        csv_format = data.get("format", "pipeline")   # "pipeline" or "live"

        # Default input file
        if not input_file:
            input_file = os.path.join(BASE_DIR, "backend",
                                      "vital_signs_data_new_tryingsomething.csv")

        if not os.path.isfile(input_file):
            return jsonify({"success": False,
                            "error": f"Input file not found: {input_file}"})

        cmd = [
            sys.executable, SLEEP_DETECTION_SCRIPT,
            "--input", input_file,
            "--output", SLEEP_OUTPUT_DIR,
            "--format", csv_format,
        ]
        if user_email:
            cmd += ["--user", user_email]

        proc = subprocess.run(cmd, capture_output=True, text=True)

        if proc.returncode != 0:
            return jsonify({"success": False,
                            "error": proc.stderr or proc.stdout})

        # Parse structured output
        stdout = proc.stdout
        sleep_result = {}
        if "SLEEP_RESULT_BEGIN" in stdout and "SLEEP_RESULT_END" in stdout:
            block = stdout.split("SLEEP_RESULT_BEGIN", 1)[1]
            block = block.split("SLEEP_RESULT_END", 1)[0].strip()
            try:
                sleep_result = json.loads(block)
            except Exception:
                pass

        return jsonify({
            "success": True,
            "summary": sleep_result.get("summary", {}),
            "output_dir": sleep_result.get("output_dir", SLEEP_OUTPUT_DIR),
            "raw_output": stdout,
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "trace": traceback.format_exc()
        })


# ------------------------------------------------------------
# MOTION / POSTURE CONTEXT DETECTION
# ------------------------------------------------------------
MOTION_POSTURE_SCRIPT = os.path.join(BACKEND_DIR, "motion_posture", "run_motion_posture.py")
MOTION_POSTURE_OUTPUT_DIR = os.path.join(BACKEND_DIR, "motion_posture", "output")

@app.post("/motion-posture")
def run_motion_posture():
    """Run motion & posture context pipeline on the latest CSV."""
    try:
        body = request.get_json(silent=True) or {}
        user_email = body.get("userEmail", "")
        input_file = body.get("inputFile", "")
        out_format = body.get("format", "pipeline")       # pipeline | live
        sleep_json = body.get("sleepJson", "")             # optional sleep report

        # Resolve input --------------------------------------------------
        if not input_file:
            if out_format == "live":
                input_file = os.path.join(
                    os.path.dirname(BACKEND_DIR), "vital_signs_data", "vital_signs_live_session.csv"
                )
            else:
                input_file = os.path.join(BACKEND_DIR, "vital_signs_data_new.csv")

        if not os.path.isfile(input_file):
            return jsonify({"success": False, "error": f"Input file not found: {input_file}"})

        # Build command ---------------------------------------------------
        cmd = [
            sys.executable, MOTION_POSTURE_SCRIPT,
            "--input", input_file,
            "--output", MOTION_POSTURE_OUTPUT_DIR,
            "--format", out_format,
        ]
        if user_email:
            cmd += ["--user", user_email]
        if sleep_json and os.path.isfile(sleep_json):
            cmd += ["--sleep-json", sleep_json]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        stdout = result.stdout
        stderr = result.stderr

        if result.returncode != 0:
            return jsonify({
                "success": False,
                "error": f"Motion/posture script failed (exit {result.returncode})",
                "stderr": stderr,
                "stdout": stdout,
            })

        # Parse structured result -----------------------------------------
        mp_result = {}
        begin_tag = "MOTION_POSTURE_RESULT_BEGIN"
        end_tag   = "MOTION_POSTURE_RESULT_END"
        if begin_tag in stdout and end_tag in stdout:
            block = stdout.split(begin_tag)[1].split(end_tag)[0].strip()
            try:
                mp_result = json.loads(block)
            except Exception:
                pass

        return jsonify({
            "success": True,
            "summary": mp_result.get("summary", {}),
            "epochs": mp_result.get("epochs", []),
            "output_dir": mp_result.get("output_dir", MOTION_POSTURE_OUTPUT_DIR),
            "raw_output": stdout,
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "trace": traceback.format_exc(),
        })


# ------------------------------------------------------------
# SLEEP STAGE CLASSIFICATION
# ------------------------------------------------------------
SLEEP_STAGING_SCRIPT = os.path.join(BACKEND_DIR, "sleep_staging", "run_sleep_staging.py")
SLEEP_STAGING_OUTPUT_DIR = os.path.join(BACKEND_DIR, "sleep_staging", "output")

@app.post("/sleep-staging")
def run_sleep_staging():
    """Run the sleep-stage classification pipeline."""
    try:
        body = request.get_json(silent=True) or {}
        user_email = body.get("userEmail", "")
        input_file = body.get("inputFile", "")
        out_format = body.get("format", "pipeline")
        model_type = body.get("modelType", "random_forest")
        train_model = body.get("trainModel", True)
        full_stages = body.get("fullStages", False)
        sleep_json = body.get("sleepJson", "")
        posture_json = body.get("postureJson", "")

        # Resolve input
        if not input_file:
            if out_format == "live":
                input_file = os.path.join(
                    os.path.dirname(BACKEND_DIR), "vital_signs_data",
                    "vital_signs_live_session.csv",
                )
            else:
                input_file = os.path.join(BACKEND_DIR, "vital_signs_data_new.csv")

        if not os.path.isfile(input_file):
            return jsonify({"success": False,
                            "error": f"Input file not found: {input_file}"})

        # Build command
        cmd = [
            sys.executable, SLEEP_STAGING_SCRIPT,
            "--input", input_file,
            "--output", SLEEP_STAGING_OUTPUT_DIR,
            "--format", out_format,
            "--model-type", model_type,
        ]
        if user_email:
            cmd += ["--user", user_email]
        if train_model:
            cmd.append("--train-model")
        if full_stages:
            cmd.append("--full-stages")
        if sleep_json and os.path.isfile(sleep_json):
            cmd += ["--sleep-json", sleep_json]
        if posture_json and os.path.isfile(posture_json):
            cmd += ["--posture-json", posture_json]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        stdout = result.stdout
        stderr = result.stderr

        if result.returncode != 0:
            return jsonify({
                "success": False,
                "error": f"Sleep staging script failed (exit {result.returncode})",
                "stderr": stderr,
                "stdout": stdout,
            })

        # Parse structured result
        staging_result = {}
        begin_tag = "SLEEP_STAGING_RESULT_BEGIN"
        end_tag = "SLEEP_STAGING_RESULT_END"
        if begin_tag in stdout and end_tag in stdout:
            block = stdout.split(begin_tag)[1].split(end_tag)[0].strip()
            try:
                staging_result = json.loads(block)
            except Exception:
                pass

        return jsonify({
            "success": True,
            "sleep_structure": staging_result.get("sleep_structure", {}),
            "metrics": staging_result.get("metrics", {}),
            "epoch_records": staging_result.get("epoch_records", []),
            "output_dir": staging_result.get("output_dir", SLEEP_STAGING_OUTPUT_DIR),
            "raw_output": stdout,
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "trace": traceback.format_exc(),
        })


# ------------------------------------------------------------
# VALIDATION & BENCHMARKING
# ------------------------------------------------------------
VALIDATION_SCRIPT = os.path.join(BACKEND_DIR, "validation", "run_validation.py")
VALIDATION_OUTPUT_DIR = os.path.join(BACKEND_DIR, "validation", "output")


# ------------------------------------------------------------
# ML-ENHANCED TRAINING
# ------------------------------------------------------------
ML_ENHANCED_SCRIPT = os.path.join(BACKEND_DIR, "ml_enhanced", "run_training.py")
ML_ENHANCED_OUTPUT_DIR = os.path.join(BACKEND_DIR, "ml_enhanced", "output")

@app.route("/ml-enhanced/train", methods=["POST"])
def run_ml_enhanced_train():
    """
    Train enhanced ML / DL models.

    Accepts JSON body with optional keys:
        task        : "event" | "stage" | "ahi"  (default: "event")
        demo        : bool – use synthetic data
        models      : list of model names to train
        skip_deep   : bool – skip DL models
        full_stages : bool – 5-class stage labels
        no_plots    : bool – skip plots
        tune        : bool – run hyperparameter tuning
        tune_model  : str  – which model to tune
        tune_method : "grid" | "bayesian"
        input_file  : str  – path to feature CSV
    """
    try:
        body = request.get_json(force=True) if request.data else {}

        cmd = [sys.executable, ML_ENHANCED_SCRIPT,
               "--output", ML_ENHANCED_OUTPUT_DIR,
               "--task", body.get("task", "event")]

        if body.get("demo", True):
            cmd.append("--demo")
        if body.get("skip_deep", False):
            cmd.append("--skip-deep")
        if body.get("full_stages", False):
            cmd.append("--full-stages")
        if body.get("no_plots", False):
            cmd.append("--no-plots")
        if body.get("tune", False):
            cmd.append("--tune")
            if body.get("tune_model"):
                cmd.extend(["--tune-model", body["tune_model"]])
            if body.get("tune_method"):
                cmd.extend(["--tune-method", body["tune_method"]])
        if body.get("models"):
            cmd.extend(["--models"] + body["models"])
        if body.get("input_file"):
            cmd.extend(["--input", body["input_file"]])

        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""

        # Parse structured result block
        ml_result = {}
        if "ML_ENHANCED_RESULT_BEGIN" in stdout:
            block = stdout.split("ML_ENHANCED_RESULT_BEGIN")[1]
            block = block.split("ML_ENHANCED_RESULT_END")[0].strip()
            try:
                ml_result = json.loads(block)
            except Exception:
                pass

        return jsonify({
            "success": proc.returncode == 0,
            "result": ml_result,
            "output_dir": ML_ENHANCED_OUTPUT_DIR,
            "raw_output": stdout,
            "stderr": stderr if proc.returncode != 0 else "",
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "trace": traceback.format_exc(),
        })


@app.route("/validate", methods=["POST"])
def run_validate():
    """
    Run the validation & benchmarking pipeline.

    Accepts JSON body with optional keys:
        system_events  : path to system event detections JSON
        psg_events     : path to PSG reference events CSV
        system_stages  : path to system stage predictions JSON
        psg_stages     : path to PSG reference stages CSV
        psg_ahi        : path to PSG AHI scores CSV
        demo           : bool – use synthetic demo data
        no_plots       : bool – skip plot generation
    """
    try:
        body = request.get_json(force=True) if request.data else {}

        cmd = [sys.executable, VALIDATION_SCRIPT,
               "--output", VALIDATION_OUTPUT_DIR]

        if body.get("demo", False):
            cmd.append("--demo")
        if body.get("no_plots", False):
            cmd.append("--no-plots")
        if body.get("system_events"):
            cmd.extend(["--system-events", body["system_events"]])
        if body.get("psg_events"):
            cmd.extend(["--psg-events", body["psg_events"]])
        if body.get("system_stages"):
            cmd.extend(["--system-stages", body["system_stages"]])
        if body.get("psg_stages"):
            cmd.extend(["--psg-stages", body["psg_stages"]])
        if body.get("psg_ahi"):
            cmd.extend(["--psg-ahi", body["psg_ahi"]])

        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""

        # Parse structured result block
        validation_result = {}
        if "VALIDATION_RESULT_BEGIN" in stdout:
            block = stdout.split("VALIDATION_RESULT_BEGIN")[1]
            block = block.split("VALIDATION_RESULT_END")[0].strip()
            try:
                validation_result = json.loads(block)
            except Exception:
                pass

        return jsonify({
            "success": True,
            "validation": validation_result,
            "output_dir": VALIDATION_OUTPUT_DIR,
            "raw_output": stdout,
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "trace": traceback.format_exc(),
        })


# ------------------------------------------------------------
# FIELD TESTING & DEPLOYMENT EVALUATION
# ------------------------------------------------------------
FIELD_TESTING_SCRIPT = os.path.join(BACKEND_DIR, "field_testing", "run_field_testing.py")
FIELD_TESTING_OUTPUT_DIR = os.path.join(BACKEND_DIR, "field_testing", "output")

@app.route("/field-testing/run", methods=["POST"])
def run_field_testing():
    """
    Run the field-testing & deployment evaluation pipeline.

    Accepts JSON body with optional keys:
        demo       : bool – use synthetic data (default True)
        subjects   : int  – number of synthetic subjects
        placements : int  – number of placement types
        epochs     : int  – epochs per recording
        no_plots   : bool – skip plot generation
        no_report  : bool – skip report generation
        configs    : str  – path to existing configs JSON
        input      : str  – path to pre-recorded data JSON
        seed       : int  – random seed
    """
    try:
        body = request.get_json(force=True) if request.data else {}

        cmd = [sys.executable, FIELD_TESTING_SCRIPT,
               "--output", FIELD_TESTING_OUTPUT_DIR]

        if body.get("demo", True):
            cmd.append("--demo")
        if body.get("subjects"):
            cmd.extend(["--subjects", str(body["subjects"])])
        if body.get("placements"):
            cmd.extend(["--placements", str(body["placements"])])
        if body.get("epochs"):
            cmd.extend(["--epochs", str(body["epochs"])])
        if body.get("no_plots", False):
            cmd.append("--no-plots")
        if body.get("no_report", False):
            cmd.append("--no-report")
        if body.get("configs"):
            cmd.extend(["--configs", body["configs"]])
        if body.get("input"):
            cmd.extend(["--input", body["input"]])
        if body.get("seed"):
            cmd.extend(["--seed", str(body["seed"])])

        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""

        # Parse structured result block
        ft_result = {}
        if "FIELD_TESTING_RESULT_BEGIN" in stdout:
            block = stdout.split("FIELD_TESTING_RESULT_BEGIN")[1]
            block = block.split("FIELD_TESTING_RESULT_END")[0].strip()
            try:
                ft_result = json.loads(block)
            except Exception:
                pass

        return jsonify({
            "success": proc.returncode == 0,
            "result": ft_result,
            "output_dir": FIELD_TESTING_OUTPUT_DIR,
            "raw_output": stdout,
            "stderr": stderr if proc.returncode != 0 else "",
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "trace": traceback.format_exc(),
        })


# ------------------------------------------------------------
# HEALTH CHECK
# ------------------------------------------------------------
@app.get("/")
def home():
    return jsonify({"status": "Radar pipeline API running (normal + behind-wall + sleep + motion-posture + staging + validation + ml-enhanced + field-testing + sleep-api)"})


# ------------------------------------------------------------
# START SERVER
# ------------------------------------------------------------
if __name__ == "__main__":
    print("Pipeline initialized (normal + behind-wall)")
    print("  VitalSigns:", VITALSIGNS_SCRIPT)
    print("  BW VitalSigns:", BW_VITALSIGNS_SCRIPT)
    print("  Cleaning:", CLEAN_SCRIPT)
    print("  BW Cleaning:", BW_CLEAN_SCRIPT)
    print("  Calibration:", CALIBRATION_SCRIPT)
    print("  Model:", MODEL_SCRIPT)
    print("  BW Model:", BW_MODEL_SCRIPT)

    app.run(port=5002, debug=True, use_reloader=False)
