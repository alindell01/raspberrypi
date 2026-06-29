# Creates a "Media Server" folder on your Desktop with shortcuts to every app,
# the start/repair scripts, and a how-to-restart guide.
# Run once:  powershell -ExecutionPolicy Bypass -File .\MakeDesktopShortcuts.ps1

$stackDir = "C:\raspberrypi\mediaserver"
$desktop  = [Environment]::GetFolderPath("Desktop")
$folder   = Join-Path $desktop "Media Server"

New-Item -ItemType Directory -Force -Path $folder | Out-Null

# --- Web UI shortcuts (.url) ---
$apps = [ordered]@{
  "1 - Seerr (Request movies and TV)" = "http://localhost:5055"
  "2 - Radarr (Movies)"               = "http://localhost:7878"
  "3 - Sonarr (TV)"                   = "http://localhost:8989"
  "4 - Prowlarr (Indexers)"           = "http://localhost:9696"
  "5 - Lidarr (Music)"                = "http://localhost:8686"
  "6 - qBittorrent (Downloads)"       = "http://localhost:18080"
  "7 - Audiobookshelf (Books)"        = "http://localhost:13378"
}
foreach ($name in $apps.Keys) {
  $path = Join-Path $folder "$name.url"
  Set-Content -Path $path -Value "[InternetShortcut]`r`nURL=$($apps[$name])" -Encoding ASCII
}

# --- Shortcuts to the start / repair scripts (.lnk) ---
$ws = New-Object -ComObject WScript.Shell
function New-BatShortcut($linkName, $target) {
  $lnk = $ws.CreateShortcut((Join-Path $folder $linkName))
  $lnk.TargetPath        = $target
  $lnk.WorkingDirectory  = $stackDir
  $lnk.Save()
}
New-BatShortcut "START - turn everything on.lnk"        (Join-Path $stackDir "StartMediaStack.bat")
New-BatShortcut "REPAIR - fix if apps won't load.lnk"   (Join-Path $stackDir "RepairAndStart.bat")

# --- Folder shortcut to the stack itself ---
$lnk = $ws.CreateShortcut((Join-Path $folder "Stack folder (config and scripts).lnk"))
$lnk.TargetPath = $stackDir
$lnk.Save()

# --- The how-to guide ---
$guide = @"
MEDIA SERVER - QUICK GUIDE
==========================

OPEN AN APP
  Double-click any of the numbered shortcuts in this folder.
  Main one for requesting movies/TV: "1 - Seerr".

FROM YOUR PHONE (same WiFi)
  Seerr:          http://<this-PC-IP>:5055
  Audiobookshelf: http://<this-PC-IP>:13378
  (Find <this-PC-IP> by running  ipconfig  - look for IPv4 Address.)

AFTER YOU RESTART THE PC
  Everything starts on its own once Docker Desktop finishes loading
  (wait 1-2 minutes). If something doesn't load, use REPAIR below.

IF AN APP WON'T LOAD
  Symptoms: a page won't open, "empty page", or "No such device".
  Fix: double-click  "REPAIR - fix if apps won't load".
  It resets everything cleanly (takes ~2 minutes). Then try the app again.
  TIP: if a page looks stuck on an old version, open it in a Private
  browser window, or press Ctrl+Shift+R to hard-refresh.

TURN EVERYTHING ON MANUALLY
  Double-click  "START - turn everything on".

CHANGE THE VPN LOCATION (for download speed)
  1. Open the Stack folder shortcut, edit the file named  .env
  2. Change the PIA_REGION line (use a port-forwarding region, e.g.
     CA Montreal, CA Vancouver, Netherlands).
  3. In PowerShell in that folder:
        docker compose stop qbittorrent gluetun
        docker compose up -d gluetun qbittorrent
  4. Get the new forwarded port:
        docker compose logs gluetun | findstr forwarded
     and set it in qBittorrent: Options > Connection > incoming port.

DON'T install a separate Windows qBittorrent - the one inside this
stack (behind the VPN) is the only one you need. A second one will
fight it for port 18080.
"@
Set-Content -Path (Join-Path $folder "HOW TO RESTART - read me.txt") -Value $guide -Encoding UTF8

Write-Host ""
Write-Host "Done. Created the 'Media Server' folder on your Desktop." -ForegroundColor Green
Write-Host $folder
