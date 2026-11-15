@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-jade-launcher.ps1"
if errorlevel 1 (
  echo.
  echo Installation du launcher en echec.
)
pause
