@echo off
REM Force-stop Navbe desktop + any serve on :8000 (navbe.exe OR python listener).
setlocal

if exist "%~dp0navbe\navbe.exe" (
  "%~dp0navbe\navbe.exe" stop >nul 2>&1
)

powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen -EA SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -EA SilentlyContinue }" >nul 2>&1

taskkill /F /IM "navbe-desktop.exe" /T >nul 2>&1
taskkill /F /IM "navbe.exe" /T >nul 2>&1

if exist "%USERPROFILE%\.navbe\serve.pid" (
  del /f /q "%USERPROFILE%\.navbe\serve.pid" >nul 2>&1
)

exit /b 0
