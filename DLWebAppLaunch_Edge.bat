@echo off
REM === Start the Flask app ===
start "" cmd /k "py app.py"

REM === Wait a moment for Flask to start ===
timeout /t 3 > nul

REM === Launch Chrome in app window mode ===
start "" edge --new-window --window-size=1400,900 --app=http://127.0.0.1:5000