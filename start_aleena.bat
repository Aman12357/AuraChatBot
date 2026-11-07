@echo off
title Aleena AI Master Companion Launcher
echo ========================================================
echo  Starting Aleena AI Master Companion...
echo ========================================================
echo.

if not exist ".env" (
    echo ERROR: Root .env file is missing.
    echo Copy .env.example to .env and configure JWT_SECRET, MASTER_EMAIL and MASTER_SETUP_KEY.
    pause
    exit /b 1
)

if not exist "web\\.env.local" (
    copy "web\\.env.example" "web\\.env.local" >nul
)

echo 1. Starting Node.js API Backend (Port 8765)...
start "Aleena Node Backend" /min cmd /c "npm start"

timeout /t 3 /nobreak >nul

echo 2. Starting Python Desktop Bridge (Port 8766)...
start "Aleena Python Bridge" /min cmd /c "python web_server.py"

timeout /t 3 /nobreak >nul

echo 3. Starting Next.js Web Companion Frontend (Port 3000)...
start "Aleena Next.js Frontend" /min cmd /c "cd web && npm run dev"

echo.
echo ========================================================
echo  Aleena AI startup commands launched.
echo  Web App:       http://localhost:3000
echo  Node API:      http://localhost:8765
echo  Python Bridge: http://localhost:8766
echo ========================================================
echo.
pause
