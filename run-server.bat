@echo off
rem Starts only the Pukaar server (http://localhost:8000) in its own window.
cd /d "%~dp0backend"
start "Pukaar server" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
