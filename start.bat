@echo off
title Flow Companion Studio Launcher
echo ==========================================================
echo    FLOW COMPANION STUDIO
echo    Hardware Tuned for RX 9070 XT + Ryzen 5 5600X
echo ==========================================================
echo.

cd /d "%~dp0"

echo [1/2] Starting Backend Orchestrator (FastAPI on http://127.0.0.1:8000)...
start "Flow Companion Backend" cmd /k "cd /d %~dp0backend && uv run uvicorn main:app --host 127.0.0.1 --port 8000"

timeout /t 2 /nobreak > nul

echo [2/2] Starting Frontend Director Dashboard (Next.js on http://localhost:3000)...
start "Flow Companion Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

timeout /t 3 /nobreak > nul

echo.
echo Launching browser at http://localhost:3000...
start http://localhost:3000

echo.
echo Flow Companion Studio is now live!
echo Press any key to exit this launcher window (services keep running).
pause > nul
