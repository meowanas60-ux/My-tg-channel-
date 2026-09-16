#!/bin/bash
echo "🚀 Starting Anas APK System..."
echo "▶️  Starting Download Bot..."
python bot.py &
BOT_PID=$!
echo "✅ Bot started (PID: $BOT_PID)"

sleep 3

echo "▶️  Starting Main Monitor..."
python main.py &
MAIN_PID=$!
echo "✅ Monitor started (PID: $MAIN_PID)"

echo "🟢 All systems running!"
wait
