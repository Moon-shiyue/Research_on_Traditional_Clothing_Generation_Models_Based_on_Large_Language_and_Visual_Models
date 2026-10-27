@echo off
setlocal
cd /d "%~dp0frontend"
call npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
if errorlevel 1 pause
