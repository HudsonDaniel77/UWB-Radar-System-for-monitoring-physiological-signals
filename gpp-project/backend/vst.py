# import serial
# import time
# import struct
# import csv
# import datetime
# import matplotlib
# matplotlib.use("TkAgg")
# import matplotlib.pyplot as plt
# import statistics
# import os

# # -----------------------------
# # User Configurations
# # -----------------------------
# USER_PORT = 'COM5'
# DATA_PORT = 'COM6'
# USER_BAUD = 115200
# DATA_BAUD = 921600
# CFG_FILE = r"C:\ti\mmwave_industrial_toolbox_4_12_1\labs\Vital_Signs\68xx_vital_signs\gui\profiles\xwr68xx_profile_VitalSigns_20fps_Front.cfg"

# DURATION = 10  # seconds
# CSV_DIR = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project\backend"

# # Single CSV file for all data
# MASTER_CSV = f"{CSV_DIR}\\vital_signs_data_new.csv"

# # Change detection thresholds
# HR_CHANGE_THRESHOLD = 2.0  # BPM
# RR_CHANGE_THRESHOLD = 1.0  # BPM
# RANGE_CHANGE_THRESHOLD = 0.05  # meters (5 cm)

# # -----------------------------
# # Prepare CSV file (append mode)
# # -----------------------------
# file_exists = os.path.exists(MASTER_CSV)

# csv_file = open(MASTER_CSV, "a", newline="")
# csv_writer = csv.writer(csv_file)

# # Write header only if file is new
# if not file_exists:
#     csv_writer.writerow([
#         "Timestamp", "SessionTime", "HeartRate_BPM", "RespirationRate_BPM", "Range_m",
#         "HeartWaveform", "BreathWaveform", "HeartRate_FFT", "BreathRate_FFT"
#     ])
#     print(f"[OK] Created new file: {MASTER_CSV}")
# else:
#     print(f"[OK] Appending to existing file: {MASTER_CSV}")

# print("="*60)
# print("TI mmWave Radar Vital Signs Data Logger")
# print("="*60)
# print("\nChange Detection Enabled:")
# print(f"  - Heart Rate threshold: +/- {HR_CHANGE_THRESHOLD} bpm")
# print(f"  - Respiration Rate threshold: +/- {RR_CHANGE_THRESHOLD} bpm")
# print(f"  - Range threshold: +/- {RANGE_CHANGE_THRESHOLD*100:.0f} cm")

# print("="*60)

# # -----------------------------
# # Connect and configure
# # -----------------------------
# print("\nConnecting to radar...")
# user_ser = serial.Serial(USER_PORT, USER_BAUD, timeout=2)
# data_ser = serial.Serial(DATA_PORT, DATA_BAUD, timeout=2)
# time.sleep(1)

# user_ser.reset_input_buffer()
# data_ser.reset_input_buffer()

# print("Stopping previous session...")
# user_ser.write(b'sensorStop\n')
# time.sleep(1)
# user_ser.read(user_ser.in_waiting or 1)

# print("Sending configuration...")
# with open(CFG_FILE, "r") as f:
#     for line in f:
#         line = line.strip()
#         if line and not line.startswith('%'):
#             user_ser.write((line + '\n').encode())
#             time.sleep(0.05)
#             if 'sensorStart' in line:
#                 time.sleep(2)

# print("Configuration sent. Starting collection...\n")

# # -----------------------------
# # Prepare plotting
# # -----------------------------
# plt.ion()
# fig, axes = plt.subplots(3, 1, figsize=(10, 8))
# ax1, ax2, ax3 = axes

# times, hr_values, rr_values, range_values = [], [], [], []

# hr_line, = ax1.plot([], [], 'r-', linewidth=2)
# ax1.set_ylabel("Heart Rate (BPM)")
# ax1.set_ylim(40, 120)
# ax1.grid(True, alpha=0.3)

# rr_line, = ax2.plot([], [], 'b-', linewidth=2)
# ax2.set_ylabel("Respiration Rate (BPM)")
# ax2.set_ylim(5, 30)
# ax2.grid(True, alpha=0.3)

# range_line, = ax3.plot([], [], 'g-', linewidth=2)
# ax3.set_xlabel("Time (s)")
# ax3.set_ylabel("Range (m)")
# ax3.set_ylim(0.3, 1.5)
# ax3.grid(True, alpha=0.3)

# plt.tight_layout()
# plt.draw()
# plt.pause(0.001)

# # -----------------------------
# # Range detection variables
# # -----------------------------
# range_history = []
# range_method_scores = {}
# debug_sample_count = 0
# best_range_method = None

# def extract_range_multi_method(tlv_data):
#     """Try multiple methods to extract range and return best estimate"""
#     candidates = []
    
#     # Method 1: Scan for float values in reasonable range (0.2-2.5m)
#     for offset in range(64, min(128, len(tlv_data)), 4):
#         try:
#             if offset + 4 <= len(tlv_data):
#                 val = struct.unpack_from('<f', tlv_data, offset)[0]
#                 if 0.2 < val < 2.5:
#                     candidates.append(('float_scan', offset, val))
#         except:
#             pass
    
#     # Method 2: Range index with different bin sizes
#     try:
#         range_idx = struct.unpack_from('<I', tlv_data, 4)[0]
#         if 1 < range_idx < 100:
#             for bin_size in [0.044, 0.04, 0.048, 0.05]:
#                 range_val = range_idx * bin_size
#                 if 0.2 < range_val < 2.5:
#                     candidates.append(('range_idx', bin_size, range_val))
#     except:
#         pass
    
#     # Method 3: Check specific offsets from TI docs
#     specific_offsets = [64, 68, 72, 76, 80, 84, 88, 92, 96, 100, 104, 108]
#     for offset in specific_offsets:
#         try:
#             if offset + 4 <= len(tlv_data):
#                 val = struct.unpack_from('<f', tlv_data, offset)[0]
#                 if 0.2 < val < 2.5:
#                     candidates.append(('specific', offset, val))
#         except:
#             pass
    
