@echo off
cd /d "%~dp0"
echo Starting temperature monitor...
echo Open http://localhost:8080 for the local dashboard.
echo.
python temperature_monitor.py
pause
