@echo off
setlocal enabledelayedexpansion
title Respiration Health Launcher
color 0B

set "PROJECT_ROOT=%~dp0"

:MENU
cls
echo ====================================================================
echo        RESPIRATION HEALTH - UWB / mmWave Radar System
echo ====================================================================
echo.
echo Select the mode you want to run:
echo.
echo   [1] Live Radar Web Dashboard (Hardware Mode - IWR6843 on COM13/COM12)
echo   [2] Demo Radar Web Dashboard (Simulated Mode - No Hardware Needed)
echo   [3] Behind-Wall / Sleep Monitoring System (Port 5004 + React UI)
echo   [4] Standalone Python Radar Tracker (CLI + Live Matplotlib Waveforms)
echo   [5] Main Radarix System (Full Stack + EDA Analysis API)
echo   [6] Stop All Running Servers (Kill ports 5173, 6666, 5004, 5001, 5000)
echo   [Q] Quit
echo.
echo ====================================================================
set /p choice="Enter choice [1-6, S, or Q] (Default: 1): "

if "%choice%"=="" set choice=1
if /i "%choice%"=="Q" goto QUIT
if /i "%choice%"=="S" goto STOP_ALL
if "%choice%"=="1" goto RUN_LIVE_RADAR
if "%choice%"=="2" goto RUN_DEMO_RADAR
if "%choice%"=="3" goto RUN_BEHIND_WALL
if "%choice%"=="4" goto RUN_STANDALONE
if "%choice%"=="5" goto RUN_MAIN_GPP
if "%choice%"=="6" goto STOP_ALL

echo Invalid option. Please select 1-6, S, or Q.
timeout /t 2 >nul
goto MENU

:RUN_LIVE_RADAR
cls
echo ====================================================================
echo Starting Live Radar Web Dashboard (Port 6666 + Port 5173)...
echo ====================================================================
echo.
echo [1/3] Launching Flask/SocketIO Backend (Hardware Mode)...
start "RespirationHealth Backend (Live Radar)" cmd /k "cd /d "%PROJECT_ROOT%RespirationHealth-feature-radar\RespirationHealth-feature-radar\backend" && python app.py"

echo [2/3] Checking Frontend dependencies and starting Vite...
start "RespirationHealth Frontend (Port 5173)" cmd /k "cd /d "%PROJECT_ROOT%RespirationHealth-feature-radar\RespirationHealth-feature-radar\frontend" && if not exist node_modules (echo Installing frontend packages... && npm install) && npm run dev"

echo [3/3] Opening browser in 4 seconds...
timeout /t 4 >nul
start http://localhost:5173
echo.
echo ====================================================================
echo Services started! Keep the opened console windows running.
echo Web UI: http://localhost:5173  ^|  Backend API: http://127.0.0.1:6666
echo ====================================================================
pause
goto QUIT

:RUN_DEMO_RADAR
cls
echo ====================================================================
echo Starting Demo Radar Web Dashboard (Simulated Mode)...
echo ====================================================================
echo.
echo [1/3] Launching Demo Backend (Synthetic Signals on Port 6666)...
start "RespirationHealth Backend (Demo Mode)" cmd /k "cd /d "%PROJECT_ROOT%RespirationHealth-feature-radar\RespirationHealth-feature-radar\backend" && python app_demo.py"

echo [2/3] Checking Frontend dependencies and starting Vite...
start "RespirationHealth Frontend (Port 5173)" cmd /k "cd /d "%PROJECT_ROOT%RespirationHealth-feature-radar\RespirationHealth-feature-radar\frontend" && if not exist node_modules (echo Installing frontend packages... && npm install) && npm run dev"

echo [3/3] Opening browser in 4 seconds...
timeout /t 4 >nul
start http://localhost:5173
echo.
echo ====================================================================
echo Demo started! Real-time synthetic vitals will stream to your browser.
echo Web UI: http://localhost:5173  ^|  Backend API: http://127.0.0.1:6666
echo ====================================================================
pause
goto QUIT

:RUN_BEHIND_WALL
cls
echo ====================================================================
echo Starting Behind-Wall / Sleep Monitoring System...
echo ====================================================================
echo.
echo [1/4] Launching Auth API (Port 5003)...
start "Behind-Wall Auth API (5003)" cmd /k "cd /d "%PROJECT_ROOT%gpp-project-behindwall\backend" && python add_user_api.py"

echo [2/4] Launching Sensor Backend Server on port 5004...
start "Behind-Wall Backend (Port 5004)" cmd /k "cd /d "%PROJECT_ROOT%gpp-project-behindwall\backend" && python app.py"

echo [3/4] Starting Behind-Wall Frontend on port 5173...
start "Behind-Wall Frontend" cmd /k "cd /d "%PROJECT_ROOT%gpp-project-behindwall" && if not exist node_modules (echo Installing frontend packages... && npm install) && npm run dev"

echo [4/4] Opening browser in 4 seconds...
timeout /t 4 >nul
start http://localhost:5173
echo.
echo ====================================================================
echo Services started!
echo Web UI: http://localhost:5173  ^|  Backend: http://localhost:5004  ^|  Auth: Port 5003
echo ====================================================================
pause
goto QUIT

:RUN_STANDALONE
cls
echo ====================================================================
echo Running Standalone Radar Tracker (vital_signs_tracker.py)...
echo ====================================================================
echo.
echo Connecting to mmWave radar on COM13 (User) and COM12 (Data)...
cd /d "%PROJECT_ROOT%"
python vital_signs_tracker.py
echo.
pause
goto QUIT

:RUN_MAIN_GPP
cls
echo ====================================================================
echo Starting Main Radarix System...
echo ====================================================================
echo.
echo [1/6] Starting Auth API (Port 5003)...
start "GPP Auth API (5003)" cmd /k "cd /d "%PROJECT_ROOT%gpp-project\backend" && python add_user_api.py"

echo [2/6] Starting Pipeline API (Port 5002)...
start "GPP Pipeline API (5002)" cmd /k "cd /d "%PROJECT_ROOT%gpp-project\backend" && python api\pipeline.py"

echo [3/6] Starting Waveform API (Port 5004)...
start "GPP Waveform API (5004)" cmd /k "cd /d "%PROJECT_ROOT%gpp-project\backend" && python app.py"

echo [4/6] Starting EDA / Statistics API (Port 5001)...
start "GPP EDA API (5001)" cmd /k "cd /d "%PROJECT_ROOT%gpp-project\backend" && python eda_flask.py"

echo [5/6] Starting Main Frontend...
start "GPP Frontend" cmd /k "cd /d "%PROJECT_ROOT%gpp-project" && if not exist node_modules (echo Installing frontend packages... && npm install) && npm run dev"

echo [6/6] Opening browser in 4 seconds...
timeout /t 4 >nul
start http://localhost:5173
echo.
echo ====================================================================
echo Services started!
echo Web UI: http://localhost:5173
echo Pipeline: Port 5002  ^|  Waveforms: Port 5004  ^|  EDA: Port 5001  ^|  Auth: Port 5003
echo ====================================================================
pause
goto QUIT

:STOP_ALL
cls
echo ====================================================================
echo             Stopping Respiration Health Servers
echo ====================================================================
echo.
set "PORTS=5173 6666 5004 5001 5002 5000 5003"
echo Searching for active processes on ports: %PORTS%...
echo.

for %%P in (%PORTS%) do (
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%%P ^| findstr LISTENING') do (
        echo [STOPPING] Process on port %%P (PID: %%a)...
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo.
echo All project servers have been stopped.
timeout /t 3 >nul
goto MENU

:QUIT
exit /b 0