#     return candidates

# # -----------------------------
# # Main loop
# # -----------------------------
# start_time = time.time()
# packet_count = 0
# data_saved = 0
# data_skipped = 0
# last_valid_hr = None
# last_valid_rr = None

# # Track last saved values for change detection
# last_saved_hr = None
# last_saved_rr = None
# last_saved_range = None

# try:
#     while time.time() - start_time < DURATION:
#         byte = data_ser.read(1)
#         if not byte or byte[0] != 0x02:
#             continue
        
#         rest = data_ser.read(7)
#         if len(rest) < 7:
#             continue
        
#         sync = byte + rest
#         if sync != b'\x02\x01\x04\x03\x06\x05\x08\x07':
#             continue
        
#         header = data_ser.read(32)
#         if len(header) < 32:
#             continue
        
#         try:
#             total_len = struct.unpack('<I', header[4:8])[0]
#             frame_num = struct.unpack('<I', header[12:16])[0]
            
#             if total_len < 40 or total_len > 65536:
#                 continue
            
#             payload_len = total_len - 40
#             payload = data_ser.read(payload_len)
#             if len(payload) < payload_len:
#                 continue
            
#             packet_count += 1
#             ts = time.time() - start_time
            
#             offset = 0
            
#             while offset + 8 <= len(payload):
#                 tlv_type, tlv_length = struct.unpack_from('<II', payload, offset)
#                 offset += 8
                
#                 if offset + tlv_length > len(payload):
#                     break
                
#                 if tlv_type == 6 and tlv_length >= 128:
#                     try:
#                         tlv_data = payload[offset:offset+tlv_length]
                        
#                         # Extract vital signs
#                         breath_waveform = struct.unpack_from('<f', tlv_data, 28)[0]
#                         heart_waveform = struct.unpack_from('<f', tlv_data, 32)[0]
#                         heart_rate_fft = struct.unpack_from('<f', tlv_data, 36)[0]
#                         breath_rate_fft = struct.unpack_from('<f', tlv_data, 52)[0]
                        
#                         # Get all range candidates
#                         range_candidates = extract_range_multi_method(tlv_data)
                        
#                         # Debug: Print first 3 packets to see what we're getting
#                         if debug_sample_count < 3:
#                             print(f"\n=== Debug Packet #{debug_sample_count + 1} ===")
#                             print(f"Range candidates found: {len(range_candidates)}")
#                             for method, param, value in range_candidates[:5]:
#                                 print(f"  {method} (param={param}): {value:.3f}m = {value*100:.0f}cm")
#                             debug_sample_count += 1
                        
#                         # Select best range estimate
#                         range_m = None
                        
#                         if best_range_method is None and len(range_history) > 20:
#                             method_variances = {}
#                             for key in range_method_scores:
#                                 if len(range_method_scores[key]) > 15:
#                                     variance = statistics.variance(range_method_scores[key])
#                                     method_variances[key] = variance
                            
#                             if method_variances:
#                                 best_range_method = min(method_variances, key=method_variances.get)
#                                 print(f"\nData appended to: {MASTER_CSV}")
#                                 print(f"  Variance: {method_variances[best_range_method]:.6f}\n")
                        
#                         # Use best method if determined
#                         if best_range_method:
#                             for method, param, value in range_candidates:
#                                 method_key = f"{method}_{param}"
#                                 if method_key == best_range_method:
#                                     range_m = value
#                                     break
                        
#                         # Fallback: use first reasonable candidate
#                         if range_m is None and range_candidates:
#                             range_m = range_candidates[0][2]
#                             method_key = f"{range_candidates[0][0]}_{range_candidates[0][1]}"
                            
#                             if method_key not in range_method_scores:
#                                 range_method_scores[method_key] = []
#                             range_method_scores[method_key].append(range_m)
#                             if len(range_method_scores[method_key]) > 30:
#                                 range_method_scores[method_key].pop(0)
                        
#                         # Default fallback
#                         if range_m is None or range_m < 0.1 or range_m > 3.0:
#                             range_m = 0.6
                        
#                         # Smooth range with median filter
#                         range_history.append(range_m)
#                         if len(range_history) > 9:
#                             range_history.pop(0)
                        
#                         if len(range_history) >= 5:
#                             smoothed_range = statistics.median(range_history)
#                         else:
#                             smoothed_range = range_m
                        
#                         # Vital signs
#                         heart_rate = heart_rate_fft
#                         breath_rate = breath_rate_fft
                        
#                         hr_valid = 30 <= heart_rate <= 200
#                         rr_valid = 5 <= breath_rate <= 50
                        
#                         if not hr_valid and last_valid_hr is not None:
#                             heart_rate = last_valid_hr
#                             hr_valid = True
                        
#                         if not rr_valid and last_valid_rr is not None:
#                             breath_rate = last_valid_rr
#                             rr_valid = True
                        
#                         if hr_valid and rr_valid:
#                             last_valid_hr = heart_rate
#                             last_valid_rr = breath_rate
                            
#                             # CHANGE DETECTION: Only save if there's a significant change
#                             should_save = False
                            
#                             if last_saved_hr is None:
#                                 # First reading - always save
#                                 should_save = True
#                             else:
#                                 # Check if any parameter changed significantly
#                                 hr_changed = abs(heart_rate - last_saved_hr) >= HR_CHANGE_THRESHOLD
#                                 rr_changed = abs(breath_rate - last_saved_rr) >= RR_CHANGE_THRESHOLD
#                                 range_changed = abs(smoothed_range - last_saved_range) >= RANGE_CHANGE_THRESHOLD
                                
#                                 should_save = hr_changed or rr_changed or range_changed
                            
