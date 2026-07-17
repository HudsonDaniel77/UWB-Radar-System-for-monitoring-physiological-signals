import serial
import time
import struct
import csv
import datetime
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

# -----------------------------
# User Configurations
# -----------------------------
USER_PORT = 'COM5'  # User/config UART
DATA_PORT = 'COM6'  # Data UART
USER_BAUD = 115200
DATA_BAUD = 921600
CFG_FILE = r"C:\ti\mmwave_industrial_toolbox_4_12_1\labs\Vital_Signs\68xx_vital_signs\gui\profiles\xwr68xx_profile_VitalSigns_20fps_Front.cfg"

DURATION = 10  # seconds
CSV_DIR = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth"

# CALIBRATION SETTINGS
# If range reads too high, increase RANGE_OFFSET (negative value)
# If range reads too low, decrease RANGE_OFFSET (negative value)
RANGE_OFFSET = -1.85  # meters - adjust this to calibrate
RANGE_SCALE = 0.25    # Scale factor for range correction
# Example: If sensor shows 0.85m but you're at 0.50m, set RANGE_OFFSET = -0.35

# -----------------------------
# Prepare CSV file
# -----------------------------
timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
csv_filename = f"{CSV_DIR}\\vital_signs_{timestamp_str}.csv"
csv_file = open(csv_filename, "w", newline="")
csv_writer = csv.writer(csv_file)
csv_writer.writerow([
    "Time", "HeartRate_BPM", "RespirationRate_BPM", "Range_m",
    "HeartWaveform", "BreathWaveform", "HeartRate_FFT", "BreathRate_FFT"
])

print("="*60)
print("TI mmWave Radar Vital Signs Data Logger")
print("="*60)

# -----------------------------
# Connect and configure
# -----------------------------
print("\nConnecting to radar...")
user_ser = serial.Serial(USER_PORT, USER_BAUD, timeout=2)
data_ser = serial.Serial(DATA_PORT, DATA_BAUD, timeout=2)
time.sleep(1)

user_ser.reset_input_buffer()
data_ser.reset_input_buffer()

print("Stopping previous session...")
user_ser.write(b'sensorStop\n')
time.sleep(1)
user_ser.read(user_ser.in_waiting or 1)

print("Sending configuration...")
with open(CFG_FILE, "r") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('%'):
            user_ser.write((line + '\n').encode())
            time.sleep(0.05)
            if 'sensorStart' in line:
                time.sleep(2)

print("Configuration sent. Starting collection...\n")

# -----------------------------
# Prepare plotting
# -----------------------------
plt.ion()
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

# Heart rate plot
times, hr_values = [], []
hr_line, = ax1.plot([], [], 'r-', label="Heart Rate (BPM)", linewidth=2, marker='o', markersize=4)
ax1.set_xlabel("Time (s)", fontsize=11)
ax1.set_ylabel("Heart Rate (BPM)", fontsize=11)
ax1.set_title("Heart Rate", fontsize=12, fontweight='bold')
ax1.legend(fontsize=9)
ax1.set_ylim(40, 120)
ax1.grid(True, alpha=0.3)

# Respiration rate plot
rr_values = []
rr_line, = ax2.plot([], [], 'b-', label="Respiration Rate (BPM)", linewidth=2, marker='s', markersize=4)
ax2.set_xlabel("Time (s)", fontsize=11)
ax2.set_ylabel("Respiration Rate (BPM)", fontsize=11)
ax2.set_title("Respiration Rate", fontsize=12, fontweight='bold')
ax2.legend(fontsize=9)
ax2.set_ylim(5, 30)
ax2.grid(True, alpha=0.3)

fig.tight_layout()
fig.canvas.draw()
fig.canvas.flush_events()

# -----------------------------
# Main loop
# -----------------------------
start_time = time.time()
packet_count = 0
data_saved = 0
last_valid_hr = None
last_valid_rr = None
range_history = []  # For smoothing range
debug_printed = False

