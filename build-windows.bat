@echo off
TITLE Jigsi Karia Terminator v4.0 - Windows Builder & Launcher
COLOR 0A
echo ========================================================
echo   JIGSI KARIA TERMINATOR - WINDOWS DEPLOYMENT SUITE
echo ========================================================
echo [1] Checking Node.js Environment...
node -v >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed. Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

echo [2] Installing Dependencies...
call npm install

echo [3] Launching Local Desktop Gateway Server...
start http://localhost:3000
npm start
pause