#                             if should_save:
#                                 # Get current timestamp
#                                 current_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                
#                                 # Save to CSV
#                                 csv_writer.writerow([
#                                     current_timestamp,
#                                     f"{ts:.2f}",
#                                     f"{heart_rate:.2f}",
#                                     f"{breath_rate:.2f}",
#                                     f"{smoothed_range:.3f}",
#                                     f"{heart_waveform:.4f}",
#                                     f"{breath_waveform:.4f}",
#                                     f"{heart_rate_fft:.2f}",
#                                     f"{breath_rate_fft:.2f}"
#                                 ])
#                                 csv_file.flush()
#                                 data_saved += 1
                                
#                                 # Update last saved values
#                                 last_saved_hr = heart_rate
#                                 last_saved_rr = breath_rate
#                                 last_saved_range = smoothed_range
                                
#                                 # Print saved reading
#                                 print(f"[{ts:5.1f}s] [SAVED] HR: {heart_rate:5.1f} | RR: {breath_rate:4.1f} | Range: {smoothed_range:.3f}m")
#                             else:
#                                 data_skipped += 1
#                                 # Optionally print skipped readings (uncomment if needed)
#                                 # if data_skipped % 10 == 0:
#                                 #     print(f"[{ts:5.1f}s] - skipped (no change)")
                            
#                             # Update plot (regardless of whether we saved)
#                             times.append(ts)
#                             hr_values.append(heart_rate)
#                             rr_values.append(breath_rate)
#                             range_values.append(smoothed_range)
                            
#                             if len(times) > 100:
#                                 times = times[-100:]
#                                 hr_values = hr_values[-100:]
#                                 rr_values = rr_values[-100:]
#                                 range_values = range_values[-100:]
                            
#                             # Update plot every 10 samples
#                             if (data_saved + data_skipped) % 10 == 0:
#                                 hr_line.set_data(times, hr_values)
#                                 rr_line.set_data(times, rr_values)
#                                 range_line.set_data(times, range_values)
                                
#                                 if len(times) > 1:
#                                     ax1.set_xlim(times[0], times[-1] + 1)
#                                     ax2.set_xlim(times[0], times[-1] + 1)
#                                     ax3.set_xlim(times[0], times[-1] + 1)
                                    
#                                     if len(range_values) > 5:
#                                         r_min = min(range_values[-20:])
#                                         r_max = max(range_values[-20:])
#                                         ax3.set_ylim(max(0.2, r_min - 0.1), min(2.5, r_max + 0.1))
                                
#                                 plt.draw()
#                                 plt.pause(0.001)
                    
#                     except Exception as e:
#                         if packet_count < 10:
#                             print(f"Error: {e}")
                
#                 offset += tlv_length
            
#             if packet_count % 100 == 0 and packet_count > 0:
#                 print(f"\n--- Packets: {packet_count} | Saved: {data_saved} | Skipped: {data_skipped} ---\n")
        
#         except Exception as e:
#             pass

# except KeyboardInterrupt:
#     print("\n\nStopped by user")

# finally:
#     print("\n" + "="*60)
#     print("SESSION SUMMARY")
#     print("="*60)
#     print(f"Duration: {time.time() - start_time:.1f} seconds")
#     print(f"Packets received: {packet_count}")
#     print(f"Data points saved: {data_saved}")
#     print(f"Data points skipped: {data_skipped} (no significant change)")
#     print(f"Compression ratio: {(data_skipped/(data_saved+data_skipped)*100) if (data_saved+data_skipped) > 0 else 0:.1f}%")
    
#     if data_saved > 0:
#         avg_hr = sum(hr_values) / len(hr_values)
#         avg_rr = sum(rr_values) / len(rr_values)
#         avg_range = sum(range_values) / len(range_values)
        
#         print(f"\nAverage HR: {avg_hr:.1f} bpm")
#         print(f"Average RR: {avg_rr:.1f} bpm")
#         print(f"Average Range: {avg_range:.3f}m ({avg_range*100:.0f}cm)")
        
#         if len(range_values) > 10:
#             range_std = statistics.stdev(range_values)
#             print(f"Range Std Dev: {range_std:.3f}m ({range_std*100:.0f}cm)")
        
#         print(f"\n✓ Data appended to: {MASTER_CSV}")
    
#     print("="*60)
    
#     csv_file.close()
#     user_ser.write(b'sensorStop\n')
#     time.sleep(0.5)
#     user_ser.close()
#     data_ser.close()
    
#     plt.ioff()
#     plt.show()

# # import serial
# # import time
# # import struct
# # import csv
# # import datetime
# # import matplotlib
# # matplotlib.use("TkAgg")
# # import matplotlib.pyplot as plt
# # import statistics
# # import os

# # # --- NEW: imports for Firebase and argv handling ---
# # import sys
# # import firebase_admin
# # from firebase_admin import credentials, firestore

# # # -----------------------------
# # # Read command-line args
# # # -----------------------------
# # # Expect: python vst.py <user_email> <config_number>
# # if len(sys.argv) >= 3:
# #     USER_EMAIL = sys.argv[1]
# #     try:
# #         CONFIG_FILE_NUMBER = int(sys.argv[2])
# #     except:
# #         CONFIG_FILE_NUMBER = 0
# # else:
# #     # Fallback defaults (if you run locally without args)
# #     USER_EMAIL = "unknown_user"
# #     CONFIG_FILE_NUMBER = 0

# # # -----------------------------
# # # Initialize Firebase Admin SDK
# # # -----------------------------
# # # Ensure serviceAccountKey.json is in the same folder (or provide full path)
# # try:
# #     cred = credentials.Certificate("serviceAccountKey.json")
# #     firebase_admin.initialize_app(cred)
# #     db = firestore.client()
# #     FIREBASE_ENABLED = True
# # except Exception as e:
# #     # If firebase not configured, we continue but mark disabled
# #     print(f"[WARN] Firebase init failed: {e}")
# #     FIREBASE_ENABLED = False

# # # -----------------------------
# # # User Configurations
# # # -----------------------------
# # USER_PORT = 'COM5'
# # DATA_PORT = 'COM6'
# # USER_BAUD = 115200
# # DATA_BAUD = 921600
# # CFG_FILE = r"C:\ti\mmwave_industrial_toolbox_4_12_1\labs\Vital_Signs\68xx_vital_signs\gui\profiles\xwr68xx_profile_VitalSigns_20fps_Front.cfg"

