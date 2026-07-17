# RespirationHealth - IWR6843 Vital Signs Radar Demo

A complete web-based application for real-time vital signs monitoring using TI's IWR6843 mmWave radar.

## ✅ Quick Start

### Easiest Way (Windows)
**Double-click one of these:**
- `START_DEMO.bat` — Batch file (most reliable)
- `START_DEMO.ps1` — PowerShell script

That's it! Both the backend and frontend will start automatically, and your browser will open.

### Manual Start
**Terminal 1 (Backend):**
```bash
cd backend
py app_demo.py
```

**Terminal 2 (Frontend):**
```bash
cd frontend
npm install
npm run dev
```

Then visit `http://localhost:5173`

## 📋 What This Does

- **Real-time vital signs** — Heart rate, respiration rate captured from radar
- **Live waveforms** — Heart and respiration waveforms at 20 FPS
- **Frequency spectrum** — FFT analysis of vital signals
- **Range detection** — Distance to detected person(s)
- **Web dashboard** — Beautiful React UI with real-time charts

## 🎯 Features

✓ Start/Stop sensor remotely via web UI  
✓ WebSocket real-time data streaming  
✓ Interactive charts (Chart.js)  
✓ Demo mode (works without hardware)  
✓ Hardware mode (with IWR6843 + COM ports)  
✓ CSV logging of all sessions  

## 📁 Project Structure

```
├── backend/
│   ├── app.py              ← Real hardware version
│   ├── app_demo.py         ← Demo mode (no hardware needed) ✓ USE THIS
│   ├── radar_client.py     ← Serial communication
│   ├── dsp.py              ← Signal processing
│   ├── xwr68xx_profile.cfg ← Radar config
│   └── requirements.txt    ← Python deps
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx         ← Main React component
│   │   ├── index.css       ← Styling
│   │   └── main.jsx
│   ├── package.json
│   ├── vite.config.js
│   └── index.html
│
├── START_DEMO.bat          ← One-click startup (Windows)
├── START_DEMO.ps1          ← PowerShell startup
├── QUICKSTART.md           ← Detailed setup guide
└── README.md               ← This file
```

## 🔧 What's Different

### Demo Mode (app_demo.py) ✓ Recommended
- Generates synthetic but realistic vital signs
- **No hardware required**
- Streaming runs at 20 FPS
- Perfect for UI testing and demos
- Shows how the real version works

### Hardware Mode (app.py)
- Requires TI IWR6843AOP radar + evaluation board
- Communicates via COM10 (data) and COM11 (config)
- Uses serial protocol for radar communication
- Real vital signs from passive radar

## 📊 Expected Data

When running, you'll see:
- **Heart Rate:** 60-100 BPM
- **Respiration Rate:** 12-20 BPM
- **Distance:** 0.3-1.5 meters
- **Waveforms:** Real-time traces
- **FFT Spectrum:** Frequency analysis

## ⚠️ Troubleshooting

**Button doesn't work?**
1. Check browser console (F12 → Console tab)
2. Verify backend is running (should see "Ready on 127.0.0.1:6666")
3. Refresh page (Ctrl+R)
4. Check that both terminals are open and showing no errors

**"Connection refused"?**
- Backend not running — start it first with `py app_demo.py`
- Wrong port — verify backend is on 6666

**"Seeking Radar..." but no data?**
- In demo mode: Normal! Backend still generates data
- In hardware mode: Check COM ports and radar connection

**Frontend won't start?**
```bash
cd frontend
npm install
npm run dev
```

## 📝 How It Works

1. **Frontend** (React) connects to backend via WebSocket on port 6666
2. **Backend** (Flask + SocketIO) opens serial connection to radar (or generates demo data)
3. **Radar thread** continuously reads vital signs and emits via WebSocket
4. **Dashboard** receives real-time updates and renders charts

## 🚀 Next Steps

### Try the Demo
Run `START_DEMO.bat` and play with the UI.

### Test with Real Hardware
1. Connect IWR6843 evaluation board via USB
2. Check COM ports in Device Manager
3. Update COM10/COM11 in `backend/app.py` if needed
4. Run `py app.py` instead of `app_demo.py`

### Customize
- Edit frontend colors in `frontend/src/index.css`
- Modify radar config in `backend/xwr68xx_profile.cfg`
- Adjust demo data generation in `backend/app_demo.py`

## 📚 Documentation Files
- **QUICKSTART.md** — Step-by-step setup guide
- **PROJECT_STATUS_DETAILED.md** — Technical details
- **PROJECT_SUMMARY_QUICK.md** — Overview

## 📄 License & Attribution
TI IWR6843 radar code based on TI mmWave lab examples.

---
**Ready to start?** → Run `START_DEMO.bat` 🚀
