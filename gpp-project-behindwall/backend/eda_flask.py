# eda_flask.py
from flask import Flask, jsonify, send_file, request
from flask_cors import CORS
import pandas as pd
import numpy as np
from pathlib import Path
import logging
import subprocess
import json
import os

# -----------------------------
# CONFIG — CSV INPUT FILES (adjust paths if needed)
# -----------------------------
SAMPLE_CSV = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project-behindwall\data_analysis\cleaned_vital_signs.csv"
RUN_CSV = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project-behindwall\data_analysis\final_run_stats.csv"
COMPARISON_FILE_LOCAL_PATH = RUN_CSV  # serves same run CSV for download

MERGE_TOLERANCE = pd.Timedelta("2min")

# -----------------------------
# INIT FLASK
# -----------------------------
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# -----------------------------
# HELPERS
# -----------------------------
def _parse_timestamp_series(series):
    """Parse many timestamp styles into pandas datetime (dayfirst)."""
    if series is None:
        return series
    s = series.astype(str).str.strip()
    # try a few formats then fallback
    parsed = pd.to_datetime(s, errors="coerce", dayfirst=True)
    # if nearly all NaT try alternate formats
    if parsed.notna().sum() < max(1, int(len(s) * 0.5)):
        parsed2 = pd.to_datetime(s, format="%d-%m-%Y %H:%M", errors="coerce", dayfirst=True)
        parsed = parsed.fillna(parsed2)
        parsed3 = pd.to_datetime(s, format="%d-%m-%Y %H:%M:%S", errors="coerce", dayfirst=True)
        parsed = parsed.fillna(parsed3)
    return parsed

def _read_csv_safe(path):
    p = Path(path)
    if not p.exists():
        app.logger.warning("CSV missing: %s", path)
        return pd.DataFrame()
    try:
        df = pd.read_csv(p)
    except Exception as e:
        app.logger.error("Failed reading CSV %s: %s", path, e)
        return pd.DataFrame()
    return df

# -----------------------------
# SAMPLE-LEVEL (cleaned_vital_signs.csv)
# -----------------------------
def fetch_cleaned_dataframe():
    df = _read_csv_safe(SAMPLE_CSV)
    if df.empty:
        return df

    # rename to canonical names used by frontend
    rename_map = {
        "HeartRate_BPM": "Heart_clean",
        "RespirationRate_BPM": "Resp_clean",
        "Range_m": "Range_clean",
        "HeartRate": "Heart_clean",
        "RespirationRate": "Resp_clean",
    }
    df = df.rename(columns=rename_map)

    # numeric coercions (best-effort)
    numeric_cols = [
    "Heart_clean", "Resp_clean", "Range_clean",
    "HeartRate_FFT", "BreathRate_FFT", "BreathWaveform",
    "HeartWaveform", "SessionTime",
    "HeartRate_raw", "RespirationRate_raw", "Range_raw"
]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "Timestamp" in df.columns:
        df["Timestamp"] = _parse_timestamp_series(df["Timestamp"])

    app.logger.info("Loaded sample-level CSV rows=%d", len(df))
    return df

# -----------------------------
# RUN-LEVEL (final_run_stats.csv)
# -----------------------------
def fetch_finalstats_dataframe():
    df = _read_csv_safe(RUN_CSV)
    if df.empty:
        return df

    # rename to canonical run-level names
    rename_map = {
        "Average Heart Rate (sensor)": "Avg_HR_clean",
        "Average Respiration Rate (sensor)": "Avg_RR_clean",
        "Average Range (m)": "Avg_Range",
        "Range Standard Deviation (m)": "Range_SD",
        "Apple Watch Average": "Apple_HR",
        "Final_Accurate_HR": "Final_Accurate_HR",
    }
    df = df.rename(columns=rename_map)

    numeric_cols = [
        "Run", "Rows", "Avg_HR_clean", "Avg_RR_clean", "Avg_Range",
        "Range_SD", "HR_SD", "RR_SD", "HR_P2P", "RR_P2P", "SQI", "Final_Accurate_HR"
    ]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "Timestamp" in df.columns:
        df["Timestamp"] = _parse_timestamp_series(df["Timestamp"])

    # try sort by Run else Timestamp else index
    if "Run" in df.columns and df["Run"].notna().any():
        try:
            df = df.sort_values("Run").reset_index(drop=True)
        except Exception:
            pass
    elif "Timestamp" in df.columns:
        try:
            df = df.sort_values("Timestamp").reset_index(drop=True)
        except Exception:
            pass

    app.logger.info("Loaded run-level CSV runs=%d", len(df))
    return df

