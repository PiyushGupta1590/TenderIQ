@echo off
echo ========================================
echo    TenderIQ - AI Bid Evaluation System
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11+
    pause & exit /b 1
)

:: Check Node
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Install Node.js 18+
    pause & exit /b 1
)

:: Install Python deps
echo [1/3] Installing Python dependencies...
pip install -r requirements.txt --quiet

:: Install frontend deps
echo [2/3] Installing frontend dependencies...
cd frontend
call npm install --silent
cd ..

:: Start backend
echo [3/3] Starting TenderIQ...
echo.
echo  Backend  : http://localhost:8000
echo  Frontend : http://localhost:5173
echo  API Docs : http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop all services.
echo.

start "TenderIQ Backend" cmd /k "python -m uvicorn backend.main:app --reload --port 8000"
timeout /t 2 /nobreak >nul
cd frontend
start "TenderIQ Frontend" cmd /k "npm run dev"
cd ..

echo Services started. Opening browser...
timeout /t 3 /nobreak >nul
start http://localhost:5173
