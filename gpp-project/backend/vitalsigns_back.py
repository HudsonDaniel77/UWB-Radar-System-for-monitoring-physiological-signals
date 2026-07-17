import serial
import time
import struct
import csv
import datetime
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import statistics
import os

# -----------------------------
# User Configurations
# -----------------------------
USER_PORT = 'COM5'
DATA_PORT = 'COM6'
USER_BAUD = 115200
DATA_BAUD = 921600
CFG_FILE = r"C:\Users\Nikhil\Downloads\mmwave_industrial_toolbox_4_12_1\labs\Vital_Signs\68xx_vital_signs\gui\profiles\xwr68xx_profile_VitalSigns_20fps_Back.cfg"

DURATION = 30  # seconds
CSV_DIR = os.path.dirname(os.path.abspath(__file__))

# Single CSV file for all data
MASTER_CSV = os.path.join(CSV_DIR, "vital_signs_data_new.csv")

# Change detection thresholds
HR_CHANGE_THRESHOLD = 2.0  # BPM
RR_CHANGE_THRESHOLD = 1.0  # BPM
RANGE_CHANGE_THRESHOLD = 0.05  # meters (5 cm)

# -----------------------------
# Prepare CSV file (append mode)
# -----------------------------
file_exists = os.path.exists(MASTER_CSV)

csv_file = open(MASTER_CSV, "a", newline="")
csv_writer = csv.writer(csv_file)

# Write header only if file is new
if not file_exists:
    csv_writer.writerow([
        "Timestamp", "SessionTime", "HeartRate_BPM", "RespirationRate_BPM", "Range_m",
        "HeartWaveform", "BreathWaveform", "HeartRate_FFT", "BreathRate_FFT"
    ])
    print(f"[OK] Created new file: {MASTER_CSV}")
else:
    print(f"[OK] Appending to existing file: {MASTER_CSV}")

print("="*60)
print("TI mmWave Radar Vital Signs Data Logger")
print("="*60)
print("\nChange Detection Enabled:")
print(f"  - Heart Rate threshold: +/- {HR_CHANGE_THRESHOLD} bpm")
print(f"  - Respiration Rate threshold: +/- {RR_CHANGE_THRESHOLD} bpm")
print(f"  - Range threshold: +/- {RANGE_CHANGE_THRESHOLD*100:.0f} cm")

print("="*60)

# -----------------------------
# Connect and configure
# -----------------------------
print("\nConnecting to radar...")
try:
    user_ser = serial.Serial(USER_PORT, USER_BAUD, timeout=2)
    data_ser = serial.Serial(DATA_PORT, DATA_BAUD, timeout=2)
    print(f"✓ Connected to {USER_PORT} and {DATA_PORT}")
except Exception as e:
    print(f"✗ Connection failed: {e}")
    csv_file.close()
    exit(1)

time.sleep(1)

user_ser.reset_input_buffer()
data_ser.reset_input_buffer()

print("\nStopping previous session...")
user_ser.write(b'sensorStop\n')
time.sleep(1)
resp = user_ser.read(user_ser.in_waiting or 1)
if resp:
    print(f"  Response: {resp.decode('utf-8', errors='ignore').strip()}")

print("\nSending configuration...")
print("-" * 60)

command_count = 0
with open(CFG_FILE, "r") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('%'):
            command_count += 1
            print(f"[{command_count:2d}] Sending: {line}")
            user_ser.write((line + '\n').encode())
            
            # Wait and read response
            time.sleep(0.15)
            response = user_ser.read(user_ser.in_waiting or 1)
            if response:
                resp_text = response.decode('utf-8', errors='ignore').strip()
                print(f"     Response: {resp_text}")
                
                # Check for errors
                if 'error' in resp_text.lower() or 'invalid' in resp_text.lower():
                    print(f"     ⚠️  WARNING: Command may have failed!")
            else:
                print(f"     (no response)")
            
            # Special delays for critical commands
            if 'sensorStop' in line or 'flushCfg' in line:
                time.sleep(0.5)
            elif 'sensorStart' in line:
                print("     ⏳ Waiting for sensor to start...")
                time.sleep(3)
                # Check for startup messages
                startup_resp = user_ser.read(user_ser.in_waiting or 1)
                if startup_resp:
                    print(f"     Startup: {startup_resp.decode('utf-8', errors='ignore').strip()}")

