# Media Automation for your Plex server (Windows)

Search for a movie/show **from your phone**, have it download automatically, get
renamed and dropped on your 4TB drive, and show up in **Plex** — which you
already have running. This adds *only* the automation layer; Plex stays as-is.

```
Phone (Seerr) → Prowlarr → Radarr / Sonarr → qBittorrent → 4TB drive → Plex sees it
   search/request     indexers    grab + rename      download      /data/media     (no change)
```

Nothing here uses your friend's API keys — every app makes its own on first run.

---

## What you get

| App | URL (on this PC) | Job |
|---|---|---|
| **Seerr** | http://localhost:5055 | The phone app. Log in with Plex, search, click request. |
| **Radarr** | http://localhost:7878 | Movies: grabs, renames, files them. |
| **Sonarr** | http://localhost:8989 | TV: same, per episode. |
| **Lidarr** | http://localhost:8686 | Music: grabs, tags, files albums. (Optional.) |
| **LazyLibrarian** | http://localhost:5299 | Books/audiobooks auto-grabber (Readarr replacement). (Optional.) |
| **Audiobookshelf** | http://localhost:13378 | Audiobook + ebook player, great phone apps. (Optional.) |
| **Prowlarr** | http://localhost:9696 | Manages all your torrent indexers in one place. |
| **qBittorrent** | http://localhost:18080 | The actual downloader (runs through your PIA VPN). |

---

## Drive layout (important — this is the whole trick)

> ### ⚠️ The drive MUST be internal (SATA/NVMe), NOT USB
> This is the single biggest gotcha. Docker Desktop's WSL2 engine **drops the
> mount on USB drives under write load** — you'll get `No such device`, torrents
> stuck **"Errored"**, and apps that won't keep `/data`. An **internal** drive is
> completely stable. Your big **USB** drives are still great for the Plex
> *library* (Plex reads them natively, no Docker mount involved) — just don't
> point `DATA_DIR` at one. Check with: `Get-Disk | Select FriendlyName, BusType`.

Everything the automation touches lives on **one internal drive**, under one
folder. That keeps downloads and finished media on the *same* volume, so
Radarr/Sonarr import files **instantly** (a hardlink, not a slow copy) and you
can keep seeding without storing the file twice.

Create this on your internal drive (example uses `G:` — adjust to match):

```
G:\MediaStack\
├── downloads\        ← qBittorrent saves here
└── media\
    ├── movies\       ← Radarr's library  → add to Plex
    ├── tv\           ← Sonarr's library  → add to Plex
    └── music\        ← Lidarr's library  → add to Plex
```

Inside the containers this whole folder appears as `/data`, so:

| You see (Windows) | Apps see (container) |
|---|---|
| `G:\MediaStack\downloads` | `/data/downloads` |
| `G:\MediaStack\media\movies` | `/data/media/movies` |
| `G:\MediaStack\media\tv` | `/data/media/tv` |

> Your two **existing** Plex drives are left completely alone. New downloads pile
> up on the 4TB. When you want new stuff to also land on the old drives, see
> **"Adding your other drives"** at the bottom.

---

## Setup — one time

### 1. Install Docker Desktop
Get it from https://www.docker.com/products/docker-desktop/ and install with the
**WSL 2** backend (the default). Reboot if it asks. Launch it once so it's running.

### 2. Make the folders
Create the `H:\MediaStack\downloads`, `media\movies`, and `media\tv` folders above.

### 3. Configure this stack
In this `mediaserver` folder:

1. Copy `.env.example` to `.env`.
2. Open `.env` and set:
   - **`DATA_DIR`** to your 4TB path, e.g. `H:/MediaStack` (forward slashes).
   - **`PIA_USER` / `PIA_PASS`** to your Private Internet Access login.
   - **`PIA_REGION`** to a **port-forwarding** region (most US regions don't
     support it — `CA Toronto` is a safe default). Set `TZ` if not Eastern.

### 4. Start everything
Open **PowerShell** in this folder and run:

```powershell
docker compose up -d
```

First run pulls the images (a few minutes). After that the apps auto-start every
time Windows boots — no Scheduled Tasks needed. Useful commands later:

```powershell
docker compose ps          # what's running
docker compose logs -f     # watch logs
docker compose pull; docker compose up -d   # update all apps
docker compose down        # stop everything
```

---

## After you restart your PC

In normal cases you don't have to do anything: Docker Desktop launches at login
and every container has `restart: unless-stopped`, so the whole stack comes back
on its own. Just wait a minute or two for Docker, then open the apps.

