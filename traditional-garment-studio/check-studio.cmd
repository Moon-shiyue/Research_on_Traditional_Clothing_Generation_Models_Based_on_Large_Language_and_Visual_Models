@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not defined GARMENT_PYTHON set "GARMENT_PYTHON=%USERPROFILE%\miniconda3\envs\d2g\python.exe"
if not exist "%GARMENT_PYTHON%" (
  echo Python environment not found. Set GARMENT_PYTHON to the project Python executable.
  pause
  exit /b 1
)
"%GARMENT_PYTHON%" -X utf8 tools/check_studio.py %*
set "STUDIO_CHECK_EXIT=%ERRORLEVEL%"
if "%~1"=="" pause
exit /b %STUDIO_CHECK_EXIT%