print("-" * 60)
print(f"Configuration complete. {command_count} commands sent.\n")

# Check if data port has any activity
print("Checking data port for activity...")
time.sleep(1)
if data_ser.in_waiting > 0:
    print(f"✓ Data port has {data_ser.in_waiting} bytes waiting")
else:
    print("⚠️  WARNING: No data detected on data port yet")
    print("   Waiting 3 more seconds...")
    time.sleep(3)
    if data_ser.in_waiting > 0:
        print(f"✓ Now detecting {data_ser.in_waiting} bytes")
    else:
        print("✗ Still no data. Possible issues:")
        print("   1. Sensor may not have started properly")
        print("   2. Wrong DATA_PORT (check device manager)")
        print("   3. Configuration file may be incompatible")
        print("   4. Radar needs power cycle")

print("\nStarting data collection...\n")

# -----------------------------
# Prepare plotting
# -----------------------------
plt.ion()
fig, axes = plt.subplots(3, 1, figsize=(10, 8))
ax1, ax2, ax3 = axes

times, hr_values, rr_values, range_values = [], [], [], []

hr_line, = ax1.plot([], [], 'r-', linewidth=2)
ax1.set_ylabel("Heart Rate (BPM)")
ax1.set_ylim(40, 120)
ax1.grid(True, alpha=0.3)

rr_line, = ax2.plot([], [], 'b-', linewidth=2)
ax2.set_ylabel("Respiration Rate (BPM)")
ax2.set_ylim(5, 30)
ax2.grid(True, alpha=0.3)

range_line, = ax3.plot([], [], 'g-', linewidth=2)
ax3.set_xlabel("Time (s)")
ax3.set_ylabel("Range (m)")
ax3.set_ylim(0.3, 1.5)
ax3.grid(True, alpha=0.3)

plt.tight_layout()
plt.draw()
plt.pause(0.001)

# -----------------------------
# Range detection variables
# -----------------------------
range_history = []
range_method_scores = {}
debug_sample_count = 0
best_range_method = None

def extract_range_multi_method(tlv_data):
    """Try multiple methods to extract range and return best estimate"""
    candidates = []
    
    # Method 1: Scan for float values in reasonable range (0.2-2.5m)
    for offset in range(64, min(128, len(tlv_data)), 4):
        try:
            if offset + 4 <= len(tlv_data):
                val = struct.unpack_from('<f', tlv_data, offset)[0]
                if 0.2 < val < 2.5:
                    candidates.append(('float_scan', offset, val))
        except:
            pass
    
    # Method 2: Range index with different bin sizes
    try:
        range_idx = struct.unpack_from('<I', tlv_data, 4)[0]
        if 1 < range_idx < 100:
            for bin_size in [0.044, 0.04, 0.048, 0.05]:
                range_val = range_idx * bin_size
                if 0.2 < range_val < 2.5:
                    candidates.append(('range_idx', bin_size, range_val))
    except:
        pass
    
    # Method 3: Check specific offsets from TI docs
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
# Main loop with diagnostics
# -----------------------------
start_time = time.time()
packet_count = 0
data_saved = 0
data_skipped = 0
last_valid_hr = None
last_valid_rr = None
bytes_read = 0
sync_attempts = 0

