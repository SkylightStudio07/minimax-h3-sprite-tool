@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo MiniMax H3 environment is missing. Run setup again.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "idle_tool.py"