# # DURATION = 10  # seconds
# # CSV_DIR = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project\backend"

# # # Single CSV file for all data
# # MASTER_CSV = f"{CSV_DIR}\\vital_signs_data.csv"

# # # Change detection thresholds
# # HR_CHANGE_THRESHOLD = 2.0  # BPM
# # RR_CHANGE_THRESHOLD = 1.0  # BPM
# # RANGE_CHANGE_THRESHOLD = 0.05  # meters (5 cm)

# # # -----------------------------
# # # Prepare CSV file (append mode)
# # # -----------------------------
# # file_exists = os.path.exists(MASTER_CSV)

# # csv_file = open(MASTER_CSV, "a", newline="")
# # csv_writer = csv.writer(csv_file)

# # # Write header only if file is new
# # if not file_exists:
# #     csv_writer.writerow([
# #         "Timestamp", "User", "SessionTime", "HeartRate_BPM", "RespirationRate_BPM", "Range_m",
# #         "HeartWaveform", "BreathWaveform", "HeartRate_FFT", "BreathRate_FFT", "ConfigurationFile"
# #     ])
# #     print(f"[OK] Created new file: {MASTER_CSV}")
# # else:
# #     print(f"[OK] Appending to existing file: {MASTER_CSV}")

# # print("="*60)
# # print("TI mmWave Radar Vital Signs Data Logger")
# # print("="*60)
# # print("\nChange Detection Enabled:")
# # print(f"  - Heart Rate threshold: +/- {HR_CHANGE_THRESHOLD} bpm")
# # print(f"  - Respiration Rate threshold: +/- {RR_CHANGE_THRESHOLD} bpm")
# # print(f"  - Range threshold: +/- {RANGE_CHANGE_THRESHOLD*100:.0f} cm")
# # print(f"\nUser: {USER_EMAIL} | ConfigurationFile: {CONFIG_FILE_NUMBER}")
# # print("="*60)

# # # -----------------------------
# # # Connect and configure
# # # -----------------------------
# # print("\nConnecting to radar...")
# # user_ser = serial.Serial(USER_PORT, USER_BAUD, timeout=2)
# # data_ser = serial.Serial(DATA_PORT, DATA_BAUD, timeout=2)
# # time.sleep(1)

# # user_ser.reset_input_buffer()
# # data_ser.reset_input_buffer()

# # print("Stopping previous session...")
# # user_ser.write(b'sensorStop\n')
# # time.sleep(1)
# # user_ser.read(user_ser.in_waiting or 1)

# # print("Sending configuration...")
# # with open(CFG_FILE, "r") as f:
# #     for line in f:
# #         line = line.strip()
# #         if line and not line.startswith('%'):
# #             user_ser.write((line + '\n').encode())
# #             time.sleep(0.05)
# #             if 'sensorStart' in line:
# #                 time.sleep(2)

# # print("Configuration sent. Starting collection...\n")

# # # -----------------------------
# # # Prepare plotting
# # # -----------------------------
# # plt.ion()
# # fig, axes = plt.subplots(3, 1, figsize=(10, 8))
# # ax1, ax2, ax3 = axes

# # times, hr_values, rr_values, range_values = [], [], [], []

# # hr_line, = ax1.plot([], [], 'r-', linewidth=2)
# # ax1.set_ylabel("Heart Rate (BPM)")
# # ax1.set_ylim(40, 120)
# # ax1.grid(True, alpha=0.3)

# # rr_line, = ax2.plot([], [], 'b-', linewidth=2)
# # ax2.set_ylabel("Respiration Rate (BPM)")
# # ax2.set_ylim(5, 30)
# # ax2.grid(True, alpha=0.3)

# # range_line, = ax3.plot([], [], 'g-', linewidth=2)
# # ax3.set_xlabel("Time (s)")
# # ax3.set_ylabel("Range (m)")
# # ax3.set_ylim(0.3, 1.5)
# # ax3.grid(True, alpha=0.3)

# # plt.tight_layout()
# # plt.draw()
# # plt.pause(0.001)

# # # -----------------------------
# # # Range detection variables
# # # -----------------------------
# # range_history = []
# # range_method_scores = {}
# # debug_sample_count = 0
# # best_range_method = None

# # def extract_range_multi_method(tlv_data):
# #     """Try multiple methods to extract range and return best estimate"""
# #     candidates = []
    
# #     # Method 1: Scan for float values in reasonable range (0.2-2.5m)
# #     for offset in range(64, min(128, len(tlv_data)), 4):
# #         try:
# #             if offset + 4 <= len(tlv_data):
# #                 val = struct.unpack_from('<f', tlv_data, offset)[0]
# #                 if 0.2 < val < 2.5:
# #                     candidates.append(('float_scan', offset, val))
# #         except:
# #             pass
    
# #     # Method 2: Range index with different bin sizes
# #     try:
# #         range_idx = struct.unpack_from('<I', tlv_data, 4)[0]
# #         if 1 < range_idx < 100:
# #             for bin_size in [0.044, 0.04, 0.048, 0.05]:
# #                 range_val = range_idx * bin_size
# #                 if 0.2 < range_val < 2.5:
# #                     candidates.append(('range_idx', bin_size, range_val))
# #     except:
# #         pass
    
# #     # Method 3: Check specific offsets from TI docs
# #     specific_offsets = [64, 68, 72, 76, 80, 84, 88, 92, 96, 100, 104, 108]
# #     for offset in specific_offsets:
# #         try:
# #             if offset + 4 <= len(tlv_data):
# #                 val = struct.unpack_from('<f', tlv_data, offset)[0]
# #                 if 0.2 < val < 2.5:
# #                     candidates.append(('specific', offset, val))
# #         except:
# #             pass
    
# #     return candidates

