from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import sys
import io
import csv
import os

# UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

app = Flask(__name__)
CORS(app)

# Path to users.csv
CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.csv")


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


if __name__ == "__main__":
    print("🔗 Using CSV file:", CSV_FILE)
    app.run(host="localhost", port=5004, debug=True)