To be sure Docker auto-starts: **Docker Desktop → Settings → General →
"Start Docker Desktop when you sign in"** (checked).

**Two helper scripts are in this folder:**

- **`StartMediaStack.bat`** — double-click to start everything (starts Docker if
  needed, waits for it, runs `docker compose up -d`). Optional: put a shortcut to
  it in your Startup folder (`Win+R` → `shell:startup`) for a guaranteed start.
- **`RepairAndStart.bat`** — run this **only** if an app won't load and you see
  **"No such device"**, an **empty page** (`NS_ERROR_NET_EMPTY_RESPONSE`), or a
  **drive-mount error**. Docker Desktop's WSL2 engine occasionally loses the H:
  drive mount across restarts; this script fully resets the engine
  (Quit Docker → `wsl --shutdown` → reopen Docker → `docker compose up -d`) which
  clears the stale mount. The H: drive must be connected in Windows first.

> The manual version of the repair, if you prefer typing it:
> 1. Quit Docker Desktop (tray icon)
> 2. `wsl --shutdown`
> 3. Reopen Docker Desktop, wait for it to be running
> 4. `docker compose up -d`

---

## Configure the apps — do them in this order

Each app's first screen will ask you to create a login. Then:

### A. qBittorrent (http://localhost:18080)
- **If the page just says "Unauthorized"** (qBittorrent rejecting the remapped
  port via host-header validation), turn that check off once:
  ```powershell
  docker compose stop qbittorrent
  notepad config\qbittorrent\qBittorrent\qBittorrent.conf
  ```
  Under the `[Preferences]` section add `WebUI\HostHeaderValidation=false`, save, then:
  ```powershell
  docker compose start qbittorrent
  ```
  Reload the page and you'll get the login screen. (Safe — it's LAN-only, behind the VPN.)
- Default login is `admin` / a temporary password shown in the logs:
  `docker compose logs qbittorrent` (look for "temporary password"). Change it
  under **Settings → Web UI**.
- **Settings → Downloads → Default Save Path:** set to `/data/downloads`.
- **Confirm the VPN is actually carrying the traffic** (do this once):
  - `docker compose logs gluetun` should show a successful connection and a line
    like `port forwarding is enabled, port = 49xxx`.
  - In qBittorrent, **Settings → Connection → Listening Port**: set it to that
    forwarded port number. (PIA's forwarded port can change if the container
    restarts; if seeding ever looks slow, re-check the gluetun log and update it.)
  - Sanity check that qBittorrent sees the VPN's IP, not yours: the gluetun log
    prints the public IP it connected with — that's the IP your torrents use.

### B. Prowlarr (http://localhost:9696)
- Add your torrent indexers under **Indexers → Add Indexer**.
- Connect it to the others: **Settings → Apps → Add → Radarr** and **Sonarr**.
  Use these addresses (containers talk to each other by name):
  - Radarr: `http://radarr:7878`
  - Sonarr: `http://sonarr:8989`
  - Grab each app's API key from its **Settings → General** page.
  Prowlarr then pushes all indexers into Radarr/Sonarr automatically.

### C. Radarr (http://localhost:7878)
- **Settings → Media Management → Root Folders → Add:** `/data/media/movies`
- **Settings → Download Clients → Add → qBittorrent:** host **`gluetun`**, port `8080`, your qbit login.
  > Use `gluetun`, not `qbittorrent` — qBittorrent shares the VPN container's
  > network, so that's the name other apps reach it by.
- Turn on **Settings → Media Management → "Use Hardlinks instead of Copy"** (default on).

### D. Sonarr (http://localhost:8989)
- Same as Radarr but root folder `/data/media/tv`, and the download client host is
  also **`gluetun`**, port `8080`.

### D2. Lidarr — music (optional, http://localhost:8686)
Same pattern as Radarr/Sonarr, plus a music folder:
- First make the folder on the drive: `H:\MediaStack\media\music`.
- **Settings → Media Management → Root Folders → Add:** `/data/media/music`
- **Settings → Download Clients → Add → qBittorrent:** host **`gluetun`**, port `8080`.
- In **Prowlarr → Settings → Apps → Add → Lidarr** (`http://lidarr:8686`, API key from
  Lidarr → Settings → General) so IPTorrents syncs in.
- Add artists/albums in Lidarr's own UI (Seerr can't request music). Then add
  `H:\MediaStack\media\music` to Plex as a **Music** library; play with Plex or Plexamp.