# # # -----------------------------
# # # Main loop
# # # -----------------------------
# # start_time = time.time()
# # packet_count = 0
# # data_saved = 0
# # data_skipped = 0
# # last_valid_hr = None
# # last_valid_rr = None

# # # Track last saved values for change detection
# # last_saved_hr = None
# # last_saved_rr = None
# # last_saved_range = None

# # try:
# #     while time.time() - start_time < DURATION:
# #         byte = data_ser.read(1)
# #         if not byte or byte[0] != 0x02:
# #             continue
        
# #         rest = data_ser.read(7)
# #         if len(rest) < 7:
# #             continue
        
# #         sync = byte + rest
# #         if sync != b'\x02\x01\x04\x03\x06\x05\x08\x07':
# #             continue
        
# #         header = data_ser.read(32)
# #         if len(header) < 32:
# #             continue
        
# #         try:
# #             total_len = struct.unpack('<I', header[4:8])[0]
# #             frame_num = struct.unpack('<I', header[12:16])[0]
            
# #             if total_len < 40 or total_len > 65536:
# #                 continue
            
# #             payload_len = total_len - 40
# #             payload = data_ser.read(payload_len)
# #             if len(payload) < payload_len:
# #                 continue
            
# #             packet_count += 1
# #             ts = time.time() - start_time
            
# #             offset = 0
            
# #             while offset + 8 <= len(payload):
# #                 tlv_type, tlv_length = struct.unpack_from('<II', payload, offset)
# #                 offset += 8
                
# #                 if offset + tlv_length > len(payload):
# #                     break
                
# #                 if tlv_type == 6 and tlv_length >= 128:
# #                     try:
# #                         tlv_data = payload[offset:offset+tlv_length]
                        
# #                         # Extract vital signs
# #                         breath_waveform = struct.unpack_from('<f', tlv_data, 28)[0]
# #                         heart_waveform = struct.unpack_from('<f', tlv_data, 32)[0]
# #                         heart_rate_fft = struct.unpack_from('<f', tlv_data, 36)[0]
# #                         breath_rate_fft = struct.unpack_from('<f', tlv_data, 52)[0]
                        
# #                         # Get all range candidates
# #                         range_candidates = extract_range_multi_method(tlv_data)
                        
# #                         # Debug: Print first 3 packets to see what we're getting
# #                         if debug_sample_count < 3:
# #                             print(f"\n=== Debug Packet #{debug_sample_count + 1} ===")
# #                             print(f"Range candidates found: {len(range_candidates)}")
# #                             for method, param, value in range_candidates[:5]:
# #                                 print(f"  {method} (param={param}): {value:.3f}m = {value*100:.0f}cm")
# #                             debug_sample_count += 1
                        
# #                         # Select best range estimate
# #                         range_m = None
                        
# #                         if best_range_method is None and len(range_history) > 20:
# #                             method_variances = {}
# #                             for key in range_method_scores:
# #                                 if len(range_method_scores[key]) > 15:
# #                                     variance = statistics.variance(range_method_scores[key])
# #                                     method_variances[key] = variance
                            
# #                             if method_variances:
# #                                 best_range_method = min(method_variances, key=method_variances.get)
# #                                 print(f"\nData appended to: {MASTER_CSV}")
# #                                 print(f"  Variance: {method_variances[best_range_method]:.6f}\n")
                        
# #                         # Use best method if determined
# #                         if best_range_method:
# #                             for method, param, value in range_candidates:
# #                                 method_key = f"{method}_{param}"
# #                                 if method_key == best_range_method:
# #                                     range_m = value
# #                                     break
                        
# #                         # Fallback: use first reasonable candidate
# #                         if range_m is None and range_candidates:
# #                             range_m = range_candidates[0][2]
# #                             method_key = f"{range_candidates[0][0]}_{range_candidates[0][1]}"
                            
# #                             if method_key not in range_method_scores:
# #                                 range_method_scores[method_key] = []
# #                             range_method_scores[method_key].append(range_m)
# #                             if len(range_method_scores[method_key]) > 30:
# #                                 range_method_scores[method_key].pop(0)
                        
# #                         # Default fallback
# #                         if range_m is None or range_m < 0.1 or range_m > 3.0:
# #                             range_m = 0.6
                        
# #                         # Smooth range with median filter
# #                         range_history.append(range_m)
# #                         if len(range_history) > 9:
# #                             range_history.pop(0)
                        
# #                         if len(range_history) >= 5:
# #                             smoothed_range = statistics.median(range_history)
# #                         else:
# #                             smoothed_range = range_m
                        
# #                         # Vital signs
# #                         heart_rate = heart_rate_fft
# #                         breath_rate = breath_rate_fft
                        
# #                         hr_valid = 30 <= heart_rate <= 200
# #                         rr_valid = 5 <= breath_rate <= 50
                        
# #                         if not hr_valid and last_valid_hr is not None:
# #                             heart_rate = last_valid_hr
# #                             hr_valid = True
                        
# #                         if not rr_valid and last_valid_rr is not None:
# #                             breath_rate = last_valid_rr
# #                             rr_valid = True
                        
# #                         if hr_valid and rr_valid:
# #                             last_valid_hr = heart_rate
# #                             last_valid_rr = breath_rate
                            
# #                             # CHANGE DETECTION: Only save if there's a significant change
# #                             should_save = False
                            
# #                             if last_saved_hr is None:
# #                                 # First reading - always save
# #                                 should_save = True
# #                             else:
# #                                 # Check if any parameter changed significantly
# #                                 hr_changed = abs(heart_rate - last_saved_hr) >= HR_CHANGE_THRESHOLD
# #                                 rr_changed = abs(breath_rate - last_saved_rr) >= RR_CHANGE_THRESHOLD
# #                                 range_changed = abs(smoothed_range - last_saved_range) >= RANGE_CHANGE_THRESHOLD
                                
# #                                 should_save = hr_changed or rr_changed or range_changed
                            
