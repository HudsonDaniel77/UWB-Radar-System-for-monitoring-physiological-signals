# vitalsigns.py  (Behind-Wall mode)
"""
Usage:
    python vitalsigns.py <user_email> <config_type>

- user_email: string (will be saved into CSV)
- config_type: 0 for front, 1 for back

Graph-paper style dashboard matching the normal vitalsigns.py.
Outputs STATS_BEGIN/STATS_END JSON with stats_text + waveform data.
"""

import serial, struct, time, sys, os, csv, datetime, statistics, json
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt, detrend
from matplotlib.ticker import MultipleLocator
import subprocess
import traceback

# ================= EMAIL FROM WEBSITE (REQUIRED) =================
if len(sys.argv) < 2:
    print("ERROR: Email ID not provided by backend")
    sys.exit(1)

USER_EMAIL = sys.argv[1]
try:
    CONFIG_TYPE = int(sys.argv[2]) if len(sys.argv) > 2 else 0
except:
    CONFIG_TYPE = 0

CONFIG_STR = "front" if CONFIG_TYPE == 0 else "back"

# ================= CONFIG =================
USER_PORT = "COM13"
DATA_PORT = "COM12"
USER_BAUD = 115200
DATA_BAUD = 921600

FRONT_CFG = r"C:\ti\mmwave_industrial_toolbox_4_12_1\labs\Vital_Signs\68xx_vital_signs\gui\profiles\xwr68xx_profile_VitalSigns_20fps_Front.cfg"
BACK_CFG  = r"C:\ti\mmwave_industrial_toolbox_4_12_1\labs\Vital_Signs\68xx_vital_signs\gui\profiles\xwr68xx_profile_VitalSigns_20fps_Front.cfg"
CFG_FILE = FRONT_CFG if CONFIG_TYPE == 0 else BACK_CFG

FPS = 20
RUN_TIME = 30
BUF_LEN = 200
MAGIC = b'\x02\x01\x04\x03\x06\x05\x08\x07'
UPSAMPLE = 8

# ================= CSV (MATCHING NORMAL VITALSIGNS FORMAT) =================
CSV_DIR = r"C:\Users\Nikhil\Downloads\SSN\College Files\Grand Project\RespirationHealth\gpp-project\backend"
os.makedirs(CSV_DIR, exist_ok=True)

MASTER_CSV = os.path.join(CSV_DIR, "vital_signs_data_new.csv")
file_exists = os.path.exists(MASTER_CSV)

csv_file = open(MASTER_CSV, "a", newline="")
csv_writer = csv.writer(csv_file)

if not file_exists:
    csv_writer.writerow([
        "Timestamp",
        "User",
        "Configuration",
        "SessionTime",
        "HeartRate_BPM",
        "RespirationRate_BPM",
        "Range_m",
        "HeartWaveform",
        "BreathWaveform",
        "HeartRate_FFT",
        "BreathRate_FFT",
        "ChestDisplacement",
        "CombinedSignal"
    ])
    csv_file.flush()

# Model script path
MODEL_SCRIPT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data_analysis", "predict_with_model.py")
)

# ================= HELPERS =================
def bandpass(sig, low, high, fs, order=4):
    if len(sig) < fs * 2:
        return sig
    b, a = butter(order, [low/(fs/2), high/(fs/2)], btype="band")
    return filtfilt(b, a, sig)

def smooth(x, w=5):
    if len(x) < w:
        return x
    return np.convolve(x, np.ones(w)/w, mode="same")

def densify(x):
    if len(x) < 4:
        return x
    t = np.arange(len(x))
    ti = np.linspace(0, len(x)-1, len(x)*UPSAMPLE)
    return np.interp(ti, t, x)

def autoscale(ax, y):
    if len(y) > 10:
        m = np.max(np.abs(y))
        if m > 0:
            ax.set_ylim(-1.2*m, 1.2*m)

def normalize(x):
    s = np.std(x)
    return x if s == 0 else x/s

def extract_range_m(tlv):
    for offset in range(64, min(128, len(tlv)), 4):
        try:
            val = struct.unpack_from("<f", tlv, offset)[0]
            if 0.2 < val < 3.0:
                return val
        except:
            pass
    return None

