#!/bin/bash
cd "$(dirname "$0")"
pkill -f "/home/user268/exam/app.py" 2>/dev/null || true
sleep 1
nohup python3 app.py >> app.log 2>&1 &
echo "Started exam dashboard PID $!"
