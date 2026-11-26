@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-jade-control.ps1" %*
if errorlevel 1 (
  echo.
  echo Echec de l'installation du controleur. Voir le message ci-dessus.
  pause
  exit /b 1
)
echo.
echo Installation terminee. La tache Windows peut demarrer le controleur automatiquement.
pause