try:
    while time.time() - start_time < DURATION:
        # Look for magic word
        byte = data_ser.read(1)
        if not byte or byte[0] != 0x02:
            continue
        
        rest = data_ser.read(7)
        if len(rest) < 7:
            continue
        
        sync = byte + rest
        if sync != b'\x02\x01\x04\x03\x06\x05\x08\x07':
            continue
        
        # Read header
        header = data_ser.read(32)
        if len(header) < 32:
            continue
        
        try:
            version = struct.unpack('<I', header[0:4])[0]
            total_len = struct.unpack('<I', header[4:8])[0]
            platform = struct.unpack('<I', header[8:12])[0]
            frame_num = struct.unpack('<I', header[12:16])[0]
            time_cpu = struct.unpack('<I', header[16:20])[0]
            num_objs = struct.unpack('<I', header[20:24])[0]
            num_tlvs = struct.unpack('<I', header[24:28])[0]
            subframe = struct.unpack('<I', header[28:32])[0]
            
            if total_len < 40 or total_len > 65536:
                continue
            
            payload_len = total_len - 40
            payload = data_ser.read(payload_len)
            if len(payload) < payload_len:
                continue
            
            packet_count += 1
            ts = time.time() - start_time
            
            # Parse TLVs
            offset = 0
            
            while offset + 8 <= len(payload):
                tlv_type, tlv_length = struct.unpack_from('<II', payload, offset)
                offset += 8
                
                if offset + tlv_length > len(payload):
                    break
                
                # TLV Type 6 = Vital Signs Statistics
                if tlv_type == 6 and tlv_length >= 128:
                    try:
                        tlv_data = payload[offset:offset+tlv_length]
                        
                        # Debug: Print structure once
                        if not debug_printed:
                            print("\n" + "="*60)
                            print("DEBUG: Scanning TLV for range field...")
                            print("="*60)
                            print(f"Offset  uint32      float       Status")
                            print("-"*60)
                            for i in [0, 4, 8, 12, 16, 20, 24, 88, 92, 96, 100, 104, 108, 112, 116, 120, 124]:
                                if i + 4 <= len(tlv_data):
                                    try:
                                        u = struct.unpack_from('<I', tlv_data, i)[0]
                                        f = struct.unpack_from('<f', tlv_data, i)[0]
                                        status = ""
                                        if 0.2 < f < 5.0:
                                            status = " <- LIKELY RANGE"
                                        print(f"{i:<6}  {u:<10}  {f:<10.4f}  {status}")
                                    except:
                                        pass
                            print("="*60 + "\n")
                            debug_printed = True
                        
                        # Extract vital signs
                        heart_waveform = struct.unpack_from('<f', tlv_data, 32)[0]
                        breath_waveform = struct.unpack_from('<f', tlv_data, 28)[0]
                        
                        heart_rate_fft = struct.unpack_from('<f', tlv_data, 36)[0]
                        breath_rate_fft = struct.unpack_from('<f', tlv_data, 52)[0]
                        
                        # Find range - Use offset 16 which shows stable range value
                        raw_range = None
                        
                        # Primary: Check offset 16 (breathDeviation field shows range pattern)
                        if 16 + 4 <= len(tlv_data):
                            try:
                                val = struct.unpack_from('<f', tlv_data, 16)[0]
                                if 0.5 < val < 10.0:  # Reasonable range
                                    raw_range = val
                            except:
                                pass
                        
                        # Fallback: Check other offsets if offset 16 fails
                        if raw_range is None:
                            for check_offset in [12, 8, 20, 24]:
                                if check_offset + 4 <= len(tlv_data):
                                    try:
                                        val = struct.unpack_from('<f', tlv_data, check_offset)[0]
                                        if 0.5 < val < 10.0:
                                            raw_range = val
                                            break
                                    except:
                                        pass
                        
                        # Last resort: try range_idx
                        if raw_range is None:
                            range_idx = struct.unpack_from('<I', tlv_data, 4)[0]
                            if 5 < range_idx < 200:
                                raw_range = range_idx * 0.044
                        
                        # Still no range? Use default
                        if raw_range is None:
                            raw_range = 1.0
                        
                        # Smooth the range
                        range_history.append(raw_range)
                        if len(range_history) > 15:  # Average last 15 readings
                            range_history.pop(0)
                        
                        smoothed_range = sum(range_history) / len(range_history)
                        
                        # Apply calibration: scale and offset
                        range_m = (smoothed_range * RANGE_SCALE) + RANGE_OFFSET
                        
                        # Ensure range stays positive
                        if range_m < 0.1:
                            range_m = 0.1
                        
                        # Use the most reliable estimate (FFT is usually most reliable)
                        heart_rate = heart_rate_fft
                        breath_rate = breath_rate_fft
                        
                        # Validate and filter
                        hr_valid = 30 <= heart_rate <= 200
                        rr_valid = 5 <= breath_rate <= 50
                        
                        # Use last valid value if current is invalid
                        if not hr_valid and last_valid_hr is not None:
                            heart_rate = last_valid_hr
                            hr_valid = True
                        
                        if not rr_valid and last_valid_rr is not None:
                            breath_rate = last_valid_rr
                            rr_valid = True
                        
                        if hr_valid and rr_valid:
                            last_valid_hr = heart_rate
                            last_valid_rr = breath_rate
                            
                            # Save to CSV
                            csv_writer.writerow([
                                f"{ts:.2f}",
                                f"{heart_rate:.2f}",
                                f"{breath_rate:.2f}",
                                f"{range_m:.3f}",
                                f"{heart_waveform:.4f}",
                                f"{breath_waveform:.4f}",
                                f"{heart_rate_fft:.2f}",
                                f"{breath_rate_fft:.2f}"
                            ])
                            csv_file.flush()
                            data_saved += 1
                            
                            # Update plot
                            times.append(ts)
                            hr_values.append(heart_rate)
                            rr_values.append(breath_rate)
                            
                            # Keep last 200 points
                            if len(times) > 200:
                                times = times[-200:]
                                hr_values = hr_values[-200:]
                                rr_values = rr_values[-200:]
                            
                            hr_line.set_data(times, hr_values)
                            rr_line.set_data(times, rr_values)
                            
                            # Update x-axis limits
                            ax1.set_xlim(max(0, ts-30), ts+2)
                            ax2.set_xlim(max(0, ts-30), ts+2)
                            
                            # Auto-scale y-axis if needed
                            if len(hr_values) > 10:
                                hr_min, hr_max = min(hr_values[-50:]), max(hr_values[-50:])
                                ax1.set_ylim(max(30, hr_min-10), min(200, hr_max+10))
                            
                            if len(rr_values) > 10:
                                rr_min, rr_max = min(rr_values[-50:]), max(rr_values[-50:])
                                ax2.set_ylim(max(5, rr_min-3), min(50, rr_max+3))
                            
                            fig.canvas.draw()
                            fig.canvas.flush_events()
                            
                            # Print every 5th valid reading
                            if data_saved % 5 == 0:
                                print(f"[{ts:6.2f}s] Frame {frame_num:5d} | HR: {heart_rate:5.1f} bpm | RR: {breath_rate:4.1f} bpm | Range: {range_m:4.2f} m (raw: {raw_range:.2f}m, offset: {RANGE_OFFSET:+.2f}m)")
                    
                    except Exception as e:
                        if packet_count < 10:
                            print(f"Parse error: {e}")
                
                offset += tlv_length
            
            # Print stats every 100 packets
            if packet_count % 100 == 0:
                print(f"\n--- Packets: {packet_count} | Data saved: {data_saved} ---\n")
        
        except Exception as e:
            if packet_count < 10:
                print(f"Packet error: {e}")

