import os
import time
import threading
import numpy as np
import csv
import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- DEMO MODE (No Hardware Required) ---
DEMO_MODE = True
CSV_LOG_FILE = "vital_signs_history.csv"

# Global state
is_running = False
current_user = "vital_user_01"

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

# --- DEMO DATA GENERATOR ---
def generate_demo_data():
    """Generates realistic fake vital signs data for demo mode."""
    base_hr = 72 + np.random.randn() * 5  # ~72 BPM
    base_rr = 16 + np.random.randn() * 2  # ~16 BPM
    base_range = 0.8 + np.random.randn() * 0.1  # ~0.8m
    
    # Waveforms (sine waves with noise)
    t = np.linspace(0, 2*np.pi, 100)
    heart_wf = (np.sin(t) + np.random.randn(100) * 0.2).tolist()
    resp_wf = (0.5*np.sin(t*0.5) + np.random.randn(100) * 0.15).tolist()
    
    return {
        "heart_rate": max(60, min(100, base_hr)),
        "resp_rate": max(12, min(20, base_rr)),
        "range": max(0.3, min(1.5, base_range)),
        "heart_wf": heart_wf,
        "resp_wf": resp_wf,
        "heart_fft": base_hr * 0.8,
        "resp_fft": base_rr * 0.6
    }

# --- MAIN LOGIC THREAD ---
def radar_thread_loop():
    global is_running
    
    print("[DEMO] Radar simulator thread active. Monitoring for commands...")
    
    frame_count = 0
    while True:
        try:
            if not is_running:
                time.sleep(0.1)
                continue
                
            frame_count += 1
            
            # Generate demo data
            frame = generate_demo_data()
            
            # Log to CSV (~1Hz)
            if frame_count % 20 == 0:
                log_to_csv(current_user, frame["heart_rate"], frame["resp_rate"], 
                          frame["range"], frame["heart_wf"][0], frame["resp_wf"][0], 
                          frame["heart_fft"], frame["resp_fft"])

            # Emit real-time data
            person_data = {
                "id": 1,
                "distance": round(frame["range"], 2),
                "respiration_rate": round(frame["resp_rate"], 1),
                "heart_rate": round(frame["heart_rate"], 1),
                "respiration_wave": frame["resp_wf"],
                "heart_wave": frame["heart_wf"],
                "freq_spectrum": { 
                    "freqs": list(range(100)), 
                    "magnitude": [frame["heart_fft"] if i == int(frame["heart_rate"]) else 0 for i in range(100)] 
                },
                "invalid": False
            }
            
            socketio.emit('radar_data', {
                "num_people": 1,
                "people": [person_data],
                "range_profile": [0.5 + 0.2*np.sin(i/50) for i in range(256)]
            })
            
            time.sleep(0.05)  # 20 FPS
            
        except Exception as e:
            print(f"[DEMO] Error: {e}")
            time.sleep(0.05)

# --- API ENDPOINTS ---
@app.route('/start', methods=['POST'])
def start_sensor():
    global is_running
    print(f"\n[COMMAND] Triggering START session for User: {current_user}")
    is_running = True
    return jsonify({"status": "success"})

@app.route('/stop', methods=['POST'])
def stop_sensor():
    global is_running
    print(f"\n[COMMAND] Triggering STOP")
    is_running = False
    return jsonify({"status": "success", "prediction": "demo_mode_active"})

if __name__ == '__main__':
    import os
    
    # Start thread
    t = threading.Thread(target=radar_thread_loop, daemon=True)
    t.start()
    
    print("=" * 60)
    print("🚀 DEMO MODE - RespirationHealth Backend")
    print("=" * 60)
    print("Ready on http://127.0.0.1:6666")
    print("Generating synthetic vital signs data...")
    print("=" * 60)
    
    socketio.run(app, host='127.0.0.1', port=6666, debug=False)
