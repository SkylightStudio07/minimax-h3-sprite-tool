@echo off
setlocal
cd /d "%~dp0"
if not exist "MINIMAX_H3_LICENSE_APPROVED.txt" (
  echo.
  echo MiniMax H3's community license excludes the Republic of Korea.
  echo Run this download only after receiving separate written authorization from MiniMax.
  echo.
  set /p CONFIRM=Type LICENSE-APPROVED if authorization has been received:
  if /I not "%CONFIRM%"=="LICENSE-APPROVED" exit /b 1
  >"MINIMAX_H3_LICENSE_APPROVED.txt" echo User confirmed separate MiniMax authorization.
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\download_models_curl.ps1"
if errorlevel 1 pause
