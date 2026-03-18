@echo off
setlocal
cd /d "%~dp0\.."
py -2 tools\build_mtmod.py
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)
echo Build completed.
pause
