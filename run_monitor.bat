@echo off
REM run_monitor.bat -- what Windows Task Scheduler runs on a schedule.
REM It moves into this folder, runs the monitor with the project's own Python,
REM and appends everything to monitor.log so you can see the history of runs.

cd /d "%~dp0"
echo. >> monitor.log
echo ===== Run started: %date% %time% ===== >> monitor.log
".venv\Scripts\python.exe" fetch_jobs.py >> monitor.log 2>&1
echo ===== Run finished: %date% %time% ===== >> monitor.log
