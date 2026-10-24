# ScholarLens Single Command Startup Script (PowerShell)
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Starting ScholarLens Full-Stack Production Environment" -ForegroundColor Green
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Yellow
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Cyan

Start-Process -FilePath "cmd.exe" -ArgumentList "/k", ".\backend_venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"
Start-Sleep -Seconds 3
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd frontend && npm start -- -p 3000"
Write-Host "ScholarLens services started in separate processes." -ForegroundColor Green
