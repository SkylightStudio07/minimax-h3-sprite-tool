@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" "team_server.py"
if errorlevel 1 pause