# ================= SERIAL =================
print("=" * 60)
print("RADAR VITAL SIGNS COLLECTION (Behind-Wall Mode)")
print("User: {} | Configuration: {} ({})".format(USER_EMAIL, CONFIG_STR, CONFIG_TYPE))
print("CFG file: {}".format(CFG_FILE))
print("=" * 60)

user_ser = serial.Serial(USER_PORT, USER_BAUD, timeout=2)
data_ser = serial.Serial(DATA_PORT, DATA_BAUD, timeout=0)

time.sleep(1)
user_ser.write(b"sensorStop\n")
time.sleep(0.5)

with open(CFG_FILE) as f:
    for l in f:
        if l.strip() and not l.startswith("%"):
            user_ser.write((l.strip()+"\n").encode())
            time.sleep(0.03)

user_ser.write(b"sensorStart\n")
print("Radar started | User:", USER_EMAIL)

# ================= BUFFERS =================
rx = bytearray()
raw_phase, heart_phase, breath_phase = [], [], []
hr_vals, rr_vals = [], []

# ================= FINAL STATS =================
final_hr, final_rr, final_range = [], [], []
last_valid_hr = last_valid_rr = None
last_saved_hr = last_saved_rr = last_saved_range = None

HR_TH, RR_TH, R_TH = 2.0, 1.0, 0.05
range_history = []

# ================= FIGURE (GRAPH-PAPER STYLE — SAME AS NORMAL) =================
plt.ion()
fig, axs = plt.subplots(2, 2, figsize=(14, 10), sharex=True)
fig.patch.set_facecolor("black")

ax_hr, ax_rr = axs[0]
ax_disp, ax_comb = axs[1]

l_hr, = ax_hr.plot([], [], 'r', lw=2.5)
l_rr, = ax_rr.plot([], [], 'c', lw=2.5)
l_disp, = ax_disp.plot([], [], 'g', lw=2.5)
l_comb, = ax_comb.plot([], [], 'm', lw=2.5)

for ax in axs.flat:
    ax.set_facecolor("white")
    ax.set_xlim(0, BUF_LEN*UPSAMPLE)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.xaxis.set_major_locator(MultipleLocator(200))
    ax.yaxis.set_major_locator(MultipleLocator(0.5))
    ax.grid(which="major", color="#4a90e2", linewidth=0.8)
    ax.xaxis.set_minor_locator(MultipleLocator(40))
    ax.yaxis.set_minor_locator(MultipleLocator(0.1))
    ax.grid(which="minor", color="#9ec9ff", linewidth=0.5)
    for s in ax.spines.values():
        s.set_color("black")
        s.set_linewidth(1.5)

def panel_title(ax, txt):
    ax.text(0.5, 1.12, txt, transform=ax.transAxes,
            ha="center", va="bottom", fontsize=14, fontweight="bold",
            bbox=dict(facecolor="white", edgecolor="black", boxstyle="round,pad=0.35"),
            clip_on=False)

panel_title(ax_hr, "HEART MOTION")
panel_title(ax_rr, "RESPIRATION MOTION")
panel_title(ax_disp, "CHEST DISPLACEMENT")
panel_title(ax_comb, "COMBINED CHEST SIGNAL")

fig.suptitle("MMWAVE VITAL SIGNS \u2013 BEHIND WALL DASHBOARD",
             fontsize=18, fontweight="bold", color="white", y=0.975)

fig.lines.append(plt.Line2D([0.1, 0.9], [0.925, 0.925], color="white", linewidth=1.2))

hr_txt = fig.text(0.42, 0.885, "HR: -- BPM",
                  ha="center", fontsize=16, fontweight="bold",
                  color="white",
                  bbox=dict(facecolor="black", edgecolor="white", boxstyle="round,pad=0.55"))

rr_txt = fig.text(0.58, 0.885, "RR: -- BPM",
                  ha="center", fontsize=16, fontweight="bold",
                  color="white",
                  bbox=dict(facecolor="black", edgecolor="white", boxstyle="round,pad=0.55"))

