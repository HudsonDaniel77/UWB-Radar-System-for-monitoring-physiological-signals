# RespirationHealth PowerShell System Launcher
# Usage: powershell -ExecutionPolicy Bypass -File .\start_system.ps1

$projectRoot = $PSScriptRoot

Clear-Host
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "       RESPIRATION HEALTH - UWB / mmWave Radar System" -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Select the mode you want to run:"
Write-Host ""
Write-Host "  [1] Live Radar Web Dashboard (Hardware Mode - COM13/COM12 on Port 6666)" -ForegroundColor Green
Write-Host "  [2] Demo Radar Web Dashboard (Simulated Mode - No Hardware Needed)" -ForegroundColor Yellow
Write-Host "  [3] Behind-Wall / Sleep Monitoring System (Port 5004 + React UI)" -ForegroundColor Magenta
Write-Host "  [4] Standalone Python Radar Tracker (CLI + Live Matplotlib Waveforms)" -ForegroundColor Cyan
Write-Host "  [5] Main Radarix System (Full Stack + EDA Analysis API)" -ForegroundColor Blue
Write-Host "  [6] Stop All Running Servers (Kill ports 5173, 6666, 5004, 5001, 5000)" -ForegroundColor Red
Write-Host "  [Q] Quit" -ForegroundColor Gray
Write-Host ""
Write-Host "====================================================================" -ForegroundColor Cyan

$choice = Read-Host "Enter choice [1-6, S, or Q] (Default: 1)"
if ([string]::IsNullOrWhiteSpace($choice)) { $choice = "1" }

switch ($choice.ToUpper()) {
    "1" {
        Write-Host "`nStarting Live Radar Web Dashboard..." -ForegroundColor Green
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\RespirationHealth-feature-radar\RespirationHealth-feature-radar\backend'; python app.py"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\RespirationHealth-feature-radar\RespirationHealth-feature-radar\frontend'; if (-not (Test-Path 'node_modules')) { npm install }; npm run dev"
        Start-Sleep -Seconds 4
        Start-Process "http://localhost:5173"
    }
    "2" {
        Write-Host "`nStarting Demo Radar Web Dashboard (Synthetic Signals)..." -ForegroundColor Yellow
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\RespirationHealth-feature-radar\RespirationHealth-feature-radar\backend'; python app_demo.py"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\RespirationHealth-feature-radar\RespirationHealth-feature-radar\frontend'; if (-not (Test-Path 'node_modules')) { npm install }; npm run dev"
        Start-Sleep -Seconds 4
        Start-Process "http://localhost:5173"
    }
    "3" {
        Write-Host "`nStarting Behind-Wall System..." -ForegroundColor Magenta
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\gpp-project-behindwall\backend'; python app.py"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\gpp-project-behindwall'; if (-not (Test-Path 'node_modules')) { npm install }; npm run dev"
        Start-Sleep -Seconds 4
        Start-Process "http://localhost:5173"
    }
    "4" {
        Write-Host "`nRunning Standalone Radar Tracker..." -ForegroundColor Cyan
        Set-Location $projectRoot
        python vital_signs_tracker.py
    }
    "5" {
        Write-Host "`nStarting Main Radarix System..." -ForegroundColor Blue
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\gpp-project\backend'; python add_user_api.py"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\gpp-project\backend'; python api\pipeline.py"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\gpp-project\backend'; python app.py"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\gpp-project\backend'; python eda_flask.py"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\gpp-project'; if (-not (Test-Path 'node_modules')) { npm install }; npm run dev"
        Start-Sleep -Seconds 4
        Start-Process "http://localhost:5173"
    }
    { $_ -in "6", "S" } {
        Write-Host "`nStopping all processes on ports 5173, 6666, 5004, 5001, 5002, 5000..." -ForegroundColor Red
        $ports = @(5173, 6666, 5004, 5001, 5002, 5000)
        Get-NetTCPConnection -LocalPort $ports -ErrorAction SilentlyContinue | ForEach-Object {
            Write-Host "Stopping process PID $($_.OwningProcess) on port $($_.LocalPort)..."
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        }
        Write-Host "All servers stopped." -ForegroundColor Green
    }
    "Q" {
        Write-Host "Exiting."
        exit
    }
    Default {
        Write-Host "Invalid choice. Exiting."
    }
}
