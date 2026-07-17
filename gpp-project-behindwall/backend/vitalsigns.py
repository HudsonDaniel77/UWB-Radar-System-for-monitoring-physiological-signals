# vitalsigns.py
"""
Usage:
    python vitalsigns.py <user_email> <config_type>

- user_email: string (will be saved into CSV)
- config_type: 0 for front, 1 for back

This script:
- loads the appropriate radar config file (front/back)
- connects to USER and DATA serial ports
- sends commands from CFG file and starts recording for DURATION seconds
- parses TLV type 6 payload used by your existing code to extract HR/RR and range
- saves rows into a master CSV with columns:
    Timestamp, User, Configuration, SessionTime, HeartRate_BPM, RespirationRate_BPM,
    Range_m, HeartWaveform, BreathWaveform, HeartRate_FFT, BreathRate_FFT
- prints a full ASCII-only stats summary at the end
- optionally calls an external ML script (predict_with_model.py) and prints its output
"""

import serial
import time
import struct
import csv
import datetime
import matplotlib
import pandas as pd
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import statistics
import os
import sys
import subprocess
import json
import traceback

# -----------------------------
# Read args: user_email and config
# Usage: python vitalsigns.py user@example.com 0
# -----------------------------
USER_EMAIL = sys.argv[1] if len(sys.argv) > 1 else "unknown_user"
try:
    CONFIG_TYPE = int(sys.argv[2]) if len(sys.argv) > 2 else 0  # 0=front, 1=back
except:
    CONFIG_TYPE = 0

CONFIG_STR = "front" if CONFIG_TYPE == 0 else "back"

# -----------------------------
# Select CFG file automatically
# Update these paths if yours are in a different location
# -----------------------------
FRONT_CFG = r"C:\ti\mmwave_industrial_toolbox_4_12_1\labs\Vital_Signs\68xx_vital_signs\gui\profiles\xwr68xx_profile_VitalSigns_20fps_Front.cfg"
BACK_CFG  = r"C:\ti\mmwave_industrial_toolbox_4_12_1\labs\Vital_Signs\68xx_vital_signs\gui\profiles\xwr68xx_profile_VitalSigns_20fps_Front.cfg"
CFG_FILE = FRONT_CFG if CONFIG_TYPE == 0 else BACK_CFG

# -----------------------------
# Serial / user config
# -----------------------------
USER_PORT = 'COM11'
DATA_PORT = 'COM10'
USER_BAUD = 115200
DATA_BAUD = 921600

DURATION = 30  # seconds - adjust as needed
CSV_DIR = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project-behindwall\backend"

MASTER_CSV = os.path.join(CSV_DIR, "vital_signs_data_new.csv")

# Model script (will be called at the end). Adjust path if needed.
MODEL_SCRIPT = os.path.normpath(os.path.join(os.path.dirname(CSV_DIR), "data_analysis", "predict_with_model.py"))

# Thresholds
HR_CHANGE_THRESHOLD = 2.0  # BPM
RR_CHANGE_THRESHOLD = 1.0  # BPM
RANGE_CHANGE_THRESHOLD = 0.05  # meters (5 cm)

# -----------------------------
# CSV setup
# -----------------------------
os.makedirs(CSV_DIR, exist_ok=True)
file_exists = os.path.exists(MASTER_CSV)

csv_file = open(MASTER_CSV, "a", newline="")
csv_writer = csv.writer(csv_file)

if not file_exists:
    csv_writer.writerow([
        "Timestamp", "User", "Configuration", "SessionTime",
        "HeartRate_BPM", "RespirationRate_BPM", "Range_m",
        "HeartWaveform", "BreathWaveform", "HeartRate_FFT", "BreathRate_FFT"
    ])
    csv_file.flush()

