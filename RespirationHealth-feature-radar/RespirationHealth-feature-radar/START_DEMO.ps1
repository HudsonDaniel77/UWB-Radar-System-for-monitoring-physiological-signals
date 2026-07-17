# RespirationHealth Demo Startup Script
# Right-click on this file → Run with PowerShell

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "RespirationHealth Demo - Starting..." -ForegroundColor Cyan
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

# Start backend
Write-Host "[1/3] Starting Backend (app_demo.py)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @("
  cd backend
  py app_demo.py
")

# Wait for backend to initialize
Start-Sleep -Seconds 2

# Start frontend
Write-Host "[2/3] Starting Frontend (Vite dev server)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @("
  cd frontend
  npm install 2>$null
  npm run dev
")

# Wait for frontend to be ready
Start-Sleep -Seconds 4

# Open browser
Write-Host "[3/3] Opening browser at http://localhost:5173..." -ForegroundColor Yellow
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "=====================================================================" -ForegroundColor Green
Write-Host "✓ Both services started!" -ForegroundColor Green
Write-Host "✓ Browser should open automatically" -ForegroundColor Green
Write-Host "✓ Click START SENSOR button to begin" -ForegroundColor Green
Write-Host "=====================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "To stop: Close both terminal windows" -ForegroundColor Gray