# Track last saved values for change detection
last_saved_hr = None
last_saved_rr = None
last_saved_range = None

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
        
        # Found valid sync word!
        if packet_count == 0:
            print("✓ Found first valid packet sync word!")
        
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
            
            if packet_count == 1:
                print(f"✓ Successfully parsed first packet (Frame #{frame_num})")
            
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
                        
                        # Extract vital signs
                        breath_waveform = struct.unpack_from('<f', tlv_data, 28)[0]
                        heart_waveform = struct.unpack_from('<f', tlv_data, 32)[0]
                        heart_rate_fft = struct.unpack_from('<f', tlv_data, 36)[0]
                        breath_rate_fft = struct.unpack_from('<f', tlv_data, 52)[0]
                        
                        # Get all range candidates
                        range_candidates = extract_range_multi_method(tlv_data)
                        
                        # Debug: Print first 3 packets to see what we're getting
                        if debug_sample_count < 3:
                            print(f"\n=== Debug Packet #{debug_sample_count + 1} ===")
                            print(f"Range candidates found: {len(range_candidates)}")
                            for method, param, value in range_candidates[:5]:
                                print(f"  {method} (param={param}): {value:.3f}m = {value*100:.0f}cm")
                            debug_sample_count += 1
                        
                        # Select best range estimate
                        range_m = None
                        
                        if best_range_method is None and len(range_history) > 20:
                            method_variances = {}
                            for key in range_method_scores:
                                if len(range_method_scores[key]) > 15:
                                    variance = statistics.variance(range_method_scores[key])
                                    method_variances[key] = variance
                            
                            if method_variances:
                                best_range_method = min(method_variances, key=method_variances.get)
                                print(f"\n✓ Selected range method: {best_range_method}")
                                print(f"  Variance: {method_variances[best_range_method]:.6f}\n")
                        
                        # Use best method if determined
                        if best_range_method:
                            for method, param, value in range_candidates:
                                method_key = f"{method}_{param}"
                                if method_key == best_range_method:
                                    range_m = value
                                    break
                        
                        # Fallback: use first reasonable candidate
                        if range_m is None and range_candidates:
                            range_m = range_candidates[0][2]
                            method_key = f"{range_candidates[0][0]}_{range_candidates[0][1]}"
                            
                            if method_key not in range_method_scores:
                                range_method_scores[method_key] = []
                            range_method_scores[method_key].append(range_m)
                            if len(range_method_scores[method_key]) > 30:
                                range_method_scores[method_key].pop(0)
                        
                        # Default fallback
                        if range_m is None or range_m < 0.1 or range_m > 3.0:
                            range_m = 0.6
                        
                        # Smooth range with median filter
                        range_history.append(range_m)
                        if len(range_history) > 9:
                            range_history.pop(0)
                        
                        if len(range_history) >= 5:
                            smoothed_range = statistics.median(range_history)
                        else:
                            smoothed_range = range_m
                        
                        # Vital signs
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
                            
                            # CHANGE DETECTION: Only save if there's a significant change
                            should_save = False
                            
                            if last_saved_hr is None:
                                # First reading - always save
                                should_save = True
                            else:
                                # Check if any parameter changed significantly
                                hr_changed = abs(heart_rate - last_saved_hr) >= HR_CHANGE_THRESHOLD
                                rr_changed = abs(breath_rate - last_saved_rr) >= RR_CHANGE_THRESHOLD
                                range_changed = abs(smoothed_range - last_saved_range) >= RANGE_CHANGE_THRESHOLD
                                
                                should_save = hr_changed or rr_changed or range_changed
                            
                            if should_save:
                                # Get current timestamp with seconds set to 00
                                now = datetime.datetime.now()
                                timestamp_zeroed = now.replace(second=0, microsecond=0)
                                current_timestamp = timestamp_zeroed.strftime("%Y-%m-%d %H:%M:%S")
                                
                                # Save to CSV
                                csv_writer.writerow([
                                    current_timestamp,
                                    f"{ts:.2f}",
                                    f"{heart_rate:.2f}",
                                    f"{breath_rate:.2f}",
                                    f"{smoothed_range:.3f}",
                                    f"{heart_waveform:.4f}",
                                    f"{breath_waveform:.4f}",
                                    f"{heart_rate_fft:.2f}",
                                    f"{breath_rate_fft:.2f}"
                                ])
                                csv_file.flush()
                                data_saved += 1
                                
                                # Update last saved values
                                last_saved_hr = heart_rate
                                last_saved_rr = breath_rate
                                last_saved_range = smoothed_range
                                
                                # Print saved reading
                                print(f"[{ts:5.1f}s] [SAVED] HR: {heart_rate:5.1f} | RR: {breath_rate:4.1f} | Range: {smoothed_range:.3f}m")
                            else:
                                data_skipped += 1
                            
                            # Update plot (regardless of whether we saved)
                            times.append(ts)
                            hr_values.append(heart_rate)
                            rr_values.append(breath_rate)
                            range_values.append(smoothed_range)
                            
                            if len(times) > 100:
                                times = times[-100:]
                                hr_values = hr_values[-100:]
                                rr_values = rr_values[-100:]
                                range_values = range_values[-100:]
                            
                            # Update plot every 10 samples
                            if (data_saved + data_skipped) % 10 == 0:
                                hr_line.set_data(times, hr_values)
                                rr_line.set_data(times, rr_values)
                                range_line.set_data(times, range_values)
                                
                                if len(times) > 1:
                                    ax1.set_xlim(times[0], times[-1] + 1)
                                    ax2.set_xlim(times[0], times[-1] + 1)
                                    ax3.set_xlim(times[0], times[-1] + 1)
                                    
                                    if len(range_values) > 5:
                                        r_min = min(range_values[-20:])
                                        r_max = max(range_values[-20:])
                                        ax3.set_ylim(max(0.2, r_min - 0.1), min(2.5, r_max + 0.1))
                                
                                plt.draw()
                                plt.pause(0.001)
                    
                    except Exception as e:
                        if packet_count < 10:
                            print(f"Error parsing TLV: {e}")
                
                offset += tlv_length
            
            if packet_count % 100 == 0 and packet_count > 0:
                print(f"\n--- Packets: {packet_count} | Saved: {data_saved} | Skipped: {data_skipped} ---\n")
        
        except Exception as e:
            if packet_count < 5:
                print(f"Error parsing packet: {e}")

