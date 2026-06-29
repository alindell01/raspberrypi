@echo off
REM ============================================================
REM  Start the media stack. Double-click this, or drop a shortcut
REM  to it in your Startup folder (Win+R -> shell:startup).
REM  Safe to run anytime - it only starts what isn't running.
REM ============================================================

cd /d C:\raspberrypi\mediaserver

REM --- Make sure Docker Desktop is running ---
tasklist /FI "IMAGENAME eq Docker Desktop.exe" | find /I "Docker Desktop.exe" >nul
if errorlevel 1 (
  echo Starting Docker Desktop...
  start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
)

REM --- Wait for the Docker engine to be ready ---
echo Waiting for the Docker engine to come up...
:waitloop
docker info >nul 2>&1
if errorlevel 1 (
  timeout /t 3 >nul
  goto waitloop
)

REM --- Start the stack ---
echo Starting the media stack...
docker compose up -d

REM --- Quick sanity check that the H: drive is mounted ---
docker compose exec -T radarr ls /data >nul 2>&1
if errorlevel 1 (
  echo.
  echo *** WARNING: the H: drive is not mounted inside the containers. ***
  echo *** Run RepairAndStart.bat to fix it.                          ***
  echo.
)

echo.
echo Done.  Seerr: http://localhost:5055   Radarr: http://localhost:7878
pause
