@echo off
rem Starts Pukaar and a public Cloudflare link, each in its own window.
rem Close those two windows to take the site offline.
rem The public address is printed in the "Pukaar tunnel" window and saved to tunnel.log.

cd /d "%~dp0"
start "Pukaar server" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
timeout /t 5 /nobreak >nul
if exist "%~dp0tunnel.log" del "%~dp0tunnel.log"
start "Pukaar tunnel" cmd /k ""%USERPROFILE%\tools\cloudflared\cloudflared.exe" tunnel --url http://localhost:8000 --logfile "%~dp0tunnel.log""
echo Pukaar is starting. The public link appears in the "Pukaar tunnel" window in a few seconds.