except KeyboardInterrupt:
    print("\n\nStopped by user")

finally:
    print("\n" + "="*60)
    print("SESSION SUMMARY")
    print("="*60)
    print(f"Duration: {time.time() - start_time:.1f} seconds")
    print(f"Total bytes read: {bytes_read:,}")
    print(f"Sync attempts: {sync_attempts:,}")
    print(f"Packets received: {packet_count}")
    print(f"Data points saved: {data_saved}")
    print(f"Data points skipped: {data_skipped} (no significant change)")
    
    if data_saved + data_skipped > 0:
        print(f"Compression ratio: {(data_skipped/(data_saved+data_skipped)*100):.1f}%")
    
    if data_saved > 0:
        avg_hr = sum(hr_values) / len(hr_values)
        avg_rr = sum(rr_values) / len(rr_values)
        avg_range = sum(range_values) / len(range_values)
        
        print(f"\nAverage HR: {avg_hr:.1f} bpm")
        print(f"Average RR: {avg_rr:.1f} bpm")
        print(f"Average Range: {avg_range:.3f}m ({avg_range*100:.0f}cm)")
        
        if len(range_values) > 10:
            range_std = statistics.stdev(range_values)
            print(f"Range Std Dev: {range_std:.3f}m ({range_std*100:.0f}cm)")
        
        print(f"\n✓ Data appended to: {MASTER_CSV}")
    else:
        print("\n⚠️  DIAGNOSTIC SUMMARY:")
        print("   No data was received. This could mean:")
        if bytes_read == 0:
            print("   1. No data on port at all - check connections")
            print("   2. Wrong DATA_PORT selected")
        else:
            print(f"   1. Read {bytes_read} bytes but found no valid packets")
            print("   2. Wrong baud rate (currently {DATA_BAUD})")
            print("   3. Configuration didn't start sensor properly")
        print("\n   Try:")
        print("   - Power cycle the radar")
        print("   - Check Device Manager for correct COM ports")
        print("   - Try running TI's GUI tool first to verify radar works")
    
    print("="*60)
    
    csv_file.close()
    user_ser.write(b'sensorStop\n')
    time.sleep(0.5)
    user_ser.close()
    data_ser.close()
    
    plt.ioff()
    plt.show()