# #                             if should_save:
# #                                 # Get current timestamp
# #                                 current_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                
# #                                 # Save to CSV
# #                                 csv_writer.writerow([
# #                                     current_timestamp,
# #                                     USER_EMAIL,
# #                                     f"{ts:.2f}",
# #                                     f"{heart_rate:.2f}",
# #                                     f"{breath_rate:.2f}",
# #                                     f"{smoothed_range:.3f}",
# #                                     f"{heart_waveform:.4f}",
# #                                     f"{breath_waveform:.4f}",
# #                                     f"{heart_rate_fft:.2f}",
# #                                     f"{breath_rate_fft:.2f}",
# #                                     CONFIG_FILE_NUMBER
# #                                 ])
# #                                 csv_file.flush()
# #                                 data_saved += 1
                                
# #                                 # Save to Firestore (collection: VitalSignsData)
# #                                 if FIREBASE_ENABLED:
# #                                     try:
# #                                         db.collection("VitalSignsData").add({
# #                                             "Timestamp": current_timestamp,
# #                                             "User": USER_EMAIL,
# #                                             "SessionTime": float(ts),
# #                                             "HeartRate_BPM": float(round(heart_rate, 2)),
# #                                             "RespirationRate_BPM": float(round(breath_rate, 2)),
# #                                             "Range_m": float(round(smoothed_range, 3)),
# #                                             "HeartWaveform": float(round(heart_waveform, 4)),
# #                                             "BreathWaveform": float(round(breath_waveform, 4)),
# #                                             "HeartRate_FFT": float(round(heart_rate_fft, 2)),
# #                                             "BreathRate_FFT": float(round(breath_rate_fft, 2)),
# #                                             "ConfigurationFile": int(CONFIG_FILE_NUMBER)
# #                                         })
# #                                     except Exception as e:
# #                                         print(f"[WARN] Firestore write failed: {e}")
                                
# #                                 # Update last saved values
# #                                 last_saved_hr = heart_rate
# #                                 last_saved_rr = breath_rate
# #                                 last_saved_range = smoothed_range
                                
# #                                 # Print saved reading
# #                                 print(f"[{ts:5.1f}s] [SAVED] HR: {heart_rate:5.1f} | RR: {breath_rate:4.1f} | Range: {smoothed_range:.3f}m")
# #                             else:
# #                                 data_skipped += 1
# #                                 # Optionally print skipped readings (uncomment if needed)
# #                                 # if data_skipped % 10 == 0:
# #                                 #     print(f"[{ts:5.1f}s] - skipped (no change)")
                            
# #                             # Update plot (regardless of whether we saved)
# #                             times.append(ts)
# #                             hr_values.append(heart_rate)
# #                             rr_values.append(breath_rate)
# #                             range_values.append(smoothed_range)
                            
# #                             if len(times) > 100:
# #                                 times = times[-100:]
# #                                 hr_values = hr_values[-100:]
# #                                 rr_values = rr_values[-100:]
# #                                 range_values = range_values[-100:]
                            
# #                             # Update plot every 10 samples
# #                             if (data_saved + data_skipped) % 10 == 0:
# #                                 hr_line.set_data(times, hr_values)
# #                                 rr_line.set_data(times, rr_values)
# #                                 range_line.set_data(times, range_values)
                                
# #                                 if len(times) > 1:
# #                                     ax1.set_xlim(times[0], times[-1] + 1)
# #                                     ax2.set_xlim(times[0], times[-1] + 1)
# #                                     ax3.set_xlim(times[0], times[-1] + 1)
                                    
# #                                     if len(range_values) > 5:
# #                                         r_min = min(range_values[-20:])
# #                                         r_max = max(range_values[-20:])
# #                                         ax3.set_ylim(max(0.2, r_min - 0.1), min(2.5, r_max + 0.1))
                                
# #                                 plt.draw()
# #                                 plt.pause(0.001)
                    
# #                     except Exception as e:
# #                         if packet_count < 10:
# #                             print(f"Error: {e}")
                
# #                 offset += tlv_length
            
# #             if packet_count % 100 == 0 and packet_count > 0:
# #                 print(f"\n--- Packets: {packet_count} | Saved: {data_saved} | Skipped: {data_skipped} ---\n")
        
# #         except Exception as e:
# #             pass

# # except KeyboardInterrupt:
# #     print("\n\nStopped by user")

# # finally:
# #     print("\n" + "="*60)
# #     print("SESSION SUMMARY")
# #     print("="*60)
# #     print(f"Duration: {time.time() - start_time:.1f} seconds")
# #     print(f"Packets received: {packet_count}")
# #     print(f"Data points saved: {data_saved}")
# #     print(f"Data points skipped: {data_skipped} (no significant change)")
# #     print(f"Compression ratio: {(data_skipped/(data_saved+data_skipped)*100) if (data_saved+data_skipped) > 0 else 0:.1f}%")
    
# #     if data_saved > 0:
# #         avg_hr = sum(hr_values) / len(hr_values)
# #         avg_rr = sum(rr_values) / len(rr_values)
# #         avg_range = sum(range_values) / len(range_values)
        
# #         print(f"\nAverage HR: {avg_hr:.1f} bpm")
# #         print(f"Average RR: {avg_rr:.1f} bpm")
# #         print(f"Average Range: {avg_range:.3f}m ({avg_range*100:.0f}cm)")
        
# #         if len(range_values) > 10:
# #             range_std = statistics.stdev(range_values)
# #             print(f"Range Std Dev: {range_std:.3f}m ({range_std*100:.0f}cm)")
        
# #         print(f"\n✓ Data appended to: {MASTER_CSV}")
    
# #     print("="*60)
    
# #     csv_file.close()
# #     user_ser.write(b'sensorStop\n')
# #     time.sleep(0.5)
# #     user_ser.close()
# #     data_ser.close()
    
# #     plt.ioff()
# #     plt.show()
# # import serial
# # import time
# # import struct
# # import csv
# # import datetime
# # import matplotlib
# # matplotlib.use("TkAgg")
# # import matplotlib.pyplot as plt
# # import statistics
# # import os
# # import sys

