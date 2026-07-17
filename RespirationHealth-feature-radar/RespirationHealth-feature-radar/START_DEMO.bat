@echo off
echo.
echo ====================================================================
echo RespirationHealth Demo - Starting...
echo ====================================================================
echo.

REM Start backend in a new window
cd backend
start cmd /k "echo [BACKEND] Running demo mode... && py app_demo.py"

REM Wait a moment for backend to start
timeout /t 2

REM Start frontend in another window
cd ..\frontend
echo [FRONTEND] Installing dependencies and starting...
npm install 2>nul
start cmd /k "npm run dev"

REM Show browser
timeout /t 3
echo.
echo ====================================================================
echo Both services started! Opening browser...
echo ====================================================================
start http://localhost:5173

cd ..
