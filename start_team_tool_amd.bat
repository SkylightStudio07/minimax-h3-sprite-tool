@echo off
setlocal
cd /d "%~dp0"
set SPRITE_BACKEND=amd
if not exist ".venv-amd\Scripts\python.exe" (
  echo Run setup_windows_amd.bat first.
  pause
  exit /b 1
)
".venv-amd\Scripts\python.exe" "team_server.py"
if errorlevel 1 pause
