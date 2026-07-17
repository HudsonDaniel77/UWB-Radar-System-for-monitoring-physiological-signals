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
import time

# Fix UTF-8 for printing
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

app = Flask(__name__)
CORS(app)

# ------------------------------------------------------------
# PATHS
# ------------------------------------------------------------
BASE_DIR = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project-behindwall"

MASTER_FILE = os.path.join(BASE_DIR, "backend", "vital_signs_new_data.csv")
USERS_FILE = os.path.join(BASE_DIR, "backend", "users.csv")

CLEAN_SCRIPT = os.path.join(BASE_DIR, "data_analysis", "cleaning_data.py")
MODEL_SCRIPT = os.path.join(BASE_DIR, "data_analysis", "predict_with_model.py")


# ------------------------------------------------------------
# USER CHECK
# ------------------------------------------------------------
def user_exists(email):
    if not os.path.exists(USERS_FILE):
        return False

    with open(USERS_FILE, "r") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if row and row[0].strip().lower() == email.lower():
                return True
    return False


# ------------------------------------------------------------
# 1️⃣ UPLOAD CSV
# ------------------------------------------------------------
@app.post("/upload")
def upload_csv():
    try:
        file = request.files.get("file")
        if file is None:
            return jsonify({"error": "No file uploaded"}), 400

        df = pd.read_csv(file)
        df.to_csv(MASTER_FILE, mode="a", header=False, index=False)

        return jsonify({"message": "File received and appended!"})

    except Exception as e:
        return jsonify({"error": str(e), "trace": traceback.format_exc()})


# ------------------------------------------------------------
# 2️⃣ RUN SENSOR → SAVE DATA → RUN PIPELINE
# ------------------------------------------------------------
@app.post("/run-sensor")
def run_sensor():
    # #region agent log
    log_data = {"location": "pipeline.py:70", "message": "run_sensor endpoint called", "data": {"method": request.method, "url": request.url, "remote_addr": request.remote_addr}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "run1", "hypothesisId": "B"}
    with open(r"c:\Project\RespirationHealth-main - Copy\.cursor\debug.log", "a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(log_data) + "\n")
    # #endregion
    try:
        data = request.get_json()
        # #region agent log
        log_data2 = {"location": "pipeline.py:78", "message": "Request data parsed", "data": {"hasData": data is not None, "userEmail": data.get("userEmail") if data else None, "config": data.get("configuration") if data else None}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "run1", "hypothesisId": "B"}
        with open(r"c:\Project\RespirationHealth-main - Copy\.cursor\debug.log", "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(log_data2) + "\n")
        # #endregion
        user_email = data.get("userEmail")
        config_number = data.get("configuration")

        if not user_email or config_number is None:
            return jsonify({"success": False, "error": "Missing userEmail or configuration"})

        if not user_exists(user_email):
            return jsonify({"success": False, "error": "User does not exist. Please sign up first."})

        VITALSIGNS_SCRIPT = os.path.join(BASE_DIR, "backend", "vitalsigns.py")

        # RUN SENSOR SCRIPT
        process = subprocess.Popen(
            [sys.executable, VITALSIGNS_SCRIPT, user_email, str(config_number)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        stdout, stderr = process.communicate()

        if process.returncode != 0:
            return jsonify({"success": False, "error": stderr or stdout})

        # EXTRACT STATS BLOCK
        stats_text = "No stats returned."
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
            stats_text = json.loads(json_buffer).get("stats_text", "No stats found.")
        except:
            pass

        # -------------------------------------------------------
        # RUN CLEANING (includes calibration internally now)
        # -------------------------------------------------------
        subprocess.run([sys.executable, CLEAN_SCRIPT], check=True)

        # -------------------------------------------------------
        # RUN ML MODEL
        # -------------------------------------------------------
        raw_output = subprocess.check_output([sys.executable, MODEL_SCRIPT], text=True).strip()

        try:
            ml_results = json.loads(raw_output)
        except:
            ml_results = {"raw_output": raw_output}

        return jsonify({
            "success": True,
            "stats_text": stats_text,
            "ml_results": ml_results
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ------------------------------------------------------------
# 3️⃣ MANUAL PIPELINE RUN
# ------------------------------------------------------------
@app.post("/run_pipeline")
def run_pipeline():
    try:
        # Run cleaning (this now includes calibration logic)
        subprocess.run([sys.executable, CLEAN_SCRIPT], check=True)

        raw_output = subprocess.check_output([sys.executable, MODEL_SCRIPT], text=True).strip()

        try:
            ml_output = json.loads(raw_output)
        except:
            ml_output = {"raw_output": raw_output}

        return jsonify({
            "message": "Pipeline completed",
            "ml_results": ml_output
        })

    except subprocess.CalledProcessError as e:
        return jsonify({
            "error": "Pipeline error",
            "details": e.output,
            "trace": traceback.format_exc()
        })


# ------------------------------------------------------------
# HEALTH CHECK
# ------------------------------------------------------------
@app.get("/")
def home():
    # #region agent log
    log_data = {"location": "pipeline.py:176", "message": "Health check endpoint called", "data": {"method": request.method, "url": request.url, "remote_addr": request.remote_addr}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}
    with open(r"c:\Project\RespirationHealth-main - Copy\.cursor\debug.log", "a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(log_data) + "\n")
    # #endregion
    return jsonify({"status": "Radar pipeline API running"})


# ------------------------------------------------------------
# START SERVER
# ------------------------------------------------------------
if __name__ == "__main__":
    # #region agent log
    log_data = {"location": "pipeline.py:188", "message": "Backend server starting", "data": {"port": 5000, "master_file": MASTER_FILE, "users_file": USERS_FILE}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}
    with open(r"c:\Project\RespirationHealth-main - Copy\.cursor\debug.log", "a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(log_data) + "\n")
    # #endregion
    print("📌 Using master file:", MASTER_FILE)
    print("📌 Users file:", USERS_FILE)
    app.run(port=5000, debug=True, use_reloader=False)
