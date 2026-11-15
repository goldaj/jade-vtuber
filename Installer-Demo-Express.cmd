@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0demo\express\Installer-Demo-Express.ps1"
if errorlevel 1 (
  echo Installation echouee. Lire le message ci-dessus.
  pause
  exit /b 1
)
echo Lancez Jade Demo Express depuis le menu Demarrer.
pause
