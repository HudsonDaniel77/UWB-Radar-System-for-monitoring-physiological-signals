@echo off
title Stop Respiration Health System
color 0C

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
echo ====================================================================
echo All project servers have been stopped successfully!
echo You can also close any remaining console windows.
echo ====================================================================
echo.
pause
