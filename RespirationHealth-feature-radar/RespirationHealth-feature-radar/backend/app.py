import os
import time
import threading
import numpy as np
import csv
import datetime
import subprocess
import json
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# Import our custom modules
from radar_client import RadarClient
from dsp import *

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- CONFIGURATION ---
CONFIG_PORT = "COM11" 
DATA_PORT = "COM10"
BAUD_RATE = 921600
RADAR_CFG = "xwr68xx_profile.cfg"
CSV_LOG_FILE = "vital_signs_history.csv"
MODEL_SCRIPT = "../data_analysis/predict_with_model.py"

# Global state
radar = RadarClient(CONFIG_PORT, DATA_PORT, BAUD_RATE)
is_running = False
current_user = "vital_user_01"
last_processed_data = {"num_people": 0, "people": [], "range_profile": []}

# --- CSV LOGGING SETUP ---
if not os.path.exists(CSV_LOG_FILE):
    with open(CSV_LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Timestamp", "User", "HeartRate_BPM", "RespirationRate_BPM", 
            "Range_m", "HeartWaveform", "BreathWaveform", "HR_FFT", "RR_FFT"
        ])

def log_to_csv(user, hr, rr, r, hw, rw, hf, rf):
    try:
        with open(CSV_LOG_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([ts, user, hr, rr, r, hw, rw, hf, rf])
    except:
        pass

def call_ml_inference():
    """Calls the external ML script for advanced classification."""
    try:
        if os.path.exists(MODEL_SCRIPT):
            print(f">>> ML inference starting: {MODEL_SCRIPT}")
            result = subprocess.check_output(["python", MODEL_SCRIPT], text=True, stderr=subprocess.STDOUT)
            print(f">>> ML Inference result: {result.strip()}")
            return result.strip()
    except Exception as e:
        print(f">>> ML Prediction Error: {e}")
    return None

# --- MAIN LOGIC THREAD ---
def radar_thread_loop():
    global is_running, last_processed_data
    
    # Pre-open ports
    if not radar.connect():
        print("CRITICAL: Port sync failed (Hardware already in use?).")
        return

    print("Radar medical logic thread active. Monitoring Port 6666...")
    
    frame_count = 0
    while True:
        try:
            if not is_running:
                time.sleep(0.1)
                continue
                
            frame = radar.read_frame()
            if not frame: 
                time.sleep(0.01)
                continue
            
            frame_count += 1
            
            hr = frame.get("heart_rate") or frame.get("heart_fft", 0)
            rr = frame.get("resp_rate") or frame.get("resp_fft", 0)
            rng = frame.get("range") or 0.65
            
            # Log to CSV (~1Hz)
            if frame_count % 20 == 0:
                log_to_csv(current_user, hr, rr, rng, frame.get("heart_wf", 0), frame.get("resp_wf", 0), frame.get("heart_fft", 0), frame.get("resp_fft", 0))

            # Update SocketIO with real-time payload
            person_data = {
                "id": 1,
                "distance": round(rng, 2),
                "respiration_rate": round(rr, 1),
                "heart_rate": round(hr, 1),
                "respiration_wave": [frame.get("resp_wf", 0)] * 10,
                "heart_wave": [frame.get("heart_wf", 0)] * 10,
                "freq_spectrum": { 
                    "freqs": list(range(100)), 
                    "magnitude": [frame.get("heart_fft", 0) if i == int(hr) else 0 for i in range(100)] 
                },
                "invalid": hr < 40 or rr < 8 
            }
            
            socketio.emit('radar_data', {
                "num_people": 1 if hr > 40 else 0,
                "people": [person_data],
                "range_profile": [0] * 256
            })
            
        except Exception as e:
            time.sleep(0.05)

# --- API ENDPOINTS ---
@app.route('/start', methods=['POST'])
def start_sensor():
    global is_running
    print(f"\n[COMMAND] Triggering START session for User: {current_user}")
    if radar.send_config(RADAR_CFG):
        is_running = True
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 500

@app.route('/stop', methods=['POST'])
def stop_sensor():
    global is_running
    print(f"\n[COMMAND] Triggering STOP and ML inference...")
    radar.send_command("sensorStop")
    is_running = False
    ml_res = call_ml_inference()
    return jsonify({"status": "success", "prediction": ml_res})

if __name__ == '__main__':
    # Start thread
    t = threading.Thread(target=radar_thread_loop, daemon=True)
    t.start()
    
    print("VitalGuard Medical Backend ready on http://127.0.0.1:6666")
    socketio.run(app, host='127.0.0.1', port=6666, debug=False)
