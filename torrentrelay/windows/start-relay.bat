@echo off
REM ============================================================
REM  Torrent Relay launcher for Windows 11
REM  1. Edit the QB_PASSWORD line below to match your qBittorrent
REM     Web UI password (Tools > Options > Web UI).
REM  2. Double-click this file to start the relay.
REM  3. Leave the window open while you want it running.
REM ============================================================

REM ----- edit these to match your qBittorrent Web UI -----
set QB_URL=http://localhost:8080
set QB_USERNAME=admin
set QB_PASSWORD=CHANGE_ME
REM Optional: force where phone downloads go / tag them.
REM set QB_SAVEPATH=C:\Users\%USERNAME%\Downloads\torrents
REM set QB_CATEGORY=phone
REM -------------------------------------------------------

REM Jump to the repo root (this file lives in torrentrelay\windows).
cd /d "%~dp0..\.."

REM Prefer the project venv if it exists, else fall back to system python.
set PY=python
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe

echo Starting Torrent Relay on http://0.0.0.0:8800 ...
echo Open http://localhost:8800/healthz to verify, then browse from your phone.
"%PY%" -m uvicorn torrentrelay.main:app --host 0.0.0.0 --port 8800
pause
