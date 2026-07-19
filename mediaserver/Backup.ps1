param(
  [Parameter(Mandatory=$true)][string]$Dest,  # external drive, e.g.  E:\   or  E:\Backup
  [switch]$IncludePlex,                        # also back up Plex library DB + settings
  [switch]$NoStop                              # skip stopping the stack (use if Docker is misbehaving)
)

# ============================================================
#  Backup.ps1 - copies everything needed to rebuild the media
#  server on a fresh Windows install, onto an external drive.
#
#  Your MEDIA is NOT here - it's on G: and the USB drives, which
#  are separate from the dying C: SSD. This backs up the app
#  configs/databases (in C:\raspberrypi\mediaserver\config), the
#  .env, and optionally Plex's library database.
#
#  Run (replace E: with your external drive letter):
#     powershell -ExecutionPolicy Bypass -File .\Backup.ps1 -Dest E:\ -IncludePlex
# ============================================================

$ErrorActionPreference = 'Continue'
$stackDir = 'C:\raspberrypi\mediaserver'
$stamp    = Get-Date -Format 'yyyy-MM-dd_HHmm'
$target   = Join-Path (Join-Path $Dest 'MediaServerBackup') $stamp

Write-Host "Backing up to: $target" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $target | Out-Null

# 1. Stop the stack so the app databases are copied clean (not mid-write)
if (-not $NoStop) {
  Write-Host "Stopping the media stack for a clean copy..."
  Push-Location $stackDir
  docker compose stop
  Pop-Location
}

# 2. The whole stack folder = compose + scripts + .env + config\ (all app data).
#    Skip logs, caches, and the qBittorrent socket (not needed, and they lock/error).
Write-Host "Copying the media-server stack (config, .env, scripts)..."
robocopy $stackDir (Join-Path $target 'mediaserver') /E /R:0 /W:0 /NFL /NDL /NP `
  /XF "ipc-socket" /XD "logs" "Cache"

# 3. Optional: Plex library database + settings (your watch history, collections, etc.)
if ($IncludePlex) {
  $plex = Join-Path $env:LOCALAPPDATA 'Plex Media Server'
  if (Test-Path $plex) {
    Write-Host "Copying Plex library DB + settings (skipping big regenerable caches)..."
    robocopy $plex (Join-Path $target 'Plex Media Server') /E /R:1 /W:1 /NFL /NDL /NP `
      /XD "Cache" "Codecs" "Crash Reports" "Logs" "Diagnostics" "Media"
  } else {
    Write-Host "Plex data folder not found at $plex - skipping." -ForegroundColor Yellow
  }
}

# 4. Restart the stack
if (-not $NoStop) {
  Write-Host "Restarting the media stack..."
  Push-Location $stackDir
  docker compose start
  Pop-Location
}

Write-Host ""
Write-Host "DONE. Backup at: $target" -ForegroundColor Green
Write-Host "Confirm these exist on the external drive before wiping the old SSD:" -ForegroundColor Green
Write-Host "   $target\mediaserver\.env"
Write-Host "   $target\mediaserver\config\   (radarr, sonarr, prowlarr, qbittorrent, overseerr, etc.)"
if ($IncludePlex) { Write-Host "   $target\Plex Media Server\Plug-in Support\Databases\" }
Write-Host ""
Write-Host "See RESTORE.md for putting it back on the new SSD."
