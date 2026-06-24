@echo off
REM Launches the scraper (Discord + continuous) and the web dashboard together.
start "Workana Scraper" cmd /k python main.py -d -c
start "Workana Dashboard" cmd /k python dashboard.py
timeout /t 2 >nul
start "" http://127.0.0.1:5000
