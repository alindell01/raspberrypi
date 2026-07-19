# Restoring the media server on a new Windows SSD

**Your media is safe.** It lives on the internal **G:** drive (WDC 1TB) and the
**USB** drives — NOT on the dying **C:** SSD. When you rebuild:

> ⚠️ Replace ONLY the C: SSD. Do **NOT** format or wipe G: or the USB drives.
> Their movies/TV/music/books stay exactly where they are.

## What the backup contains (from Backup.ps1)
- `mediaserver\` — the whole stack: `docker-compose.yml`, the scripts, your `.env`
  (PIA login + `DATA_DIR`), and **`config\`** = every app's database, API keys,
  indexers, IPTorrents cookie, Prowlarr links, Seerr users, qBittorrent settings.
- `Plex Media Server\` (if you ran `-IncludePlex`) — Plex's library DB + settings
  (watch history, collections, library layout).

## Steps on the fresh Windows install
1. Install Windows on the **new** SSD. Leave G: and the USB drives untouched.
2. **Check drive letters.** The 1TB media drive **must be `G:`** (that's what
   `DATA_DIR=G:/MediaStack` in `.env` points at). If Windows gave it another
   letter, fix it in **Disk Management → Change Drive Letter → G**, or edit
   `.env`'s `DATA_DIR` to match. Do the same for the drives your Plex libraries use.
3. Install: **Docker Desktop** (WSL2 backend), **Git**, **Node.js**. Reboot.
4. Copy the backed-up **`mediaserver`** folder from the external drive to
   **`C:\raspberrypi\mediaserver`** (restores code + config + .env together).
5. Bring it up:
   ```powershell
   cd C:\raspberrypi\mediaserver
   docker compose up -d
   ```
   Every app returns with its settings intact, because `config\` was restored.
6. Re-do the Windows-side setup (details in `README.md`):
   - Power Options → **Turn off hard disk after = Never**.
   - Set the wired network profile to **Private**.
   - Re-add the **firewall** rule for the phone ports.
   - **Static IP / DHCP reservation** for the PC.
   - Install **Tailscale**, sign in, re-run `tailscale serve` for the HTTPS URL
     (`https://desktop-4tl435v.tail513bc9.ts.net`).
   - (Optional) re-register the **HealthCheck** scheduled task.
   - Reinstall the **Claude Code** CLI (`npm install -g @anthropic-ai/claude-code`).
7. **Plex:** reinstall Plex Media Server. To keep your library + history, stop Plex,
   replace the fresh `%LOCALAPPDATA%\Plex Media Server` folder with the backed-up
   one, start Plex, and confirm the libraries point at the right G:/USB folders.

## Sanity check after restore
```powershell
docker compose ps                                   # all containers Up
docker compose exec qbittorrent ls /data/downloads  # lists files = G: mount OK
```
Open Seerr / Radarr / Sonarr — your indexers, users, and history should all be there.
If an app can't see `/data`, run `RepairAndStart.bat` (the usual mount reset).
