from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import sys
import io
import csv
import os
import pandas as pd
import threading
import time

# UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

app = Flask(__name__)
CORS(app)

# Path to users.csv and data files
CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.csv")
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vital_signs_data_new.csv")

# Global variables for real-time data
current_waveform_data = {
    'heart_waveform': [],
    'respiration_waveform': [],
    'heart_rate': [],
    'respiration_rate': [],
    'timestamps': []
}
data_lock = threading.Lock()


def user_exists(email):
    """Check if user email exists in users.csv"""
    if not os.path.exists(CSV_FILE):
        return False

    with open(CSV_FILE, "r") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for row in reader:
            if row and row[0].strip().lower() == email.lower():
                return True
    return False


@app.post("/run-sensor")
def run_sensor():
    try:
        # React request
        data = request.get_json()
        user_email = data.get("userEmail")
        config_number = data.get("configuration")

        if not user_email or config_number is None:
            return jsonify({
                "success": False,
                "error": "Missing userEmail or configuration in request."
            })

        print("\n--- Sensor Request Received ---")
        print("User Email:", user_email)
        print("Selected Config:", config_number)
        print("--------------------------------\n")

        # 🔥 VALIDATE USER FROM CSV
        if not user_exists(user_email):
            return jsonify({
                "success": False,
                "error": "User does not exist in users.csv. Please sign up first."
            })

        # Run your Python sensor script
        process = subprocess.Popen(
            [sys.executable, "vst.py", user_email, str(config_number)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        stdout, stderr = process.communicate()

        if process.returncode != 0:
            print("Error running vst.py:", stderr)
            return jsonify({"success": False, "error": stderr})

        return jsonify({"success": True, "output": stdout})

    except Exception as e:
        print("Backend Error:", str(e))
        return jsonify({"success": False, "error": str(e)})


@app.route("/get-waveform-data", methods=["GET"])
def get_waveform_data():
    """Get current waveform data for real-time visualization"""
    try:
        with data_lock:
            # Return the latest 50 data points
            max_points = 50
            response_data = {
                'heart_waveform': current_waveform_data['heart_waveform'][-max_points:],
                'respiration_waveform': current_waveform_data['respiration_waveform'][-max_points:],
                'heart_rate': current_waveform_data['heart_rate'][-max_points:],
                'respiration_rate': current_waveform_data['respiration_rate'][-max_points:],
                'timestamps': current_waveform_data['timestamps'][-max_points:]
            }
        
        return jsonify({"success": True, "data": response_data})
    
    except Exception as e:
        print("Error getting waveform data:", str(e))
        return jsonify({"success": False, "error": str(e)})


@app.route("/get-latest-vitals", methods=["GET"])
def get_latest_vitals():
    """Get latest vital signs from CSV and update global store"""
    try:
        if not os.path.exists(DATA_FILE):
            return jsonify({"success": False, "error": "No data file found"})
        
        # Read last 20 rows from the CSV
        df = pd.read_csv(DATA_FILE)
        if df.empty:
            return jsonify({"success": False, "error": "No data available"})
        
        # Get most recent data
        recent_data = df.tail(20)
        
        # Extract waveform and vital sign data
        heart_waveforms = recent_data['HeartWaveform'].fillna(0).tolist() if 'HeartWaveform' in recent_data.columns else []
        respiration_waveforms = recent_data['BreathWaveform'].fillna(0).tolist() if 'BreathWaveform' in recent_data.columns else []
        heart_rates = recent_data['HeartRate_BPM'].fillna(0).tolist() if 'HeartRate_BPM' in recent_data.columns else []
        respiration_rates = recent_data['RespirationRate_BPM'].fillna(0).tolist() if 'RespirationRate_BPM' in recent_data.columns else []
        timestamps = recent_data['Timestamp'].fillna('').tolist() if 'Timestamp' in recent_data.columns else []
        
        # Update global data store
        with data_lock:
            current_waveform_data['heart_waveform'] = heart_waveforms
            current_waveform_data['respiration_waveform'] = respiration_waveforms
            current_waveform_data['heart_rate'] = heart_rates
            current_waveform_data['respiration_rate'] = respiration_rates
            current_waveform_data['timestamps'] = timestamps
        
        return jsonify({
            "success": True,
            "data": {
                'heart_waveform': heart_waveforms,
                'respiration_waveform': respiration_waveforms,
                'heart_rate': heart_rates,
                'respiration_rate': respiration_rates,
                'timestamps': timestamps
            }
        })
    
    except Exception as e:
        print("Error getting latest vitals:", str(e))
        return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
    print("🔗 Using CSV file:", CSV_FILE)
    print("🌐 Starting real-time waveform server...")
    
    # Run Flask server
    app.run(host="localhost", port=5004, debug=True)