# -----------------------------
# Print header (ASCII safe)
# -----------------------------
print("=" * 60)
print("RADAR VITAL SIGNS COLLECTION")
print("User: {} | Configuration: {} ({})".format(USER_EMAIL, CONFIG_STR, CONFIG_TYPE))
print("CFG file: {}".format(CFG_FILE))
print("Model script (post-run): {}".format(MODEL_SCRIPT))
print("=" * 60)

# -----------------------------
# Connect to serial ports
# -----------------------------
print("\nConnecting to radar...")
try:
    user_ser = serial.Serial(USER_PORT, USER_BAUD, timeout=2)
    data_ser = serial.Serial(DATA_PORT, DATA_BAUD, timeout=2)
except Exception as e:
    print("ERROR: Could not open serial ports.")
    print("Details:", e)
    csv_file.close()
    sys.exit(1)

time.sleep(1)
user_ser.reset_input_buffer()
data_ser.reset_input_buffer()

# Stop previous and send config
print("Stopping previous session...")
try:
    user_ser.write(b'sensorStop\n')
    time.sleep(1)
    # try to read any initial response
    _ = user_ser.read(user_ser.in_waiting or 1)
except Exception as e:
    print("Warning: sensorStop may have failed:", e)

print("Sending configuration file...")
try:
    with open(CFG_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('%'):
                user_ser.write((line + '\n').encode())
                # small delay to allow radar to respond
                time.sleep(0.05)
                # if it's sensorStart, allow more time
                if 'sensorStart' in line:
                    time.sleep(2)
except Exception as e:
    print("ERROR: Could not read or send CFG file:", e)
    try:
        user_ser.write(b'sensorStop\n')
    except:
        pass
    csv_file.close()
    user_ser.close()
    data_ser.close()
    sys.exit(1)

print("Configuration sent. Starting collection...\n")

# -----------------------------
# Plot setup (non-blocking)
# -----------------------------
plt.ion()
fig, axes = plt.subplots(3, 1, figsize=(10, 8))
ax1, ax2, ax3 = axes

times, hr_values, rr_values, range_values = [], [], [], []
hr_line, = ax1.plot([], [], '-', linewidth=2)
rr_line, = ax2.plot([], [], '-', linewidth=2)
range_line, = ax3.plot([], [], '-', linewidth=2)
ax1.set_ylabel("Heart Rate (BPM)"); ax1.set_ylim(40, 120); ax1.grid(True, alpha=0.3)
ax2.set_ylabel("Respiration Rate (BPM)"); ax2.set_ylim(5, 30); ax2.grid(True, alpha=0.3)
ax3.set_xlabel("Time (s)"); ax3.set_ylabel("Range (m)"); ax3.set_ylim(0.3, 1.5); ax3.grid(True, alpha=0.3)
plt.tight_layout(); plt.pause(0.001)

def show_ti_combined_graph(csv_path, user_email, config_type):
    import pandas as pd
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Button

    try:
        print("\n[TI GUI] Loading CSV...")
        df = pd.read_csv(csv_path)

        # Filter only recent session rows for this user/config
        df = df[df["User"] == user_email]
        df = df[df["Configuration"] == config_type]

        if df.empty:
            print("[TI GUI] No matching rows for this session.")
            return

        # Extract columns
        heart_wf = df["HeartWaveform"].astype(float).values
        breath_wf = df["BreathWaveform"].astype(float).values
        hr_fft = df["HeartRate_FFT"].astype(float).values
        rr_fft = df["BreathRate_FFT"].astype(float).values

        # Normalization logic (same as your repl script)
        def normalize(arr):
            amin, amax = min(arr), max(arr)
            if abs(amax - amin) < 1e-6:
                return [0.0] * len(arr)
            return [((v - amin) / (amax - amin)) * 2.0 - 1.0 for v in arr]

        nh = normalize(heart_wf)
        nb = normalize(breath_wf)
        nhf = normalize(hr_fft)
        nrf = normalize(rr_fft)

        # Combined weighted waveform
        combined = []
        for i in range(len(nh)):
            h = nh[i]
            b = nb[i] if i < len(nb) else 0
            hf = nhf[i] if i < len(nhf) else 0
            rf = nrf[i] if i < len(nrf) else 0
            combined.append(0.45*h + 0.35*b + 0.10*hf + 0.10*rf)

        combined = normalize(combined)

        # ========================
        # PLOT EXACT TI-STYLE GUI
        # ========================
        plt.style.use('dark_background')
        fig, axs = plt.subplots(4, 1, figsize=(12, 8), sharex=True)
        ax_h, ax_b, ax_hf, ax_comb = axs

        x = list(range(len(combined)))

        ax_h.plot(x, heart_wf, linewidth=1, label="HeartWaveform")
        ax_h.set_ylabel("HeartWF")
        ax_h.legend(loc="upper right")

        ax_b.plot(x, breath_wf, linewidth=1, label="BreathWaveform")
        ax_b.set_ylabel("BreathWF")
        ax_b.legend(loc="upper right")

        ax_hf.plot(x, hr_fft, linewidth=1, label="HR_FFT")
        ax_hf.set_ylabel("HR_FFT")
        ax_hf.legend(loc="upper right")

        ax_comb.plot(x, combined, linewidth=2, label="COMBINED")
        ax_comb.set_ylabel("Combined")
        ax_comb.legend(loc="upper right")

        for a in axs:
            a.grid(alpha=0.2)

        fig.suptitle(f"Combined Vital Signs Waveform — user: {user_email} config: {config_type}")

        # Save PNG button (same as your repl)
        axsave = plt.axes([0.85, 0.92, 0.12, 0.05])
        btn = Button(axsave, 'Save PNG')

        def on_save(event):
            out_png = os.path.splitext(csv_path)[0] + "_combined_output.png"
            fig.savefig(out_png, dpi=180)
            print("Saved:", out_png)

        btn.on_clicked(on_save)

        plt.tight_layout(rect=[0,0,1,0.96])
        plt.show()

    except Exception as e:
        print("[TI GUI ERROR]", e)


# -----------------------------
# Variables for processing & stats
# -----------------------------
start_time = time.time()
packet_count = 0
data_saved = 0
data_skipped = 0
bytes_read = 0
sync_attempts = 0

last_valid_hr = None
last_valid_rr = None

last_saved_hr = None
last_saved_rr = None
last_saved_range = None

range_history = []
range_method_scores = {}
debug_sample_count = 0
best_range_method = None

# helper: extract possible range floats from TLV payload
def extract_range_multi_method(tlv_data):
    candidates = []
    # scan offsets for floats in reasonable range
    for offset in range(64, min(128, len(tlv_data)), 4):
        try:
            if offset + 4 <= len(tlv_data):
                val = struct.unpack_from('<f', tlv_data, offset)[0]
                if 0.2 < val < 2.5:
                    candidates.append(('float_scan', offset, val))
        except:
            pass
    # range-index fallback
    try:
        range_idx = struct.unpack_from('<I', tlv_data, 4)[0]
        if 1 < range_idx < 100:
            for bin_size in [0.044, 0.04, 0.048, 0.05]:
                range_val = range_idx * bin_size
                if 0.2 < range_val < 2.5:
                    candidates.append(('range_idx', bin_size, range_val))
    except:
        pass
    # specific offsets (TI docs)
    specific_offsets = [64, 68, 72, 76, 80, 84, 88, 92, 96, 100, 104, 108]
    for offset in specific_offsets:
        try:
            if offset + 4 <= len(tlv_data):
                val = struct.unpack_from('<f', tlv_data, offset)[0]
                if 0.2 < val < 2.5:
                    candidates.append(('specific', offset, val))
        except:
            pass
    return candidates

# -----------------------------
# Main read loop
# -----------------------------
try:
    while time.time() - start_time < DURATION:
        byte = data_ser.read(1)
        bytes_read += 1
        if not byte:
            continue
        if byte[0] != 0x02:
            sync_attempts += 1
            continue

        rest = data_ser.read(7)
        bytes_read += len(rest)
        if len(rest) < 7:
            continue

        sync = byte + rest
        if sync != b'\x02\x01\x04\x03\x06\x05\x08\x07':
            continue

        # got sync
        if packet_count == 0:
            print("Found first valid packet sync word.")

        header = data_ser.read(32)
        bytes_read += len(header)
        if len(header) < 32:
            continue

        try:
            total_len = struct.unpack('<I', header[4:8])[0]
            frame_num = struct.unpack('<I', header[12:16])[0]
            if total_len < 40 or total_len > 65536:
                continue
            payload_len = total_len - 40
            payload = data_ser.read(payload_len)
            bytes_read += len(payload)
            if len(payload) < payload_len:
                continue

            packet_count += 1
            ts = time.time() - start_time

            offset = 0
            while offset + 8 <= len(payload):
                tlv_type, tlv_length = struct.unpack_from('<II', payload, offset)
                offset += 8
                if offset + tlv_length > len(payload):
                    break

                if tlv_type == 6 and tlv_length >= 128:
                    try:
                        tlv_data = payload[offset:offset+tlv_length]

                        # Extract vital signs (positions from your code)
                        # NOTE: if these byte offsets don't match your TLV format,
                        # adjust indexes used below accordingly.
                        breath_waveform = struct.unpack_from('<f', tlv_data, 28)[0]
                        heart_waveform  = struct.unpack_from('<f', tlv_data, 32)[0]
                        heart_rate_fft  = struct.unpack_from('<f', tlv_data, 36)[0]
                        breath_rate_fft = struct.unpack_from('<f', tlv_data, 52)[0]

                        # Range candidates
                        range_candidates = extract_range_multi_method(tlv_data)

                        # Debug prints (first 3)
                        if debug_sample_count < 3:
                            print("")
                            print("DEBUG PACKET #{}".format(debug_sample_count + 1))
                            print("Range candidates found:", len(range_candidates))
                            for method, param, value in range_candidates[:5]:
                                print("  {} (param={}): {:.3f} m".format(method, param, value))
                            debug_sample_count += 1

                        # Choose range
                        range_m = None
                        if best_range_method is None and len(range_history) > 20:
                            method_variances = {}
                            for key in range_method_scores:
                                if len(range_method_scores[key]) > 15:
                                    variance = statistics.variance(range_method_scores[key])
                                    method_variances[key] = variance
                            if method_variances:
                                best_range_method = min(method_variances, key=method_variances.get)
                                print("Selected range method:", best_range_method)

                        if best_range_method:
                            for method, param, value in range_candidates:
                                method_key = "{}_{}".format(method, param)
                                if method_key == best_range_method:
                                    range_m = value
                                    break

                        if range_m is None and range_candidates:
                            range_m = range_candidates[0][2]
                            method_key = "{}_{}".format(range_candidates[0][0], range_candidates[0][1])
                            if method_key not in range_method_scores:
                                range_method_scores[method_key] = []
                            range_method_scores[method_key].append(range_m)
                            if len(range_method_scores[method_key]) > 30:
                                range_method_scores[method_key].pop(0)

                        if range_m is None or range_m < 0.1 or range_m > 3.0:
                            range_m = 0.6

                        # smooth range
                        range_history.append(range_m)
                        if len(range_history) > 9:
                            range_history.pop(0)
                        smoothed_range = statistics.median(range_history) if len(range_history) >= 5 else range_m

                        # Validate HR/RR
                        heart_rate = heart_rate_fft
                        breath_rate = breath_rate_fft
                        hr_valid = 30 <= heart_rate <= 200
                        rr_valid = 5 <= breath_rate <= 50

                        if not hr_valid and last_valid_hr is not None:
                            heart_rate = last_valid_hr
                            hr_valid = True
                        if not rr_valid and last_valid_rr is not None:
                            breath_rate = last_valid_rr
                            rr_valid = True

                        if hr_valid and rr_valid:
                            last_valid_hr = heart_rate
                            last_valid_rr = breath_rate

                            # decide whether to save
                            should_save = False
                            if last_saved_hr is None:
                                should_save = True
                            else:
                                if abs(heart_rate - last_saved_hr) >= HR_CHANGE_THRESHOLD:
                                    should_save = True
                                if abs(breath_rate - last_saved_rr) >= RR_CHANGE_THRESHOLD:
                                    should_save = True
                                if abs(smoothed_range - last_saved_range) >= RANGE_CHANGE_THRESHOLD:
                                    should_save = True

                            if should_save:
                                now = datetime.datetime.now().replace(second=0, microsecond=0)
                                current_timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

                                # Write CSV row (with User + Configuration)
                                csv_writer.writerow([
                                    current_timestamp,
                                    USER_EMAIL,
                                    CONFIG_TYPE,
                                    "{:.2f}".format(ts),
                                    "{:.2f}".format(heart_rate),
                                    "{:.2f}".format(breath_rate),
                                    "{:.3f}".format(smoothed_range),
                                    "{:.4f}".format(heart_waveform),
                                    "{:.4f}".format(breath_waveform),
                                    "{:.2f}".format(heart_rate_fft),
                                    "{:.2f}".format(breath_rate_fft)
                                ])
                                csv_file.flush()
                                data_saved += 1

                                last_saved_hr = heart_rate
                                last_saved_rr = breath_rate
                                last_saved_range = smoothed_range

                                print("[{:.1f}s] SAVED HR: {:.1f} | RR: {:.1f} | Range: {:.3f} m".format(ts, heart_rate, breath_rate, smoothed_range))
                            else:
                                data_skipped += 1

                            # update plot arrays
                            times.append(ts); hr_values.append(heart_rate); rr_values.append(breath_rate); range_values.append(smoothed_range)
                            if len(times) > 100:
                                times = times[-100:]; hr_values = hr_values[-100:]; rr_values = rr_values[-100:]; range_values = range_values[-100:]
                            if (data_saved + data_skipped) % 10 == 0:
                                hr_line.set_data(times, hr_values)
                                rr_line.set_data(times, rr_values)
                                range_line.set_data(times, range_values)
                                if len(times) > 1:
                                    ax1.set_xlim(times[0], times[-1] + 1); ax2.set_xlim(times[0], times[-1] + 1); ax3.set_xlim(times[0], times[-1] + 1)
                                    if len(range_values) > 5:
                                        r_min = min(range_values[-20:]); r_max = max(range_values[-20:])
                                        ax3.set_ylim(max(0.2, r_min - 0.1), min(2.5, r_max + 0.1))
                                plt.draw(); plt.pause(0.001)

                    except Exception as e:
                        if packet_count < 10:
                            print("Error parsing TLV:", e)
                offset += tlv_length

        except Exception as e:
            if packet_count < 5:
                print("Error parsing packet:", e)

# end main loop
except KeyboardInterrupt:
    print("\nStopped by user")

finally:
    
    # -----------------------------
    # Session summary (ASCII safe)
    # -----------------------------
    duration = time.time() - start_time
    print("\n" + "-" * 60)
    print("USER:", USER_EMAIL)
    print("CONFIGURATION:", CONFIG_STR, "({})".format(CONFIG_TYPE))
    print("\nSESSION SUMMARY")
    print("-" * 40)
    print("Duration (sec)      : {:.1f}".format(duration))
    print("Packets Received    : {}".format(packet_count))
    print("Frames Saved        : {}".format(data_saved))
    print("Frames Skipped      : {}".format(data_skipped))
    total = data_saved + data_skipped
    if total > 0:
        save_ratio = data_saved / total * 100.0
        print("Save Ratio (%)      : {:.1f}%".format(save_ratio))
    else:
        print("Save Ratio (%)      : N/A")

    # compute averages and std dev
    if len(hr_values) > 0:
        avg_hr = sum(hr_values)/len(hr_values)
        avg_rr = sum(rr_values)/len(rr_values)
        avg_range = sum(range_values)/len(range_values)

        # Build full stats text EXACTLY like printed (ASCII)
        stats_text = "\nVITAL SIGNS SUMMARY\n" \
                    + ("-" * 40) + "\n" \
                    + "Average Heart Rate  : {:.1f} bpm\n".format(avg_hr) \
                    + "Average Resp Rate   : {:.1f} bpm\n".format(avg_rr) \
                    + "Average Distance    : {:.3f} m ({:.0f} cm)\n".format(avg_range, avg_range * 100.0)

        print("\nVITAL SIGNS SUMMARY")
        print("-" * 40)
        print("Average Heart Rate  : {:.1f} bpm".format(avg_hr))
        print("Average Resp Rate   : {:.1f} bpm".format(avg_rr))
        print("Average Distance    : {:.3f} m ({:.0f} cm)".format(avg_range, avg_range * 100.0))

        if len(range_values) > 1:
            range_std = statistics.stdev(range_values)
            stats_text += "Distance Std Dev    : {:.3f} m ({:.0f} cm)\n".format(range_std, range_std * 100.0)
            print("Distance Std Dev    : {:.3f} m ({:.0f} cm)".format(range_std, range_std * 100.0))
    else:
        stats_text = "No valid HR/RR frames were saved."
        print("\nNo valid HR/RR frames were saved.")

    # IMPORTANT: Send stats back to Flask
    print("STATS_BEGIN")
    print(json.dumps({"stats_text": stats_text}))
    print("STATS_END")

    print("\nCSV Saved To:")
    print("  {}".format(MASTER_CSV))
    print("-" * 60)
    

    # -----------------------------
    # Run ML model script (if exists) and show HR/RR/Stress classes
    # -----------------------------
    ml_summary = None
    try:
        if os.path.exists(MODEL_SCRIPT):
            print("\nRunning ML model for classification (may take a moment)...")
            try:
                result = subprocess.check_output([sys.executable, MODEL_SCRIPT], text=True, stderr=subprocess.STDOUT)
                raw = result.strip()
                try:
                    ml_summary = json.loads(raw)
                except:
                    try:
                        safe = raw.replace("'", '"')
                        ml_summary = json.loads(safe)
                    except:
                        ml_summary = {"raw_output": raw}
            except subprocess.CalledProcessError as e:
                print("Model script returned error:")
                print(e.output or str(e))
                ml_summary = None
        else:
            print("\nModel script not found at:", MODEL_SCRIPT)
    except Exception as e:
        print("\nError running model script:")
        print(traceback.format_exc())
        ml_summary = None

    if ml_summary:
        print("\nML ANALYSIS SUMMARY")
        print("-" * 40)
        # Try common keys
        try:
            get = ml_summary.get
            ph = get('Predicted_HR', get('predicted_hr', 'N/A'))
            hc = get('HR_Class', get('hr_class', 'N/A'))
            rc = get('RR_Class', get('rr_class', 'N/A'))
            sc = get('Stress_Class', get('stress_class', 'N/A'))
            print("Predicted_HR  :", ph)
            print("HR_Class      :", hc)
            print("RR_Class      :", rc)
            print("Stress_Class  :", sc)
        except Exception:
            print(ml_summary)
    else:
        print("\nNo ML summary available (model script not run or returned unparsable output).")

    # -----------------------------
    # Clean up serial / files / plots
    # -----------------------------
    try:
        csv_file.close()
    except:
        pass
    try:
        user_ser.write(b'sensorStop\n')
    except:
        pass
    time.sleep(0.5)
    try:
        user_ser.close()
        data_ser.close()
    except:
        pass

    plt.ioff()
    try:
        plt.show()
    except:
        pass

    show_ti_combined_graph(MASTER_CSV, USER_EMAIL, CONFIG_TYPE)    
    print("\nDone.")