# -----------------------------
# Basic EDA helpers
# -----------------------------
def histogram(values, bins):
    vals = np.array([v for v in (values or []) if not pd.isna(v)])
    if vals.size == 0:
        return {"bins": [], "counts": []}
    counts, edges = np.histogram(vals, bins=bins)
    return {"bins": edges.tolist(), "counts": counts.tolist()}

def boxplot_stats(values):
    vals = np.array([v for v in (values or []) if not pd.isna(v)])
    if vals.size == 0:
        return {}
    q1 = float(np.percentile(vals, 25))
    q3 = float(np.percentile(vals, 75))
    median = float(np.percentile(vals, 50))
    iqr = q3 - q1
    lw = q1 - 1.5 * iqr
    uw = q3 + 1.5 * iqr
    non_out = vals[(vals >= lw) & (vals <= uw)]
    lower_whisker = float(non_out.min()) if non_out.size else float(vals.min())
    upper_whisker = float(non_out.max()) if non_out.size else float(vals.max())
    outliers = vals[(vals < lw) | (vals > uw)].tolist()
    return {
        "q1": q1, "q3": q3, "median": median, "iqr": iqr,
        "lower_whisker": lower_whisker, "upper_whisker": upper_whisker,
        "min": float(vals.min()), "max": float(vals.max()), "outliers": outliers
    }

def corr_matrix(df, cols):
    valid = [c for c in cols if c in df.columns]
    if not valid:
        return {"columns": [], "matrix": []}
    sub = df[valid].dropna()
    if sub.empty:
        # return column names so frontend shows emptiness but knows the labels
        return {"columns": valid, "matrix": []}
    return {"columns": valid, "matrix": sub.corr().values.tolist()}

def scatter_points(df, x, y):
    if x not in df.columns or y not in df.columns:
        return []
    sub = df[[x, y]].dropna()
    return [{"x": float(a), "y": float(b)} for a, b in zip(sub[x], sub[y])]

def anomaly_detection(df):
    results = []
    if df.empty:
        return results
    # use Avg_HR_clean if available
    hr_col = "Avg_HR_clean" if "Avg_HR_clean" in df.columns else None
    hr_mean = float(df[hr_col].mean()) if hr_col else None
    hr_std = float(df[hr_col].std()) if hr_col else None

    for _, r in df.iterrows():
        flags = []
        if hr_col and pd.notna(r.get(hr_col)) and hr_std and hr_std > 0:
            if abs(r[hr_col] - hr_mean) > 2 * hr_std:
                flags.append("HR Population Outlier")
        if "Range_SD" in r and pd.notna(r.get("Range_SD")) and r["Range_SD"] > 0.05:
            flags.append("High Movement")
        results.append({
            "Run": int(r["Run"]) if pd.notna(r.get("Run")) else None,
            "Timestamp": str(r.get("Timestamp")) if "Timestamp" in r else None,
            "flags": flags
        })
    return results

# -----------------------------
# ROUTES (CSV-backed)
# -----------------------------
@app.route("/health")
def health():
    return jsonify({"ok": True})

@app.route("/eda/overview")
def eda_overview():
    final = fetch_finalstats_dataframe()
    if final.empty:
        return jsonify({"error": "No final stats"}), 404

    # --- BASIC METRICS ---
    runs = int(len(final))

    avg_hr = float(final["Avg_HR_clean"].mean()) if "Avg_HR_clean" in final else None
    avg_rr = float(final["Avg_RR_clean"].mean()) if "Avg_RR_clean" in final else None
    avg_range = float(final["Avg_Range"].mean()) if "Avg_Range" in final else None

    # --- SIGNAL QUALITY ---
    sqi_mean = float(final["SQI"].mean()) if "SQI" in final else None
    sqi_std = float(final["SQI"].std()) if "SQI" in final else None
    good_sqi = int(final[final["SQI"] > 200].shape[0]) if "SQI" in final else 0

    # --- FINAL HR (CALIBRATED) ---
    if "Final_Accurate_HR" in final:
        final_hr_mean = float(final["Final_Accurate_HR"].mean())
        final_hr_std = float(final["Final_Accurate_HR"].std())
        final_hr_min = float(final["Final_Accurate_HR"].min())
        final_hr_max = float(final["Final_Accurate_HR"].max())
    else:
        final_hr_mean = final_hr_std = final_hr_min = final_hr_max = None

    return jsonify({
        "runs": runs,

        "avg_hr": avg_hr,
        "avg_rr": avg_rr,
        "avg_range": avg_range,

        "sqi_mean": sqi_mean,
        "sqi_std": sqi_std,
        "good_sqi": good_sqi,

        "final_hr_mean": final_hr_mean,
        "final_hr_std": final_hr_std,
        "final_hr_min": final_hr_min,
        "final_hr_max": final_hr_max,
    })


