@echo off
REM Stop Navbe desktop + bundled/CLI daemon before install/uninstall.
REM Safe to run when nothing is running (errors ignored).

setlocal

REM Prefer graceful stop via bundled CLI (clears serve.pid).
if exist "%~dp0navbe\navbe.exe" (
  "%~dp0navbe\navbe.exe" stop >nul 2>&1
)

REM Force-stop desktop shell and any navbe serve/sidecar still holding files.
taskkill /F /IM "navbe-desktop.exe" /T >nul 2>&1
taskkill /F /IM "navbe.exe" /T >nul 2>&1

if exist "%USERPROFILE%\.navbe\serve.pid" (
  del /f /q "%USERPROFILE%\.navbe\serve.pid" >nul 2>&1
)

exit /b 0
