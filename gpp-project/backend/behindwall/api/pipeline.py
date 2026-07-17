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
# PATHS  (Behind-Wall pipeline — runs on port 5005)
# ------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MASTER_FILE = os.path.join(BASE_DIR, "backend", "vital_signs_data_new.csv")
USERS_FILE  = os.path.join(BASE_DIR, "backend", "users.csv")

CLEAN_SCRIPT = os.path.join(BASE_DIR, "data_analysis", "behindwall", "cleaning_data.py")
MODEL_SCRIPT = os.path.join(BASE_DIR, "data_analysis", "behindwall", "predict_with_model.py")


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
# 1. UPLOAD CSV
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
# 2. RUN SENSOR -> SAVE DATA -> RUN PIPELINE
# ------------------------------------------------------------
@app.post("/run-sensor")
def run_sensor():
    try:
        data = request.get_json()
        user_email = data.get("userEmail")
        config_number = data.get("configuration")

        if not user_email or config_number is None:
            return jsonify({"success": False, "error": "Missing userEmail or configuration"})

        if not user_exists(user_email):
            return jsonify({"success": False, "error": "User does not exist. Please sign up first."})

        VITALSIGNS_SCRIPT = os.path.join(BASE_DIR, "backend", "behindwall", "vitalsigns.py")

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

        # EXTRACT STATS BLOCK (now includes waveform data)
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

        # -------------------------------------------------------
        # RUN CLEANING (includes calibration internally)
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
            "ml_results": ml_results,
            "waveform": waveform_data
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ------------------------------------------------------------
# 3. MANUAL PIPELINE RUN
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
    return jsonify({"status": "Behind-Wall radar pipeline API running"})


# ------------------------------------------------------------
# START SERVER  (port 5005 — distinct from main pipeline on 5002)
# ------------------------------------------------------------
if __name__ == "__main__":
    print("Using master file:", MASTER_FILE)
    print("Users file:", USERS_FILE)
    print("Starting Behind-Wall pipeline on port 5005...")
    app.run(port=5005, debug=True, use_reloader=False)
