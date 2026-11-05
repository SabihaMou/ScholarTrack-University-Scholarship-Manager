@echo off
setlocal
cd /d "%~dp0"
title ScholarTrack - Windows Launcher
where py >nul 2>&1
if not errorlevel 1 (
  py -3.10 -c "import sys" >nul 2>&1
  if not errorlevel 1 (set "PY=py -3.10") else (set "PY=py -3")
) else (set "PY=python")
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  %PY% -m venv .venv
  if errorlevel 1 goto error
)
set "VENV_PY=.venv\Scripts\python.exe"
echo Installing/checking ScholarTrack requirements...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto error
echo.
echo Starting ScholarTrack at http://127.0.0.1:5000
start "" http://127.0.0.1:5000
"%VENV_PY%" app.py
if errorlevel 1 goto error
exit /b 0
:error
echo.
echo Something went wrong. Please send a screenshot of this window.
pause
exit /b 1