plt.subplots_adjust(top=0.76, hspace=0.55, wspace=0.22)

# ================= MAIN LOOP =================
start = time.time()

# Initialize waveform arrays for final output
heart_wave = np.array([])
breath_wave = np.array([])
chest_wave = np.array([])
combined = np.array([])

while time.time() - start < RUN_TIME:
    rx.extend(data_ser.read(4096))

    while True:
        i = rx.find(MAGIC)
        if i < 0 or len(rx) < i + 40:
            break

        plen = struct.unpack("<I", rx[i+12:i+16])[0]
        if len(rx) < i + plen:
            break

        pkt = rx[i:i+plen]
        rx = rx[i+plen:]
        pay = pkt[40:]

        off = 0
        while off + 8 <= len(pay):
            t, l = struct.unpack_from("<II", pay, off)
            off += 8

            if t == 6:
                bp = struct.unpack_from("<f", pay, off+28)[0]
                hp = struct.unpack_from("<f", pay, off+32)[0]
                hr = struct.unpack_from("<f", pay, off+36)[0]
                rr = struct.unpack_from("<f", pay, off+52)[0]

                range_m = extract_range_m(pay[off:off+l])
                if range_m is not None:
                    range_history.append(range_m)
                    if len(range_history) > 9:
                        range_history.pop(0)
                    range_sm = statistics.median(range_history)
                else:
                    range_sm = last_saved_range

                if not (30 <= hr <= 200) and last_valid_hr is not None:
                    hr = last_valid_hr
                if not (5 <= rr <= 50) and last_valid_rr is not None:
                    rr = last_valid_rr

                last_valid_hr, last_valid_rr = hr, rr

                # ================= FINAL STATS COLLECTION =================
                include = False

                if last_saved_hr is None and (30 <= hr <= 200) and (5 <= rr <= 50):
                    include = True
                else:
                    if last_saved_hr is not None:
                        if abs(hr - last_saved_hr) >= HR_TH:
                            include = True
                        if abs(rr - last_saved_rr) >= RR_TH:
                            include = True
                        if range_sm is not None and last_saved_range is not None:
                            if abs(range_sm - last_saved_range) >= R_TH:
                                include = True

                if include:
                    final_hr.append(hr)
                    final_rr.append(rr)
                    if range_sm is not None:
                        final_range.append(range_sm)

                    last_saved_hr = hr
                    last_saved_rr = rr
                    last_saved_range = range_sm

                raw_phase.append(bp)
                heart_phase.append(hp)
                breath_phase.append(bp)
                hr_vals.append(hr)
                rr_vals.append(rr)

                raw_phase[:] = raw_phase[-BUF_LEN:]
                heart_phase[:] = heart_phase[-BUF_LEN:]
                breath_phase[:] = breath_phase[-BUF_LEN:]

                chest = smooth(detrend(np.cumsum(np.diff(
                    np.unwrap(breath_phase), prepend=breath_phase[0]
                ))))
                chest_wave = bandpass(chest, 0.05, 0.8, FPS)

                heart = smooth(detrend(np.cumsum(np.diff(
                    np.unwrap(heart_phase), prepend=heart_phase[0]
                ))))
                heart_wave = bandpass(heart, 0.8, 2.0, FPS)
                breath_wave = bandpass(chest, 0.1, 0.5, FPS)
                raw_sig = smooth(detrend(np.unwrap(raw_phase)))

                combined = (
                    0.3*normalize(chest_wave) +
                    0.3*normalize(breath_wave) +
                    0.25*normalize(heart_wave) +
                    0.15*normalize(raw_sig)
                )

                l_hr.set_data(range(len(densify(heart_wave))), densify(heart_wave))
                l_rr.set_data(range(len(densify(breath_wave))), densify(breath_wave))
                l_disp.set_data(range(len(densify(chest_wave))), densify(chest_wave))
                l_comb.set_data(range(len(densify(combined))), densify(combined))

                autoscale(ax_hr, heart_wave)
                autoscale(ax_rr, breath_wave)
                autoscale(ax_disp, chest_wave)
                autoscale(ax_comb, combined)

                hr_txt.set_text(f"HR: {np.mean(hr_vals[-10:]):.1f} BPM")
                rr_txt.set_text(f"RR: {np.mean(rr_vals[-10:]):.1f} BPM")

                # ================= SAVE EVERY FRAME =================
                now = time.time()

                csv_writer.writerow([
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                    USER_EMAIL,
                    CONFIG_TYPE,
                    f"{now - start:.3f}",
                    f"{hr:.2f}",
                    f"{rr:.2f}",
                    f"{range_sm:.3f}" if range_sm is not None else "",
                    f"{heart_wave[-1]:.4f}" if len(heart_wave) else "",
                    f"{breath_wave[-1]:.4f}" if len(breath_wave) else "",
                    f"{hr:.2f}",
                    f"{rr:.2f}",
                    f"{chest_wave[-1]:.4f}" if len(chest_wave) else "",
                    f"{combined[-1]:.4f}" if len(combined) else ""
                ])

                csv_file.flush()
                plt.pause(0.001)

            off += l

