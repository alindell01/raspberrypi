# Media server — project memory

A Windows + Docker Desktop (WSL2) media automation stack feeding an existing
**Plex** server (Plex runs natively on Windows, not in Docker).

**Read `HANDOFF.md` in this folder for the full briefing** — services, ports,
scripts, remote access, and the current open items. This file is the short
always-loaded version.

## Rules that must not be broken

1. **`DATA_DIR` must be an INTERNAL (SATA/NVMe) drive** — currently
   `G:/MediaStack`. USB drives lose the Docker/WSL2 mount under write load
   (`No such device`, torrents "Errored"). The 5TB `H:` is USB — never use it
   for `DATA_DIR`. USB is fine for Plex library storage.
2. **Never `docker compose up -d --force-recreate <one-service>`** for a
   container that mounts the data drive — it wedges the WSL mount
   (`mkdir /run/desktop/mnt/host/h: file exists`) and can delete the container.
   Any mount problem → run **`RepairAndStart.bat`** (full reset).
3. **The *arr apps reach qBittorrent at `gluetun:8080`** — not `qbittorrent`,
   not 18080. qBittorrent shares gluetun's (VPN) network.
4. **Paths:** inside containers `/data/...`; in Windows/Plex
   `G:\MediaStack\...`. `/data` == `G:\MediaStack`.
5. **`http://prowlarr:9696`-style names are for app-to-app config fields only** —
   in a browser always use `localhost:<port>`.
6. **No native Windows qBittorrent** — it fights the Docker one for port 18080.

## Triage shortcut

- Container `Up` + port shows `0.0.0.0:...` → server is fine, suspect the
  browser (hard refresh / private window).
- Missing port mapping, `Restarting`, `Exited`, or `No such device` →
  `RepairAndStart.bat`.
- `HealthCheck.ps1` checks every container + whether its port answers, and
  restarts what's down.

## Keeping this current

When we learn a new gotcha or finish an open item, update `HANDOFF.md` (and this
file if it's a hard rule) and commit — that's how the knowledge persists across
sessions.
