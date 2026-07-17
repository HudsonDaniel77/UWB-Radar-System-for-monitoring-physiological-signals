import csv
import firebase_admin
from firebase_admin import credentials, firestore

# ----------------------------
# 1. Initialize Firebase Admin
# ----------------------------
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# ----------------------------
# 2. CSV FILE PATH
# ----------------------------
CSV_FILE = "vital_signs_new_data.csv"   # <-- change if needed

# ----------------------------
# 3. Upload Function
# ----------------------------
def upload_csv_to_firestore():
    print("\nUploading CSV data to Firestore...\n")

    # Use utf-8-sig to remove BOM automatically
    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        # Clean header names (remove BOM just in case)
        reader.fieldnames = [name.replace("ï»¿", "") for name in reader.fieldnames]

        count = 0
        for row in reader:
            try:
                # Remove BOM from keys again (for safety)
                clean_row = {k.replace("ï»¿", ""): v for k, v in row.items()}

                # Convert string fields into correct numeric types
                doc = {
                    "Timestamp": clean_row["Timestamp"],
                    "User": clean_row["User"],
                    "SessionTime": float(clean_row["SessionTime"]),
                    "HeartRate_BPM": float(clean_row["HeartRate_BPM"]),
                    "RespirationRate_BPM": float(clean_row["RespirationRate_BPM"]),
                    "Range_m": float(clean_row["Range_m"]),
                    "HeartWaveform": float(clean_row["HeartWaveform"]),
                    "BreathWaveform": float(clean_row["BreathWaveform"]),
                    "HeartRate_FFT": float(clean_row["HeartRate_FFT"]),
                    "BreathRate_FFT": float(clean_row["BreathRate_FFT"]),
                    "ConfigurationFile": int(clean_row["ConfigurationFile"]),
                }

                # Upload to Firestore
                db.collection("VitalSignsData").add(doc)
                count += 1

                if count % 50 == 0:
                    print(f"Uploaded {count} records...")

            except Exception as e:
                print("ERROR uploading row:", row)
                print("Reason:", e)

        print(f"\n✔ Upload completed. Total rows uploaded: {count}")

# ----------------------------
# Run the upload
# ----------------------------
if __name__ == "__main__":
    upload_csv_to_firestore()
