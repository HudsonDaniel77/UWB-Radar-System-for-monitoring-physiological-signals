import serial, struct, time
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt, detrend
from matplotlib.ticker import MultipleLocator

# ================= CONFIG =================
USER_PORT = "COM5"
DATA_PORT = "COM6"
USER_BAUD = 115200
DATA_BAUD = 921600

CFG_FILE = r"C:\ti\mmwave_industrial_toolbox_4_12_1\labs\Vital_Signs\68xx_vital_signs\gui\profiles\xwr68xx_profile_VitalSigns_20fps_Front.cfg"

FPS = 20
RUN_TIME = 30
BUF_LEN = 200
MAGIC = b'\x02\x01\x04\x03\x06\x05\x08\x07'
UPSAMPLE = 8

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

# ================= SERIAL =================
user = serial.Serial(USER_PORT, USER_BAUD, timeout=2)
data = serial.Serial(DATA_PORT, DATA_BAUD, timeout=0)

time.sleep(1)
user.write(b"sensorStop\n")
time.sleep(0.5)

with open(CFG_FILE) as f:
    for l in f:
        if l.strip() and not l.startswith("%"):
            user.write((l.strip()+"\n").encode())
            time.sleep(0.03)

user.write(b"sensorStart\n")
print("Radar started")

# ================= BUFFERS =================
rx = bytearray()
raw_phase, heart_phase, breath_phase = [], [], []
hr_vals, rr_vals = [], []

# ================= FIGURE =================
plt.ion()
fig, axs = plt.subplots(2, 2, figsize=(14, 10), sharex=True)
fig.patch.set_facecolor("black")

ax_hr, ax_rr = axs[0]
ax_disp, ax_comb = axs[1]

# ================= PLOTS =================
l_hr,   = ax_hr.plot([], [], 'r', lw=2.5)
l_rr,   = ax_rr.plot([], [], 'c', lw=2.5)
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

# ================= PANEL TITLES =================
def panel_title(ax, txt):
    ax.text(
        0.5, 1.12, txt,
        transform=ax.transAxes,
        ha="center", va="bottom",
        fontsize=14, fontweight="bold",
        bbox=dict(facecolor="white", edgecolor="black", boxstyle="round,pad=0.35"),
        clip_on=False
    )

panel_title(ax_hr, "HEART MOTION")
panel_title(ax_rr, "RESPIRATION MOTION")
panel_title(ax_disp, "CHEST DISPLACEMENT")
panel_title(ax_comb, "COMBINED CHEST SIGNAL")

# ================= PAGE TITLE =================
fig.suptitle(
    "MMWAVE VITAL SIGNS – GRAPH PAPER DASHBOARD",
    fontsize=18,
    fontweight="bold",
    color="white",
    y=0.975
)

# -------- VISUAL SEPARATOR (LOWERED) --------
fig.lines.append(
    plt.Line2D([0.1, 0.9], [0.925, 0.925], color="white", linewidth=1.2)
)

# ================= HR / RR (MORE GAP, SAME LINE) =================
hr_txt = fig.text(
    0.42, 0.885, "HR: -- BPM",
    ha="center", fontsize=16, fontweight="bold",
    color="white",
    bbox=dict(facecolor="black", edgecolor="white", boxstyle="round,pad=0.55")
)

rr_txt = fig.text(
    0.58, 0.885, "RR: -- BPM",
    ha="center", fontsize=16, fontweight="bold",
    color="white",
    bbox=dict(facecolor="black", edgecolor="white", boxstyle="round,pad=0.55")
)

# ================= SPACING =================
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

                raw_phase.append(bp)
                heart_phase.append(hp)
                breath_phase.append(bp)
                hr_vals.append(hr)
                rr_vals.append(rr)

                raw_phase[:] = raw_phase[-BUF_LEN:]
                heart_phase[:] = heart_phase[-BUF_LEN:]
                breath_phase[:] = breath_phase[-BUF_LEN:]
                hr_vals[:] = hr_vals[-BUF_LEN:]
                rr_vals[:] = rr_vals[-BUF_LEN:]

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

                plt.pause(0.001)

            off += l

# ================= CLEANUP =================
user.write(b"sensorStop\n")
user.close()
data.close()
plt.ioff()
plt.show()
