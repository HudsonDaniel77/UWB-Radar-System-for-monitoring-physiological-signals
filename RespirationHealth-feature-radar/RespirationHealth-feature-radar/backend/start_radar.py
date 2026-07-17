import time
import requests
import sys

# --- CONFIGURATION (Points to app.py) ---
BACKEND_URL = "http://127.0.0.1:6666"
SESSION_DURATION = 30 # seconds

def trigger_30s_session():
    print(f"\n[SESSION CONTROL] Requesting 30-second medical session from VitalGuard Backend...")
    try:
        # Start the sensor via the Backend API
        start_resp = requests.post(f"{BACKEND_URL}/start", timeout=5)
        if start_resp.status_code == 200:
            print(f"[SESSION CONTROL] Sensor ACTIVE. Starting 30s countdown...")
            print("[SESSION CONTROL] Live telemetry is now streaming to the Dashboard.")
            
            for i in range(SESSION_DURATION, 0, -1):
                sys.stdout.write(f"\r[SESSION CONTROL] Time Remaining: {i}s   ")
                sys.stdout.flush()
                time.sleep(1)
            
            print(f"\n[SESSION CONTROL] Countdown complete. Finalizing session...")
            # Stop the sensor via the Backend API
            stop_resp = requests.post(f"{BACKEND_URL}/stop", timeout=5)
            if stop_resp.status_code == 200:
                print("[SESSION CONTROL] Session successful. Sensor is now IDLE.")
                # Show prediction result from the ML model
                res = stop_resp.json()
                if res.get("prediction"):
                    print(f"[SESSION CONTROL] ML Classification Result: {res['prediction']}")
            else:
                print("[SESSION CONTROL] Failed to stop sensor.")
        else:
            print(f"[SESSION CONTROL] ERROR: Backend rejected start. Status: {start_resp.status_code}")
    except requests.exceptions.ConnectionError:
        print("[SESSION CONTROL] CRITICAL ERROR: Backend (app.py) is NOT running on Port 6666.")
        print("[SESSION CONTROL] Please keep 'python app.py' running in a separate terminal.")
    except Exception as e:
        print(f"[SESSION CONTROL] An unexpected error occurred: {e}")

if __name__ == "__main__":
    trigger_30s_session()