# # # -----------------------------
# # # Read command-line args
# # # -----------------------------
# # if len(sys.argv) >= 3:
# #     USER_EMAIL = sys.argv[1]
# #     try:
# #         CONFIG_FILE_NUMBER = int(sys.argv[2])
# #     except:
# #         CONFIG_FILE_NUMBER = 0
# # else:
# #     USER_EMAIL = "unknown_user"
# #     CONFIG_FILE_NUMBER = 0


# # # -----------------------------
# # # User Configurations
# # # -----------------------------
# # USER_PORT = 'COM5'
# # DATA_PORT = 'COM6'
# # USER_BAUD = 115200
# # DATA_BAUD = 921600

# # DURATION = 10  # seconds

# # CSV_DIR = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project\backend"
# # MASTER_CSV = f"{CSV_DIR}\\vital_signs_data.csv"

# # HR_CHANGE_THRESHOLD = 2.0
# # RR_CHANGE_THRESHOLD = 1.0
# # RANGE_CHANGE_THRESHOLD = 0.05

# # # -----------------------------
# # # Prepare CSV
# # # -----------------------------
# # file_exists = os.path.exists(MASTER_CSV)

# # csv_file = open(MASTER_CSV, "a", newline="")
# # csv_writer = csv.writer(csv_file)

# # if not file_exists:
# #     csv_writer.writerow([
# #         "Timestamp", "User", "SessionTime", "HeartRate_BPM", "RespirationRate_BPM", "Range_m",
# #         "HeartWaveform", "BreathWaveform", "HeartRate_FFT", "BreathRate_FFT", "ConfigurationFile"
# #     ])
# #     print(f"[OK] Created new file: {MASTER_CSV}")
# # else:
# #     print(f"[OK] Appending to existing file: {MASTER_CSV}")

# # print("="*60)
# # print("TI mmWave Radar Vital Signs Data Logger")
# # print("="*60)

# # # -----------------------------
# # # Connect & Initialize
# # # -----------------------------
# # print("\nConnecting to radar...")
# # user_ser = serial.Serial(USER_PORT, USER_BAUD, timeout=2)
# # data_ser = serial.Serial(DATA_PORT, DATA_BAUD, timeout=2)
# # time.sleep(1)

# # user_ser.reset_input_buffer()
# # data_ser.reset_input_buffer()

# # print("Stopping previous session...")
# # user_ser.write(b'sensorStop\n')
# # time.sleep(1)
# # user_ser.read(user_ser.in_waiting or 1)

# # # -----------------------------
# # # INLINE CONFIGURATION (NEW)
# # # -----------------------------
# # print("Sending configuration...")

# # CONFIG_COMMANDS = [
# #     "sensorStop",
# #     "flushCfg",
# #     "dfeDataOutputMode 1",
# #     "channelCfg 15 3 0",
# #     "adcCfg 2 1",
# #     "adcbufCfg -1 0 0 1 0",
# #     "profileCfg 0 60.25 7 6 57 0 0 65 1 200 4000 0 0 40",
# #     "chirpCfg 0 0 0 0 0 0 0 1",
# #     "frameCfg 0 0 2 0 50 1 0",
# #     "lowPower 0 1",
# #     "guiMonitor 0 0 0 0 1",
# #     "calibDcRangeSig -1 0 0 0 0",
# #     "vitalSignsCfg 0.3 0.9 256 512 4 0.1 0.05 100000 300000",
# #     "motionDetection 1 20 2.0 0",
# #     "sensorStart"
# # ]

# # for cmd in CONFIG_COMMANDS:
# #     user_ser.write((cmd + "\n").encode())
# #     time.sleep(0.05)

# # time.sleep(2)
# # print("Configuration sent. Starting collection...\n")

# # # -----------------------------
# # # Plotting
# # # -----------------------------
# # plt.ion()
# # fig, axes = plt.subplots(3, 1, figsize=(10, 8))
# # ax1, ax2, ax3 = axes

# # times, hr_values, rr_values, range_values = [], [], [], []

# # hr_line, = ax1.plot([], [], 'r-', linewidth=2)
# # ax1.set_ylabel("Heart Rate (BPM)")
# # ax1.set_ylim(40, 120)
# # ax1.grid(True, alpha=0.3)

# # rr_line, = ax2.plot([], [], 'b-', linewidth=2)
# # ax2.set_ylabel("Respiration Rate (BPM)")
# # ax2.set_ylim(5, 30)
# # ax2.grid(True, alpha=0.3)

# # range_line, = ax3.plot([], [], 'g-', linewidth=2)
# # ax3.set_xlabel("Time (s)")
# # ax3.set_ylabel("Range (m)")
# # ax3.set_ylim(0.3, 1.5)
# # ax3.grid(True, alpha=0.3)

# # plt.tight_layout()
# # plt.pause(0.001)

# # # -----------------------------
# # # Range Function
# # # -----------------------------
# # range_history = []
# # range_method_scores = {}
# # debug_sample_count = 0
# # best_range_method = None

# # def extract_range_multi_method(tlv_data):
# #     candidates = []
# #     for offset in range(64, min(128, len(tlv_data)), 4):
# #         try:
# #             val = struct.unpack_from('<f', tlv_data, offset)[0]
# #             if 0.2 < val < 2.5:
# #                 candidates.append(('float_scan', offset, val))
# #         except:
# #             pass

# #     try:
# #         range_idx = struct.unpack_from('<I', tlv_data, 4)[0]
# #         if 1 < range_idx < 100:
# #             for bin_size in [0.044, 0.04, 0.048, 0.05]:
# #                 val = range_idx * bin_size
# #                 if 0.2 < val < 2.5:
# #                     candidates.append(('range_idx', bin_size, val))
# #     except:
# #         pass

# #     specific_offsets = [64,68,72,76,80,84,88,92,96,100,104,108]
# #     for o in specific_offsets:
# #         try:
# #             val = struct.unpack_from('<f', tlv_data, o)[0]
# #             if 0.2 < val < 2.5:
# #                 candidates.append(('specific', o, val))
# #         except:
# #             pass

