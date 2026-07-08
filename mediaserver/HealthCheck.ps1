param([switch]$Repair)

# ============================================================
#  HealthCheck.ps1 - checks every media-server container and
#  restarts anything that's down. Safe to run repeatedly.
#
#  Run manually:
#     powershell -ExecutionPolicy Bypass -File .\HealthCheck.ps1
#  Auto-run the full reset if the drive mount is lost:
#     powershell -ExecutionPolicy Bypass -File .\HealthCheck.ps1 -Repair
#
#  It checks two things per service:
#    1. is the container running?
#    2. is its web UI port actually answering? (catches the
#       "container Up but WebUI refused" case)
#  ...then restarts any that fail. gluetun + qBittorrent are
#  handled together because qBittorrent rides gluetun's network.
# ============================================================

$ErrorActionPreference = 'SilentlyContinue'
$stackDir = 'C:\raspberrypi\mediaserver'
Set-Location $stackDir

$logFile = Join-Path $stackDir 'healthcheck.log'
function Log($msg) {
  $line = "{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
  Write-Host $line
  Add-Content -Path $logFile -Value $line
}

# service name -> host port that should be listening
$services = [ordered]@{
  qbittorrent    = 18080   # via gluetun
  radarr         = 7878
  sonarr         = 8989
  lidarr         = 8686
  prowlarr       = 9696
  seerr          = 5055
  audiobookshelf = 13378
  lazylibrarian  = 5299
  flaresolverr   = 8191
}

function Test-Port($port) {
  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $iar = $client.BeginConnect('127.0.0.1', $port, $null, $null)
    if ($iar.AsyncWaitHandle.WaitOne(3000, $false) -and $client.Connected) {
      $client.EndConnect($iar); return $true
    }
    return $false
  } catch { return $false } finally { $client.Close() }
}

function Container-Running($name) {
  return ((docker inspect -f '{{.State.Running}}' $name 2>$null) -eq 'true')
}

# --- 1. Docker engine itself ---
docker info *> $null
if ($LASTEXITCODE -ne 0) {
  Log "Docker engine not responding - starting Docker Desktop..."
  Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
  for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep 5
    docker info *> $null
    if ($LASTEXITCODE -eq 0) { break }
  }
  if ($LASTEXITCODE -ne 0) { Log "Docker still down after waiting. Aborting."; exit 1 }
  Log "Docker engine is up."
  docker compose up -d *> $null
  Start-Sleep 20
}

# --- 2. gluetun + qBittorrent (coupled: qbit uses gluetun's network) ---
$gluetunRunning = Container-Running 'gluetun'
$gluetunHealth  = docker inspect -f '{{.State.Health.Status}}' gluetun 2>$null
$restartedGluetun = $false
if (-not $gluetunRunning -or $gluetunHealth -eq 'unhealthy') {
  Log "gluetun down/unhealthy (running=$gluetunRunning health=$gluetunHealth) - restarting gluetun + qbittorrent..."
  docker compose up -d gluetun *> $null
  docker compose restart gluetun *> $null
  Start-Sleep 20
  docker compose restart qbittorrent *> $null
  $restartedGluetun = $true
} else {
  # gluetun is fine; check qBittorrent's WebUI on its own
  if (-not (Container-Running 'qbittorrent') -or -not (Test-Port 18080)) {
    Log "qbittorrent not answering on 18080 - restarting qbittorrent..."
    docker compose up -d qbittorrent *> $null
    docker compose restart qbittorrent *> $null
  } else {
    Log "qbittorrent OK (port 18080), gluetun healthy"
  }
}

# --- 3. Drive-mount check (the USB/WSL gremlin - only a full reset fixes it) ---
Start-Sleep 5
if (Container-Running 'qbittorrent') {
  docker compose exec -T qbittorrent ls /data/downloads *> $null
  if ($LASTEXITCODE -ne 0) {
    Log "WARNING: qbittorrent can't see /data (drive mount lost)."
    if ($Repair) {
      Log "-Repair set: running RepairAndStart.bat (full reset)..."
      & (Join-Path $stackDir 'RepairAndStart.bat')
    } else {
      Log "Fix: run RepairAndStart.bat, or re-run this script with -Repair."
    }
  } else {
    Log "qbittorrent /data mount OK"
  }
}

# --- 4. Everything else ---
foreach ($svc in $services.Keys) {
  if ($svc -eq 'qbittorrent') { continue }   # handled above
  $port = $services[$svc]
  $running = Container-Running $svc
  $portOk  = Test-Port $port
  if (-not $running -or -not $portOk) {
    Log "$svc down (running=$running port${port}=$portOk) - restarting..."
    docker compose up -d $svc *> $null
    docker compose restart $svc *> $null
  } else {
    Log "$svc OK (port $port)"
  }
}

Log "Health check complete."
