@echo off
REM ============================================================
REM  Use this ONLY when the apps won't load or you see
REM  "No such device" / an empty page / a drive-mount error.
REM
REM  It fully resets Docker's WSL2 engine (which clears the
REM  stale H: drive mount), then restarts everything.
REM  This is the automated version of: Quit Docker -> wsl --shutdown
REM  -> reopen Docker -> docker compose up -d
REM ============================================================

echo Stopping Docker Desktop...
taskkill /IM "Docker Desktop.exe" /F >nul 2>&1
timeout /t 5 >nul

echo Resetting the WSL2 engine (clears the stale drive mount)...
wsl --shutdown
timeout /t 5 >nul

echo Starting Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"

echo Waiting for the Docker engine to come up...
:waitloop
docker info >nul 2>&1
if errorlevel 1 (
  timeout /t 3 >nul
  goto waitloop
)

cd /d C:\raspberrypi\mediaserver
echo Starting the media stack (rebuilding containers so drive mounts are fresh)...
REM --force-recreate rebuilds every container. This is what actually fixes a
REM stale "/data" mount - a plain "up -d" reuses the old container and keeps
REM the broken mount.
docker compose up -d --force-recreate

echo Verifying the H: drive is mounted...
docker compose exec -T radarr ls /data >nul 2>&1
if errorlevel 1 (
  echo.
  echo *** Drive still not mounted. Make sure H: is connected in Windows, ***
  echo *** then run this script again.                                    ***
) else (
  echo Drive mounted OK.
)

echo.
echo Done.  Seerr: http://localhost:5055   Radarr: http://localhost:7878
pause
