@echo off
setlocal
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File ".\scripts\setup_yue2.ps1" %*
if errorlevel 1 pause