# #     return candidates

# # # -----------------------------
# # # Main Loop
# # # -----------------------------
# # start_time = time.time()
# # packet_count = 0
# # data_saved = 0
# # data_skipped = 0
# # last_valid_hr = None
# # last_valid_rr = None

# # last_saved_hr = None
# # last_saved_rr = None
# # last_saved_range = None

# # try:
# #     while time.time() - start_time < DURATION:
# #         byte = data_ser.read(1)
# #         if not byte or byte[0] != 0x02:
# #             continue

# #         rest = data_ser.read(7)
# #         if len(rest) < 7:
# #             continue

# #         sync = byte + rest
# #         if sync != b'\x02\x01\x04\x03\x06\x05\x08\x07':
# #             continue

# #         header = data_ser.read(32)
# #         if len(header) < 32:
# #             continue

# #         try:
# #             total_len = struct.unpack('<I', header[4:8])[0]
# #             frame_num = struct.unpack('<I', header[12:16])[0]

# #             if total_len < 40 or total_len > 65536:
# #                 continue

# #             payload_len = total_len - 40
# #             payload = data_ser.read(payload_len)
# #             if len(payload) < payload_len:
# #                 continue

# #             packet_count += 1
# #             ts = time.time() - start_time
# #             offset = 0

# #             while offset + 8 <= len(payload):
# #                 tlv_type, tlv_length = struct.unpack_from('<II', payload, offset)
# #                 offset += 8

# #                 if offset + tlv_length > len(payload):
# #                     break

# #                 if tlv_type == 6 and tlv_length >= 128:
# #                     tlv_data = payload[offset:offset+tlv_length]

# #                     # Extract waveforms & FFT HR/RR
# #                     breath_waveform = struct.unpack_from('<f', tlv_data, 28)[0]
# #                     heart_waveform = struct.unpack_from('<f', tlv_data, 32)[0]
# #                     heart_rate_fft = struct.unpack_from('<f', tlv_data, 36)[0]
# #                     breath_rate_fft = struct.unpack_from('<f', tlv_data, 52)[0]

# #                     # Get range candidates
# #                     range_candidates = extract_range_multi_method(tlv_data)

# #                     # Select best
# #                     range_m = range_candidates[0][2] if range_candidates else 0.6

# #                     # Smooth
# #                     range_history.append(range_m)
# #                     if len(range_history) > 9: range_history.pop(0)
# #                     smoothed_range = statistics.median(range_history) if len(range_history)>=5 else range_m

# #                     # HR/RR validation
# #                     hr = heart_rate_fft
# #                     rr = breath_rate_fft

# #                     if not (30 <= hr <= 200) and last_valid_hr is not None:
# #                         hr = last_valid_hr
# #                     if not (5 <= rr <= 50) and last_valid_rr is not None:
# #                         rr = last_valid_rr

# #                     last_valid_hr = hr
# #                     last_valid_rr = rr

# #                     # CHANGE DETECTION
# #                     save = False

# #                     if last_saved_hr is None:
# #                         save = True
# #                     else:
# #                         hr_changed = abs(hr - last_saved_hr) >= HR_CHANGE_THRESHOLD
# #                         rr_changed = abs(rr - last_saved_rr) >= RR_CHANGE_THRESHOLD
# #                         r_changed = abs(smoothed_range - last_saved_range) >= RANGE_CHANGE_THRESHOLD
# #                         save = hr_changed or rr_changed or r_changed

# #                     if save:
# #                         now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# #                         csv_writer.writerow([
# #                             now_ts,
# #                             USER_EMAIL,
# #                             f"{ts:.2f}",
# #                             f"{hr:.2f}",
# #                             f"{rr:.2f}",
# #                             f"{smoothed_range:.3f}",
# #                             f"{heart_waveform:.4f}",
# #                             f"{breath_waveform:.4f}",
# #                             f"{heart_rate_fft:.2f}",
# #                             f"{breath_rate_fft:.2f}",
# #                             CONFIG_FILE_NUMBER
# #                         ])
# #                         csv_file.flush()

# #                         data_saved += 1
# #                         last_saved_hr = hr
# #                         last_saved_rr = rr
# #                         last_saved_range = smoothed_range

# #                         print(f"[{ts:5.1f}s] [SAVED] HR: {hr:5.1f} | RR: {rr:4.1f} | Range: {smoothed_range:.3f}m")
# #                     else:
# #                         data_skipped += 1

# #                     # Plot
# #                     times.append(ts)
# #                     hr_values.append(hr)
# #                     rr_values.append(rr)
# #                     range_values.append(smoothed_range)

# #                     if len(times) > 100:
# #                         times = times[-100:]
# #                         hr_values = hr_values[-100:]
# #                         rr_values = rr_values[-100:]
# #                         range_values = range_values[-100:]

# #                     if (data_saved + data_skipped) % 10 == 0:
# #                         hr_line.set_data(times, hr_values)
# #                         rr_line.set_data(times, rr_values)
# #                         range_line.set_data(times, range_values)

# #                         if len(times) > 1:
# #                             ax1.set_xlim(times[0], times[-1] + 1)
# #                             ax2.set_xlim(times[0], times[-1] + 1)
# #                             ax3.set_xlim(times[0], times[-1] + 1)

# #                         plt.draw()
# #                         plt.pause(0.001)

# #                 offset += tlv_length

# #         except:
# #             pass

# # except KeyboardInterrupt:
# #     print("\nStopped manually")

# # finally:
# #     print("\n" + "="*60)
# #     print("SESSION SUMMARY")
# #     print("="*60)
# #     print(f"Packets: {packet_count} | Saved: {data_saved} | Skipped: {data_skipped}")

# #     csv_file.close()
# #     user_ser.write(b'sensorStop\n')
# #     time.sleep(0.5)
# #     user_ser.close()
# #     data_ser.close()

# #     plt.ioff()
# #     plt.show()
