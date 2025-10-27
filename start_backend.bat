@echo off
REM Helper batch script to start the backend from the repository root
REM Usage: double-click or run from cmd: start_backend.bat
cd /d "%~dp0\\backend"
echo Starting backend from: %CD%
REM Run uvicorn pointing at the backend package module
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
