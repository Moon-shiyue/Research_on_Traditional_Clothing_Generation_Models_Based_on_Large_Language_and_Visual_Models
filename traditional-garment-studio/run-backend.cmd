@echo off
setlocal
cd /d "%~dp0"
if not defined GARMENT_PYTHON set "GARMENT_PYTHON=%USERPROFILE%\miniconda3\envs\d2g\python.exe"
if not exist "%GARMENT_PYTHON%" (
  echo Python environment not found. Set GARMENT_PYTHON to the project Python executable.
  pause
  exit /b 1
)
"%GARMENT_PYTHON%" -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
if errorlevel 1 pause