except KeyboardInterrupt:
    print("\n\nStopped by user")

finally:
    print("\n" + "="*60)
    print("SESSION SUMMARY")
    print("="*60)
    print(f"Duration: {time.time() - start_time:.1f} seconds")
    print(f"Total packets received: {packet_count}")
    print(f"Valid data points saved: {data_saved}")
    
    if data_saved > 0:
        avg_hr = sum(hr_values) / len(hr_values) if hr_values else 0
        avg_rr = sum(rr_values) / len(rr_values) if rr_values else 0
        print(f"\nAverage Heart Rate: {avg_hr:.1f} bpm")
        print(f"Average Respiration Rate: {avg_rr:.1f} bpm")
        if range_history:
            avg_range_raw = sum(range_history) / len(range_history)
            avg_range_calibrated = avg_range_raw + RANGE_OFFSET
            print(f"Average Range: {avg_range_calibrated:.3f} m ({avg_range_calibrated*100:.1f} cm)")
            print(f"  (Raw: {avg_range_raw:.3f}m, Offset: {RANGE_OFFSET:+.2f}m)")
        print(f"\n✓ Data successfully saved to:")
        print(f"  {csv_filename}")
    else:
        print("\n✗ No valid data was collected")
    
    print("="*60)
    
    csv_file.close()
    user_ser.write(b'sensorStop\n')
    time.sleep(0.5)
    user_ser.close()
    data_ser.close()
    
    plt.ioff()
    plt.show()