### D3. Books & audiobooks (optional)

Readarr is retired, so books split into two tools:

**Audiobookshelf (the player) — http://localhost:13378**
- Make folders first: `H:\MediaStack\media\audiobooks` and `H:\MediaStack\media\books`.
- On first launch create an admin account, then **Add Library** →
  point an **Audiobooks** library at `/data/media/audiobooks` and (optionally) a
  **Books** library at `/data/media/books`.
- Install the **Audiobookshelf** app on your phone, point it at
  `http://<this-pc-ip>:13378` (open that port in the firewall like Seerr's).

**LazyLibrarian (the auto-grabber) — http://localhost:5299**
- **Config → Downloaders:** add qBittorrent — host **`gluetun`**, port `8080`,
  your qbit login; set its download dir under `/data/downloads`.
- **Config → Processing:** set the destination to `/data/media/books` (and/or audiobooks).
- **Config → Searching:** add a **Torznab** provider pointing at Prowlarr. In Prowlarr,
  **Settings → Indexers**, open IPTorrents and copy its **Torznab feed URL + API key**,
  paste into LazyLibrarian. (LazyLibrarian doesn't use the Prowlarr "Apps" sync the
  way the \*arrs do — you give it the feed directly.)
- Add authors/books in LazyLibrarian's UI; finished files land in the folder
  Audiobookshelf serves. (Music/books can't be requested from Seerr.)

### E. Seerr (http://localhost:5055) — the phone app
- Sign in with **Plex** → it imports your Plex account and libraries.
- Add Radarr and Sonarr under **Settings → Services** (host `radarr` / `sonarr`,
  their ports, their API keys). Now a phone request flows straight through.

### F. Point Plex at the new media
In Plex: add `H:\MediaStack\media\movies` to your **Movies** library and
`H:\MediaStack\media\tv` to your **TV** library (or make new libraries). When
Radarr/Sonarr finish an import, Plex picks it up — turn on Plex's "Scan my
library automatically," or have Radarr/Sonarr notify Plex under their
**Settings → Connect → Plex Media Server**.

---

## Using it from your phone

Open `http://<this-pc-ip>:5055` in your phone's browser (same as your friend's
`10.0.0.157` trick — use this PC's IP). Log in with Plex, search, tap request.
Done. To reach it you may need a firewall rule, same idea as their note:

```powershell
New-NetFirewallRule -DisplayName "Seerr 5055" -Direction Inbound -Protocol TCP -LocalPort 5055 -Action Allow -Profile Private
```

---

## Adding IPTorrents (your private tracker)

In **Prowlarr → Indexers → Add Indexer**, search **"IPTorrents"** and pick it.
Private trackers don't have a normal API, so Prowlarr logs in with your **browser
session cookie**:

1. Log into `iptorrents.com` in your browser (tick "remember me").
2. **F12 → Application → Cookies → iptorrents.com**, copy the `uid` and `pass` values.
3. In the Prowlarr IPTorrents indexer, paste them into the **Cookie** field as one line:
   ```
   uid=YOUR_UID; pass=YOUR_PASS
   ```
4. **Test** → green → **Save**. It then syncs into Radarr/Sonarr automatically.

Notes for any private tracker:
- The cookie **expires** eventually. When searches suddenly stop, re-grab the
  cookies and update them — that's the only regular maintenance.
- **Ratio matters.** In qBittorrent don't auto-delete finished torrents — let them
  seed. Your PIA port forward (set above) helps your ratio, and the hardlink setup
  means seeding costs no extra disk space.

## VPN — already built in

qBittorrent routes all its traffic through PIA via the `gluetun` container, with a
kill-switch (if the tunnel drops, downloads stop instead of leaking your IP). Set
`PIA_USER` / `PIA_PASS` / `PIA_REGION` in `.env`. Only qBittorrent uses the VPN;
the other apps (and Plex) run normally.

---

## Adding your other drives later

When the 4TB fills up, or you want new movies on the old drives too:

1. In `docker-compose.yml`, add another mount to **radarr** (and/or sonarr), e.g.
   `- D:/Movies:/data2/movies`, then `docker compose up -d`.
2. In Radarr, add `/data2/movies` as a second **Root Folder**.
3. When you add a movie you pick which root folder it goes to. (Note: imports to a
   *different* drive than the download are a copy, not an instant hardlink — that's
   unavoidable across physical drives.)

That's it. If you hit a snag on any step, tell me which app and what you see.
