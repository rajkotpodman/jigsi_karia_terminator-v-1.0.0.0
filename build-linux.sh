#!/usr/bin/env bash
# ========================================================
# JIGSI KARIA TERMINATOR - LINUX BUILD & LAUNCH SCRIPT
# ========================================================
echo "⚡ Initializing Jigsi Karia Cyber OSINT Matrix on Linux..."

if ! command -v node &> /dev/null
then
    echo "[ERROR] Node.js is required. Install via apt: sudo apt install nodejs npm"
    exit 1
fi

echo "[+] Installing Node dependencies..."
npm install

echo "[+] Starting local threat intelligence server..."
node server.js &
SERVER_PID=$!

sleep 2

# Open browser if available
if command -v xdg-open &> /dev/null
then
    xdg-open "http://localhost:3000"
elif command -v sensible-browser &> /dev/null
then
    sensible-browser "http://localhost:3000"
else
    echo "[+] Server running at http://localhost:3000"
fi

echo "Operator Matrix active (PID: $SERVER_PID). Press Ctrl+C to terminate."
wait $SERVER_PID
