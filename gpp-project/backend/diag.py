import csv, os

CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.csv")
print(f"CSV path: {CSV_FILE}")
print(f"Exists: {os.path.exists(CSV_FILE)}")

with open(CSV_FILE, "r", encoding="utf-8") as f:
    raw = f.read()
    print(f"Raw bytes: {raw.encode('utf-8')[:200]}")
    print(f"Raw content:\n---\n{raw}\n---")

with open(CSV_FILE, "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader)
    print(f"Header: {header}")
    for i, row in enumerate(reader):
        if row:
            print(f"Row {i}: email='{row[0]}' stripped='{row[0].strip()}'")
