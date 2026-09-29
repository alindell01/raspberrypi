# Handoff briefing — media server

Context for a fresh Claude session working on this stack. Read this first.

## What this is

A media automation stack on **Windows + Docker Desktop (WSL2)** feeding an
**existing Plex** server. Phone request → auto-download → renamed onto disk →
Plex plays it.

```
Seerr → Prowlarr (indexers) → Radarr/Sonarr/Lidarr → qBittorrent (via PIA VPN) → I:\MediaStack → Plex
```

- Stack folder: **`C:\raspberrypi\mediaserver`**
- Repo: `alindell01/raspberrypi`, branch `claude/personal-media-server-yi9o8p`
- Plex runs **natively on Windows** (not in Docker) and is already set up.

## Services

| Service | Browser URL | Notes |
|---|---|---|
| Seerr | http://localhost:5055 | Request app (successor to Overseerr). Config dir is still `config/overseerr`. |
| Radarr | http://localhost:7878 | Movies → `/data/media/movies` |
| Sonarr | http://localhost:8989 | TV → `/data/media/tv` |
| Lidarr | http://localhost:8686 | Music → `/data/media/music` |
| Prowlarr | http://localhost:9696 | Indexers; syncs into the *arrs via Settings → Apps |
| qBittorrent | http://localhost:18080 | Host 18080 → container 8080 |
| gluetun | — | PIA VPN + port forwarding; qBittorrent uses its network |
| FlareSolverr | http://localhost:8191 | Cloudflare solver for 1337x etc. |
| Audiobookshelf | http://localhost:13378 | Audiobook/ebook player |
| LazyLibrarian | http://localhost:5299 | Book grabber (Readarr is retired) |

## Non-obvious rules — violating these caused most past breakage

1. **`DATA_DIR` is `I:/MediaStack` — on USB, by necessity.** Verified
   2026-09-28 (see Drive map below). The library is ~2 TB; no internal drive
   has room, so USB is the only option. **Do not move it to an internal drive.**
   The known cost: USB can drop the Docker/WSL2 mount under write load
   (`No such device`, errored torrents) → run `RepairAndStart.bat`.
   Always read the live value (`Get-Content .env | Select-String DATA_DIR`)
   rather than trusting a remembered letter.
2. **Never `docker compose up -d --force-recreate <single-service>`** for a
   container that mounts the data drive. It wedges the WSL mount
   (`mkdir /run/desktop/mnt/host/h: file exists`) and can delete the container.
   To fix any mount problem run **`RepairAndStart.bat`** (Quit Docker →
   `wsl --shutdown` → restart Docker → `up -d --force-recreate` for all).
3. **The *arr apps reach qBittorrent at host `gluetun`, port `8080`** — not
   `qbittorrent`, not 18080 — because qBittorrent shares gluetun's network.
4. **Container paths vs Windows paths.** Inside apps: `/data/media/movies`.
   In Windows/Plex: `I:\MediaStack\media\movies`. `/data` == `I:\MediaStack`.
5. **`http://prowlarr:9696` style names are for app-to-app fields only** — never
   in a browser. Browser always uses `localhost:<port>`.
6. **Don't install a native Windows qBittorrent.** One was fighting the Docker
   one for port 18080 and silently receiving the *arr handoffs. It was uninstalled.
7. **Symptom triage:** container `Up` + port shows `0.0.0.0:...` = server fine,
   suspect the browser (hard refresh / private window). Missing port mapping,
   `Restarting`, or `No such device` = run `RepairAndStart.bat`.
8. qBittorrent WebUI showing bare **"Unauthorized"** → set
   `WebUI\HostHeaderValidation=false` under `[Preferences]` in
   `config/qbittorrent/qBittorrent/qBittorrent.conf` (needed because of the
   18080→8080 remap).

## Scripts in this folder

| Script | Purpose |
|---|---|
| `StartMediaStack.bat` | Start Docker + the stack |
| `RepairAndStart.bat` | **The fix for anything weird** — full WSL/Docker reset + recreate |
| `HealthCheck.ps1` | Checks each container + whether its port answers; restarts what's down. `-Repair` auto-runs the full reset |
| `Backup.ps1` | Backs up `config\`, `.env`, optionally Plex DB to an external drive |
| `MakeDesktopShortcuts.ps1` | Builds a Desktop "Media Server" folder of app shortcuts |
| `RESTORE.md` | Rebuild checklist for a fresh Windows install |
| `RUN-CLAUDE-LOCALLY.md` | How this local Claude Code setup was installed |

## Remote access

- **Tailscale** on the PC + phone. Tailscale IP is **`100.71.148.20`**
  (re-registered after the SSD swap — it used to be 100.71.198.95, so any older
  bookmark is stale). Apps are reachable at `http://100.71.148.20:<port>`.
