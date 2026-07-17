# RespirationHealth-Feature-Radar: Complete Setup Guide

## Error You're Seeing
```
Failed to connect to backend. Is app_demo.py running on port 6666?
```

**Translation:** The frontend can't reach the backend. The backend service isn't running.

---

## SOLUTION #1: ONE-CLICK START (EASIEST)

Double-click: **`START_DEMO.bat`**

This automatically starts everything. Done!

**If that doesn't work, use Solution #2:**

---

## SOLUTION #2: MANUAL STARTUP (RELIABLE)

### Step 1: Open First Terminal Window
- Press `Windows Key` + `R`
- Type: `cmd`
- Press `Enter`

### Step 2: Navigate and Start Backend
Copy-paste this entire block into Terminal 1:

```
cd RespirationHealth-feature-radar\RespirationHealth-feature-radar\backend
py app_demo.py
```

Press `Enter`.

**Expected output:**
```
============================================================
🚀 DEMO MODE - RespirationHealth Backend
============================================================
Ready on http://127.0.0.1:6666
Generating synthetic vital signs data...
============================================================
```

✅ **If you see this, backend is RUNNING. Leave this terminal open.**

### Step 3: Open Second Terminal Window
- Press `Windows Key` + `R`
- Type: `cmd`
- Press `Enter`

### Step 4: Navigate and Start Frontend
Copy-paste this into Terminal 2:

```
cd RespirationHealth-feature-radar\RespirationHealth-feature-radar\frontend
npm run dev
```

Press `Enter`.

**Expected output:**
```
➜  Local:   http://localhost:5173/
```

✅ **If you see this, frontend is RUNNING.**

### Step 5: Open Browser
- Your browser should auto-open to `http://localhost:5173`
- If not, manually go to: `http://localhost:5173`

### Step 6: Click START SENSOR Button
Now it should work! ✅

---

## TROUBLESHOOTING

### Problem: Terminal closes immediately after running the command

**Solution:**
1. Don't just double-click the file
2. Open `cmd` manually first
3. Copy-paste the command line by line
4. Check for error messages

### Problem: "ModuleNotFoundError: No module named 'flask'"

**Solution:**
Run this in the terminal:
```
py -m pip install flask flask-cors flask-socketio pyserial numpy scipy requests
```

Then run `py app_demo.py` again.

### Problem: "Port 6666 already in use"

**Solution:**
Run this to find what's using port 6666:
```
netstat -ano | findstr :6666
```

Then kill it:
```
taskkill /PID <the_number_shown> /F
```

Then try `py app_demo.py` again.

### Problem: "npm: command not found"

**Solution:**
- Download Node.js from https://nodejs.org/
- Install it
- Open a new terminal and try again

### Problem: Frontend runs but still says "Seeking Radar..."

**Solution:**
1. Open browser DevTools (F12)
2. Go to Console tab
3. Check for error messages
4. Refresh page (Ctrl+R)
5. Try clicking START SENSOR again

Check that Terminal 1 (backend) is STILL running and showing "Ready on http://127.0.0.1:6666"

### Problem: Only one terminal is running but not both

**Solution:**
You MUST have:
1. Terminal 1 running `py app_demo.py` (backend)
2. Terminal 2 running `npm run dev` (frontend)

Both must be running simultaneously.

---

## QUICK CHECKLIST

Before clicking START SENSOR, verify:

- [ ] Terminal 1 is open and running (shows "Ready on http://127.0.0.1:6666")
- [ ] Terminal 2 is open and running (shows "http://localhost:5173")
- [ ] Browser is open at http://localhost:5173
- [ ] Browser console shows no red errors (F12 → Console tab)
- [ ] START SENSOR button is visible and clickable

---

## FILES IN THIS FOLDER

| File | Purpose |
|------|---------|
| `START_DEMO.bat` | One-click startup (Windows) |
| `START_DEMO.ps1` | One-click startup (PowerShell) |
| `CHECK_BACKEND.bat` | Check if backend is running |
| `TROUBLESHOOT_BUTTON.txt` | Button troubleshooting guide |
| `QUICKSTART.md` | Quick start reference |
| `README_DEMO.md` | Full feature overview |
| `backend/app_demo.py` | Demo backend (no hardware needed) |
| `frontend/src/App.jsx` | React frontend |

---

## WHAT'S HAPPENING

**Backend (app_demo.py)**
- Generates fake vital signs data
- Listens on http://127.0.0.1:6666
- Sends data via WebSocket at 20 FPS

**Frontend (React + Vite)**
- Runs at http://localhost:5173
- Connects to backend
- Shows real-time charts

**Your Button**
- Sends POST request to `http://127.0.0.1:6666/start`
- Backend must be running for this to work

---

## GETTING HELP

If stuck:

1. **Check Terminal 1** for error messages
2. **Open browser console** (F12) for errors
3. **Run CHECK_BACKEND.bat** to diagnose
4. **Read TROUBLESHOOT_BUTTON.txt** for common issues
5. Take a screenshot of the error and share it

---

**Ready?**
→ Double-click `START_DEMO.bat` or follow Solution #2

Good luck! 🚀
