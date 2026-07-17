from flask import Flask, request, jsonify
from flask_cors import CORS
import csv
import os

app = Flask(__name__)
CORS(app)

CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.csv")

# Ensure CSV exists
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["email", "password"])


@app.route("/add-user", methods=["POST"])
def add_user():
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "message": "Invalid request format"}), 400

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"success": False, "message": "Missing email or password"}), 400

    # Check duplicates safely
    with open(CSV_FILE, "r") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) >= 1 and row[0].strip() == email.strip():
                return jsonify({"success": False, "message": "Email already exists."})

    # Append new user
    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([email, password])

    return jsonify({"success": True})


@app.route("/get-users", methods=["GET"])
def get_users():
    with open(CSV_FILE, "r") as f:
        return f.read()


if __name__ == "__main__":
    print("Saving CSV to:", CSV_FILE)
    app.run(port=5003, debug=True)