- The HTTPS name `https://desktop-4tl435v.tail513bc9.ts.net` only covers Seerr and
  only while a `tailscale serve` mapping exists — that must be re-run after the
  reinstall, and the machine name may have changed if the old node wasn't removed
  from the tailnet. Verify with `tailscale status` / `tailscale serve status`.
- LAN: `http://<pc-ip>:5055`. PC was `192.168.86.41` before the rebuild — re-check
  with `ipconfig` (wired, gateway 192.168.86.1,
  Google/Nest WiFi — set a DHCP reservation so it stops moving).
- Needs the Ethernet profile set to **Private** + a firewall rule allowing
  TCP 5055,13378,7878,8989,9696,8686,18080.

## Current state (as of this handoff)

The **Windows SSD was replaced** and Windows reinstalled. Config was backed up
with `Backup.ps1` to an external drive (verified: `radarr.db`, `sonarr.db`,
`prowlarr.db`, `overseerr/db/db.sqlite3`, `.env` all present). Media on G: and
the USB drives was untouched.

### Open items
1. **Verify the restore**: all containers `Up`,
   `docker compose exec qbittorrent ls /data/downloads` lists files, and the
   media drive is still lettered **G:** (must match `DATA_DIR`).
2. **Redo Windows-side setup** (lost with the old install): disk sleep = Never,
   USB selective suspend off, Ethernet profile Private, firewall rule, DHCP
   reservation, Tailscale + `tailscale serve`, HealthCheck scheduled task,
   desktop shortcuts.
3. **Re-seed for ratio**: IPTorrents ratio took a hit during the migration.
   Plan is **Set location → Force recheck** on errored torrents so they resume
   seeding without re-downloading. Set location FIRST — rechecking against a
   wrong path marks them 0% and re-downloads. Files must live under
   `I:\MediaStack\downloads` (qBittorrent can't see outside `/data`).
   Also: prefer **freeleech** on IPTorrents; public indexers (1337x etc., via
   FlareSolverr) have no ratio requirement.
4. **Quality tuning (optional)**: allow 2160p in the Radarr/Sonarr quality
   profiles but cap 2160p **Max ≈ 300 MB/min** in Quality Definitions, so 4K is
   possible without 60–90 GB remuxes. Exclude Bluray-2160p Remux.
5. **Stuck import**: a "Haunted Mansion 2023 REPACK" download completed but
   Radarr said *"No video files were found in the selected folder"* — likely a
   RAR-packed or fake release. Inspect the folder; if RAR/junk, blocklist it and
   Interactive Search a different release.
6. **Finish LazyLibrarian**: installed but never fully configured, so book
   grabbing doesn't work. Needs a downloader (`gluetun:8080`), processing
   destinations under `/data/media`, and — the usual missing piece — a
   **Torznab feed pasted in manually** (it does not use Prowlarr's Apps sync).
   Step-by-step in **`LAZYLIBRARIAN.md`**. Low-effort alternative for
   audiobooks: drop files into `I:\MediaStack\media\audiobooks\<Author>\<Title>\`
   and let Audiobookshelf scan them.


---

## Drive map — verified 2026-09-28

After the SSD swap, **every large drive is USB**; the only internal drives are
C: and D:, neither big enough for the library.

| Letter | Bus | Label | Free | Role |
|---|---|---|---|---|
| C: | NVMe (internal) | — | 811 GB | Windows |
| D: | SATA (internal) | — | 100 GB | — |
| E: | USB | Boxofawesomeness2 | 459 GB | — |
| F: | USB | Plex | 1781 GB | Plex library storage |
| G: | USB | Data | 149 GB | empty |
| H: | USB | Acer | 637 GB | old Windows install |
| **I:** | **USB** | **boxofawesomeness** | **2650 GB** | **`DATA_DIR` — the live library** |

Library on I: — movies 577 GB, tv 886 GB, music 76 GB, audiobooks 2.6 GB,
downloads 800 GB (≈2.0 TB used, 2.6 TB free).

**False alarm worth remembering:** `G:\MediaStack` looked empty and was mistaken
for the live path, because the setup README uses `G:\MediaStack` as its *example*.
The authoritative source is always `.env`, not the docs and not Explorer.

## Pending manual cleanup

Both verified byte-for-byte as duplicates/empty, safe to delete, but an agent's
guardrails blocked removing drive-root folders — **delete these by hand**:

- `C:\MediaStack` — 26.7 GB stale duplicate from a briefly mis-set `DATA_DIR`
  during the reinstall; all content also exists on I:.
- `G:\MediaStack` — empty folder.

## Git is not attached on the PC

`C:\raspberrypi\mediaserver` on the machine is **not a git repo** after the
rebuild (files were restored from the backup copy, not cloned), so local doc
edits are not versioned or pushed. Re-attach it to
`github.com/alindell01/raspberrypi`, branch `claude/personal-media-server-yi9o8p`,
**without overwriting local files** (fetch + mixed reset, then review and commit).
