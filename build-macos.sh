#!/usr/bin/env bash
# ========================================================
# JIGSI KARIA TERMINATOR - macOS BUILD & LAUNCH SCRIPT
# ========================================================
echo "⚡ Initializing Jigsi Karia OSINT Matrix on macOS..."

# Check Node
if ! command -v node &> /dev/null
then
    echo "[ERROR] Node.js is required. Please install via Homebrew: brew install node"
    exit 1
fi

echo "[+] Installing project dependencies..."
npm install

echo "[+] Starting secure OSINT Gateway server..."
node server.js &
SERVER_PID=$!

sleep 2
echo "[+] Opening interface in default browser..."
open "http://localhost:3000"

echo "Gateway running (PID: $SERVER_PID). Press Ctrl+C to terminate."
wait $SERVER_PID
