@echo off
REM Diagnostic script to check if backend is running
echo.
echo ====================================================================
echo RespirationHealth Backend Diagnostic
echo ====================================================================
echo.

REM Check if backend process is running
tasklist | find /i "python" >nul
if %errorlevel% equ 0 (
    echo [OK] Python is running
) else (
    echo [ERROR] Python is NOT running
    echo.
    echo Solution:
    echo 1. Open a NEW terminal window
    echo 2. Run this command:
    echo    cd backend
    echo    py app_demo.py
    echo.
    pause
    exit /b 1
)

REM Try to connect to port 6666
echo.
echo Checking if backend is listening on port 6666...
netstat -ano | find ":6666" >nul
if %errorlevel% equ 0 (
    echo [OK] Port 6666 is OPEN - Backend is running!
    echo.
    echo You can now:
    echo 1. Refresh your browser (Ctrl+R)
    echo 2. Click the START SENSOR button
    echo.
) else (
    echo [ERROR] Port 6666 is NOT listening
    echo.
    echo Solution:
    echo 1. Open a NEW terminal window
    echo 2. Navigate to the backend folder:
    echo    cd RespirationHealth-feature-radar\RespirationHealth-feature-radar\backend
    echo 3. Run:
    echo    py app_demo.py
    echo.
)

echo ====================================================================
pause
