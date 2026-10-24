@echo off
echo ======================================================================
echo Starting ScholarLens Full-Stack Production Environment
echo Backend:  http://localhost:8000 (FastAPI + SentenceTransformers)
echo Frontend: http://localhost:3000 (Next.js Production Build)
echo ======================================================================

start "ScholarLens Backend (Port 8000)" cmd /k ".\backend_venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak >nul
start "ScholarLens Frontend (Port 3000)" cmd /k "cd frontend && npm start -- -p 3000"

echo Services started!
