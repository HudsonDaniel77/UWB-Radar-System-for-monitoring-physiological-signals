import serial, struct, time, sys, os, csv, datetime, statistics, json
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt, detrend
from matplotlib.ticker import MultipleLocator

# ================= EMAIL FROM WEBSITE (REQUIRED) =================
if len(sys.argv) < 2:
    print("ERROR: Email ID not provided by backend")
    sys.exit(1)

USER_EMAIL = sys.argv[1]
CONFIG_TYPE = int(sys.argv[2]) if len(sys.argv) > 2 else 0
RUN_TIME    = int(sys.argv[3]) if len(sys.argv) > 3 else 30  # seconds; override via argv[3]

# ================= CONFIG =================
USER_PORT = "COM13"
DATA_PORT = "COM12"
USER_BAUD = 115200
DATA_BAUD = 921600

# Use the CFG profiles bundled inside the project's labs folder.
# Falls back to the TI toolbox installation if the project copy is missing.
_SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))
CFG_BASE = os.path.join(
    _PROJECT_ROOT, "labs", "Vital_Signs",
    "68xx_vital_signs", "gui", "profiles"
)
if not os.path.isdir(CFG_BASE):          # fallback to TI installation in Downloads
    CFG_BASE = r"C:\ti\mmwave_industrial_toolbox_4_12_1\labs\Vital_Signs\68xx_vital_signs\gui\profiles"

CFG_FILES = {
    0: os.path.join(CFG_BASE, "xwr68xx_profile_VitalSigns_20fps_Front.cfg"),
    1: os.path.join(CFG_BASE, "xwr68xx_profile_VitalSigns_20fps_Back.cfg"),
}
CFG_FILE = CFG_FILES.get(CONFIG_TYPE, CFG_FILES[0])

FPS = 20
BUF_LEN = 200
MAGIC = b'\x02\x01\x04\x03\x06\x05\x08\x07'
UPSAMPLE = 8

# ================= CSV (SESSION FILE — new file per run) =================
CSV_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(CSV_DIR, exist_ok=True)

# Each run gets its own timestamped file so analysis only sees THIS session's data
SESSION_TS = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
SESSION_CSV = os.path.join(CSV_DIR, f"vital_signs_session_{SESSION_TS}.csv")

csv_file = open(SESSION_CSV, "w", newline="")
csv_writer = csv.writer(csv_file)
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

SAVE_INTERVAL = 0.0
last_save_time = 0

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
    # scan for float range values (TI Vital Signs compatible)
    for offset in range(64, min(128, len(tlv)), 4):
        try:
            val = struct.unpack_from("<f", tlv, offset)[0]
            if 0.2 < val < 3.0:
                return val
        except:
            pass
    return None


# ================= SERIAL =================
try:
    if not os.path.isfile(CFG_FILE):
        print(f"ERROR: Config file not found: {CFG_FILE}", file=sys.stderr)
        csv_file.close()
        sys.exit(1)

    user = serial.Serial(USER_PORT, USER_BAUD, timeout=2)
    data = serial.Serial(DATA_PORT, DATA_BAUD, timeout=0)
except serial.SerialException as e:
    print(f"ERROR: Could not open serial port - {e}", file=sys.stderr)
    print(f"  Make sure the radar is connected and {USER_PORT}/{DATA_PORT} are correct.", file=sys.stderr)
    csv_file.close()
    sys.exit(1)
except Exception as e:
    print(f"ERROR: Serial setup failed - {e}", file=sys.stderr)
    csv_file.close()
    sys.exit(1)

time.sleep(1)
user.write(b"sensorStop\n")
time.sleep(0.5)

with open(CFG_FILE) as f:
    for l in f:
        if l.strip() and not l.startswith("%"):
            user.write((l.strip()+"\n").encode())
            time.sleep(0.03)

user.write(b"sensorStart\n")
print("Radar started | User:", USER_EMAIL)

# ================= BUFFERS =================
rx = bytearray()
raw_phase, heart_phase, breath_phase = [], [], []
hr_vals, rr_vals = [], []

# ================= FINAL STATS (OLD CODE LOGIC) =================
final_hr, final_rr, final_range = [], [], []
last_valid_hr = last_valid_rr = None
last_saved_hr = last_saved_rr = last_saved_range = None

HR_TH, RR_TH, R_TH = 2.0, 1.0, 0.05
range_history = []

# ================= FIGURE (DO NOT TOUCH) =================
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

fig.suptitle("MMWAVE VITAL SIGNS – GRAPH PAPER DASHBOARD",
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

while time.time() - start < RUN_TIME:
    rx.extend(data.read(4096))

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

                # Force first valid frame
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

def dealias_hr_list(hr_list):
    if not hr_list:
        return hr_list
    arr = np.array(hr_list, dtype=float)
    low_c = arr[(arr >= 50) & (arr <= 95)]
    high_c = arr[(arr >= 115) & (arr <= 150)]
    if len(low_c) > 0 and len(high_c) > 0:
        arr[(arr >= 115) & (arr <= 150)] /= 2.0
    elif len(high_c) == len(arr):
        arr /= 2.0
    return arr.tolist()

if final_hr:
    clean_final_hr = dealias_hr_list(final_hr)
    avg_hr = sum(clean_final_hr) / len(clean_final_hr)
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

stats_text = "VITAL SIGNS SUMMARY\n" + "-" * 40 + "\n" + "\n".join(stats_lines)

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

    dealiased_hr_vals = dealias_hr_list(hr_vals)
    waveform_data["hr_text"] = f"{np.mean(dealiased_hr_vals[-10:]):.1f}" if dealiased_hr_vals else "--"
    waveform_data["rr_text"] = f"{np.mean(rr_vals[-10:]):.1f}" if rr_vals else "--"
    
    # Add vital signs arrays and timestamps for live graphing (the graphpaper chart)
    if len(hr_vals) > 0:
        waveform_data["hr_vals"] = dealiased_hr_vals
        waveform_data["rr_vals"] = rr_vals
        # Generate timestamps based on FPS (assume ~1.68 Hz actual sampling)
        timestamps = [i / FPS for i in range(len(hr_vals))]
        waveform_data["timestamps"] = timestamps
except Exception:
    pass

print("STATS_BEGIN")
print(json.dumps({"stats_text": stats_text, "waveform": waveform_data}))
print("STATS_END")


# ================= CLEANUP =================
user.write(b"sensorStop\n")
user.close()
data.close()
csv_file.close()
plt.ioff()
try:
    plt.close('all')
except Exception:
    pass

print("\nCSV saved to:", SESSION_CSV)

# Print session CSV path so the calling process (sleep_api.py) can pick it up
print("CSV_PATH_BEGIN")
print(SESSION_CSV)
print("CSV_PATH_END")

print("Done.")