@app.route("/eda/runs")
def eda_runs():
    final = fetch_finalstats_dataframe()

    # Convert timestamp columns safely
    for col in final.columns:
        if ("time" in col.lower()) or ("date" in col.lower()) or ("timestamp" in col.lower()):
            final[col] = final[col].astype(str)

    # Also replace NaN with None so JSON can handle it
    final = final.replace({pd.NA: None, np.nan: None})

    return jsonify(final.to_dict(orient="records"))


@app.route("/eda/histogram")
def eda_histogram():
    feature = request.args.get("feature", "Heart_clean")
    bins = int(request.args.get("bins", 20))
    cleaned = fetch_cleaned_dataframe()
    final = fetch_finalstats_dataframe()
    # prefer sample-level (cleaned) if exists
    if feature in cleaned.columns:
        return jsonify(histogram(cleaned[feature].tolist(), bins))
    if feature in final.columns:
        return jsonify(histogram(final[feature].tolist(), bins))
    return jsonify({"error": "Feature not found"}), 400

@app.route("/eda/boxplot")
def eda_boxplot():
    feature = request.args.get("feature", "Heart_clean")
    cleaned = fetch_cleaned_dataframe()
    final = fetch_finalstats_dataframe()
    if feature in cleaned.columns:
        return jsonify(boxplot_stats(cleaned[feature].tolist()))
    if feature in final.columns:
        return jsonify(boxplot_stats(final[feature].tolist()))
    return jsonify({}), 400

@app.route("/eda/correlation_merged")
def eda_correlation_merged():
    cleaned = fetch_cleaned_dataframe()
    final = fetch_finalstats_dataframe()

    # Build merged table: merge sample -> nearest run on timestamp if available,
    # else fallback to join on Run if present.
    merged = pd.DataFrame()
    if not cleaned.empty and not final.empty and "Timestamp" in cleaned.columns and "Timestamp" in final.columns:
        try:
            merged = pd.merge_asof(
                cleaned.sort_values("Timestamp").reset_index(drop=True),
                final.sort_values("Timestamp").reset_index(drop=True),
                on="Timestamp",
                direction="nearest",
                tolerance=MERGE_TOLERANCE,
                suffixes=("_sample", "_run")
            )
        except Exception as e:
            app.logger.warning("merge_asof failed: %s", e)
            merged = pd.merge(cleaned, final, left_index=True, right_index=True, how="left")
    elif not final.empty:
        merged = final.copy()
    elif not cleaned.empty:
        merged = cleaned.copy()
    else:
        return jsonify({"columns": [], "matrix": []})

    cols = [
        "Heart_clean", "Resp_clean", "Range_clean",
        "Avg_HR_clean", "Avg_RR_clean", "Avg_Range", "Range_SD", "HR_SD", "RR_SD", "HR_P2P", "RR_P2P"
    ]
    return jsonify(corr_matrix(merged, cols))

@app.route("/eda/scatter")
def eda_scatter():
    x = request.args.get("x", "Range_clean")
    y = request.args.get("y", "Heart_clean")
    cleaned = fetch_cleaned_dataframe()
    final = fetch_finalstats_dataframe()
    # prefer sample-level if both columns exist there
    if x in cleaned.columns and y in cleaned.columns:
        return jsonify(scatter_points(cleaned, x, y))
    if x in final.columns and y in final.columns:
        return jsonify(scatter_points(final, x, y))
    # try merged
    if "Timestamp" in cleaned.columns and "Timestamp" in final.columns:
        try:
            merged = pd.merge_asof(
                cleaned.sort_values("Timestamp"),
                final.sort_values("Timestamp"),
                on="Timestamp",
                direction="nearest",
                tolerance=MERGE_TOLERANCE
            )
            if x in merged.columns and y in merged.columns:
                return jsonify(scatter_points(merged, x, y))
        except Exception:
            pass
    return jsonify([])

