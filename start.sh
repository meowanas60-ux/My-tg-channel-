#!/usr/bin/env bash

set -u

echo "🚀 Starting Anas APK System..."
echo "========================================"

# ------------------------------------------------------------
# Start Download Bot
# ------------------------------------------------------------

echo "▶️ Starting Download Bot..."

python -u bot.py &
BOT_PID=$!

echo "✅ Download Bot started | PID: $BOT_PID"

sleep 3

# ------------------------------------------------------------
# Start Main Telethon Monitor
# ------------------------------------------------------------

echo "▶️ Starting Main Monitor..."

python -u main.py &
MAIN_PID=$!

echo "✅ Main Monitor started | PID: $MAIN_PID"

echo "========================================"
echo "🟢 All systems running!"
echo "🤖 Bot PID: $BOT_PID"
echo "⚙️ Monitor PID: $MAIN_PID"
echo "========================================"

# ------------------------------------------------------------
# Monitor both processes
# If either process exits, stop the other and exit.
# Render will restart the service if configured to do so.
# ------------------------------------------------------------

while true; do
    if ! kill -0 "$BOT_PID" 2>/dev/null; then
        echo "❌ Download Bot stopped!"
        kill "$MAIN_PID" 2>/dev/null || true
        exit 1
    fi

    if ! kill -0 "$MAIN_PID" 2>/dev/null; then
        echo "❌ Main Monitor stopped!"
        kill "$BOT_PID" 2>/dev/null || true
        exit 1
    fi

    sleep 10
done