# ================= SEND FINAL STATS TO FRONTEND =================
stats_lines = []

if final_hr:
    avg_hr = sum(final_hr) / len(final_hr)
    avg_rr = sum(final_rr) / len(final_rr)

    stats_lines.append(f"Average Heart Rate  : {avg_hr:.1f} bpm")
    stats_lines.append(f"Average Resp Rate   : {avg_rr:.1f} bpm")

    if len(final_range) > 0:
        avg_r = sum(final_range) / len(final_range)
        stats_lines.append(f"Average Distance    : {avg_r:.3f} m ({avg_r*100:.0f} cm)")

        if len(final_range) > 1:
            sd = statistics.stdev(final_range)
            stats_lines.append(f"Distance Std Dev    : {sd:.3f} m ({sd*100:.0f} cm)")
else:
    stats_lines.append("No valid HR/RR frames were saved.")

stats_text = "VITAL SIGNS SUMMARY (Behind-Wall)\n" + "-" * 40 + "\n" + "\n".join(stats_lines)

# ================= WAVEFORM DATA FOR WEB EMBEDDING =================
waveform_data = {}
try:
    if len(heart_wave) > 0:
        waveform_data["heart"] = densify(heart_wave).tolist()
    if len(breath_wave) > 0:
        waveform_data["respiration"] = densify(breath_wave).tolist()
    if len(chest_wave) > 0:
        waveform_data["chest"] = densify(chest_wave).tolist()
    if len(combined) > 0:
        waveform_data["combined"] = densify(combined).tolist()
    waveform_data["hr_text"] = f"{np.mean(hr_vals[-10:]):.1f}" if hr_vals else "--"
    waveform_data["rr_text"] = f"{np.mean(rr_vals[-10:]):.1f}" if rr_vals else "--"
except Exception:
    pass

print("STATS_BEGIN")
print(json.dumps({"stats_text": stats_text, "waveform": waveform_data}))
print("STATS_END")

# ================= ML MODEL (optional) =================
ml_summary = None
try:
    if os.path.exists(MODEL_SCRIPT):
        print("\nRunning ML model for classification...")
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
    else:
        print("\nModel script not found at:", MODEL_SCRIPT)
except Exception:
    print("\nError running model script:")
    print(traceback.format_exc())

if ml_summary:
    print("\nML ANALYSIS SUMMARY")
    print("-" * 40)
    try:
        get = ml_summary.get
        print("Predicted_HR  :", get('Predicted_HR', get('predicted_hr', 'N/A')))
        print("HR_Class      :", get('HR_Class', get('hr_class', 'N/A')))
        print("RR_Class      :", get('RR_Class', get('rr_class', 'N/A')))
        print("Stress_Class  :", get('Stress_Class', get('stress_class', 'N/A')))
    except Exception:
        print(ml_summary)

# ================= CLEANUP =================
user_ser.write(b"sensorStop\n")
user_ser.close()
data_ser.close()
csv_file.close()
plt.ioff()
plt.show()

print("\nCSV saved to:", MASTER_CSV)
print("Done.")