@app.route("/eda/anomalies")
def eda_anomalies():
    final = fetch_finalstats_dataframe()
    if final.empty:
        return jsonify({"ok": 0, "not_ok": 0})

    anomalies = anomaly_detection(final)

    ok_count = 0
    not_ok_count = 0

    for a in anomalies:
        if len(a["flags"]) == 0:
            ok_count += 1
        else:
            not_ok_count += 1

    return jsonify({
        "ok": ok_count,
        "not_ok": not_ok_count
    })


@app.route("/download/comparison")
def download_comparison():
    p = Path(COMPARISON_FILE_LOCAL_PATH)
    if not p.exists():
        return jsonify({"error": "file missing"}), 404
    return send_file(p, as_attachment=True, download_name=p.name)

@app.route("/debug/columns")
def debug_columns():
    c = fetch_cleaned_dataframe()
    f = fetch_finalstats_dataframe()
    return jsonify({
        "cleaned_columns": c.columns.tolist() if not c.empty else [],
        "final_columns": f.columns.tolist() if not f.empty else [],
        "cleaned_rows": len(c),
        "final_rows": len(f)
    })

@app.route("/eda/hypothesis_tests")
def hypothesis_tests():
    try:
        BASE_DIR = r"C:\Project\RespirationHealth-main - Copy\gpp-project"
        result = subprocess.check_output(
            ["python", os.path.join(BASE_DIR, "data_analysis", "hypotheses_tests.py")],
            text=True
        )
        return jsonify(json.loads(result))
    except Exception as e:
        return jsonify({"error": str(e)})
    
@app.route("/eda/hypothesis/calibration_data")
def calibration_data():
    df = fetch_finalstats_dataframe()
    if df.empty:
        return jsonify({
            "clean": [],
            "final": [],
            "error": "df empty"
        })

    # Ensure required columns exist
    if "Avg_HR_clean" not in df.columns or "Final_Accurate_HR" not in df.columns:
        return jsonify({
            "clean": [],
            "final": [],
            "error": "Required columns missing",
            "available_columns": df.columns.tolist()
        })

    clean = df["Avg_HR_clean"].replace({np.nan: None}).tolist()
    final = df["Final_Accurate_HR"].replace({np.nan: None}).tolist()

    return jsonify({
        "clean": clean,
        "final": final
    })

@app.route("/eda/hypothesis/hr_sqi_groups")
def hr_sqi_groups():
    df = fetch_finalstats_dataframe()
    if df.empty:
        return jsonify({
            "high": [],
            "low": [],
            "error": "df empty"
        })

    if "SQI" not in df.columns or "Avg_HR_clean" not in df.columns:
        return jsonify({
            "high": [],
            "low": [],
            "error": "Required columns missing",
            "available_columns": df.columns.tolist()
        })

    high = df[df["SQI"] >= 200]["Avg_HR_clean"].replace({np.nan: None}).tolist()
    low  = df[df["SQI"] < 200]["Avg_HR_clean"].replace({np.nan: None}).tolist()

    return jsonify({
        "high": high,
        "low": low
    })


@app.route("/eda/hypothesis/hr_stress_matrix")
def hr_stress_matrix():
    df = fetch_finalstats_dataframe()
    if df.empty:
        return jsonify({"labels": [], "matrix": []})

    # Create classes if not available
    if "HR_Class" not in df.columns:
        df["HR_Class"] = df["Avg_HR_clean"].apply(
            lambda x: "Low" if x < 70 else ("Normal" if x <= 90 else "High")
        )
    if "Stress_Class" not in df.columns:
        df["Stress_Class"] = df["Range_SD"].apply(
            lambda x: "Low" if x < 0.02 else ("Medium" if x < 0.05 else "High")
        )

    pivot = pd.crosstab(df["HR_Class"], df["Stress_Class"])

    return jsonify({
        "labels": pivot.columns.tolist(),
        "index": pivot.index.tolist(),
        "matrix": pivot.values.tolist()
    })

# -----------------------------
# START
# -----------------------------
if __name__ == "__main__":
    print("CSV-Only Flask EDA running on port 5001...")
    app.run(host="0.0.0.0", port=5001, debug=True)