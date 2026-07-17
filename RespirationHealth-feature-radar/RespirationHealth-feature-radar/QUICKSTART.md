# RespirationHealth Demo - Quick Start Guide

## What You Get
A fully functional demo of the RespirationHealth application with **synthetic vital signs data** (no hardware required).

## Quickest Way to Start (One-Click)

**Double-click:** `START_DEMO.bat`

This automatically:
- Starts the backend (app_demo.py) in Terminal 1
- Starts the frontend (npm run dev) in Terminal 2  
- Opens your browser at http://localhost:5173
- Ready to use!

---

## Manual Setup & Run

### Terminal 1: Start Backend (Demo Mode)
```powershell
cd "RespirationHealth-feature-radar\RespirationHealth-feature-radar\backend"
py app_demo.py
```

You should see:
```
============================================================
🚀 DEMO MODE - RespirationHealth Backend
============================================================
Ready on http://127.0.0.1:6666
Generating synthetic vital signs data...
============================================================
```

### Terminal 2: Start Frontend
```powershell
cd "RespirationHealth-feature-radar\RespirationHealth-feature-radar\frontend"
npm install
npm run dev
```

You should see something like:
```
  ➜  Local:   http://localhost:5173/
```

### Step 3: Open in Browser
Visit `http://localhost:5173` in your web browser.

### Step 4: Interact with the App
1. Click the **START SENSOR** button
2. Watch real-time vital signs data stream in:
   - Heart Rate (60-100 BPM)
   - Respiration Rate (12-20 BPM)
   - Waveforms and FFT spectrum
   - Range profile
3. Click **STOP SENSOR** to pause

## What's Happening Behind the Scenes

**Backend (app_demo.py):**
- Generates realistic fake vital signs data
- Streams it via WebSocket (Socket.IO) at 20 FPS
- Simulates /start and /stop API endpoints
- Logs data to CSV file

**Frontend (React + Vite):**
- Connects to backend on port 6666
- Displays real-time charts using Chart.js
- Updates UI as data streams in

## To Switch to Real Hardware Later
Replace `app_demo.py` with the original `app.py` and:
1. Verify your radar is connected (COM10/COM11 ports)
2. Check/update ports in app.py if needed
3. Run `py app.py` instead

## Troubleshooting

**Button is greyed out / disabled?**
- Backend not running? Check Terminal 1
- Run: `py app_demo.py` in the backend folder

**"Connection refused"?**
- Backend not running? Start it first in Terminal 1
- Wrong port? Check app is on 6666

**Window shows "Seeking Radar..."?**
- Normal in demo mode (backend still generates data)
- In real hardware, this means radar connection issue

**Button doesn't work after clicking?**
- Open browser DevTools (F12) → Console tab
- Check for error messages
- Verify both backend and frontend terminals show no errors
- Refresh the page (Ctrl+R) and try again

---
**Last Updated:** March 25, 2026

