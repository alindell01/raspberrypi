# Torrent Relay — send torrents from your phone to qBittorrent

Two ways to get a torrent from your phone onto the PC running qBittorrent:

1. **`.torrent` files → qBittorrent watch folder** (no code, set up in qBittorrent).
2. **Magnet links → this relay app** (a small web page you "Share" to from your
   phone). Magnet links aren't files, so a watch folder can't handle them — that's
   what the relay is for. It also accepts `.torrent` files if you'd rather use one tool.

---

## Part 1 — qBittorrent settings (do this once)

### Enable the Web UI (required for the relay)
1. qBittorrent → **Tools → Options → Web UI**.
2. Tick **Web User Interface (Remote control)**.
3. Port **8080** (default).
4. Set a username/password (or tick *Bypass authentication for clients on localhost*
   if the relay runs on the same machine).
5. Apply. Test in a browser: `http://<pc-ip>:8080`.

### Enable the watch folder (the no-code `.torrent` path)
1. qBittorrent → **Tools → Options → Downloads**.
2. Under **Automatically add torrents from:** click **Add** and pick a folder,
   e.g. `~/torrents/watch` (Windows: `C:\Users\you\torrents\watch`).
3. Choose where the downloaded data should go. Apply.

Drop any `.torrent` file into that folder and it downloads automatically.

### Make the watch folder reachable from your phone (optional but slick)
Install **Syncthing** on the PC and phone, share the `~/torrents/watch` folder.
Saving a `.torrent` into that synced folder on the phone makes it appear on the PC,
where qBittorrent picks it up. No cloud, no relay needed for `.torrent` files.

---

## Part 2 — the relay (magnet links from the phone share sheet)

Runs as a tiny FastAPI app on the same machine/network as qBittorrent.

### Windows 11 — step by step (recommended)
1. **Install Python** (if you don't have it): `winget install Python.Python.3.12`
   (or from python.org — tick *Add python.exe to PATH*). Verify in a new
   terminal: `python --version`.
2. **Install the dependencies.** Open PowerShell in the repo folder and run:
   ```powershell
   python -m pip install -r requirements.txt
   ```
3. **Open the firewall** so your phone can reach the relay. Right-click
   `torrentrelay\windows\allow-firewall.ps1` → **Run with PowerShell** (accept the
   admin prompt). It adds the rule and prints your PC's IP address.
4. **Set your password and start it.** Open `torrentrelay\windows\start-relay.bat`
   in Notepad, change `QB_PASSWORD=CHANGE_ME` to your qBittorrent Web UI password,
   save, then **double-click the .bat**. A window opens and stays open while the
   relay runs.
5. **Verify:** in a browser on the PC, open `http://localhost:8800/healthz` — it
   should show the qBittorrent version.
6. **From your phone** (same Wi-Fi), open `http://<your-pc-ip>:8800` (the IP the
   firewall script printed, e.g. `http://192.168.1.50:8800`), then install it
   (see below).

#### Start the relay automatically at login (Windows)
Press <kbd>Win</kbd>+<kbd>R</kbd>, type `shell:startup`, Enter. Right-click
`start-relay.bat` → **Copy**, then paste a **shortcut** to it into that Startup
folder. It'll launch when you log in. (To hide the console window, set the
shortcut's *Run* to *Minimized*.)

### Run it (Linux / macOS)
From the repo root (after `pip install -r requirements.txt`, or the project venv):

```bash
QB_URL=http://localhost:8080 QB_USERNAME=admin QB_PASSWORD=yourpass \
  python -m uvicorn torrentrelay.main:app --host 0.0.0.0 --port 8800
```

Check it's wired up: open `http://<pc-ip>:8800/healthz` — it should report the
qBittorrent version. Then open `http://<pc-ip>:8800` on your phone (same Wi-Fi).

### Configuration (env vars)
| Var | Default | Meaning |
|-----|---------|---------|
| `QB_URL` | `http://localhost:8080` | qBittorrent Web UI base URL |
| `QB_USERNAME` | `admin` | Web UI username |
| `QB_PASSWORD` | `adminadmin` | Web UI password |
| `QB_SAVEPATH` | *(qB default)* | force a download location for phone adds |
| `QB_CATEGORY` | *(none)* | tag phone adds with a qB category |
| `QB_PAUSED` | `false` | add torrents paused instead of starting |

### Install on your phone (Android / Chrome)
1. Open `http://<pc-ip>:8800` in Chrome.
2. **Menu → Add to Home screen / Install**.
3. Now **“Send to qBittorrent”** appears in the system **Share** sheet. Tap Share
   on any magnet link (or `.torrent`) and choose it — it lands in qBittorrent and
   you get a confirmation.

On **iPhone**, Safari doesn't support PWA share targets — just open the page and
paste the magnet into the box (or build a Shortcut that POSTs to `/api/add`).

### Run on boot (Linux / Raspberry Pi)
A systemd unit is provided at `deploy/torrentrelay.service`. Edit the `Environment=`
lines, then:

```bash
sudo sed -e "s|__USER__|$USER|g" -e "s|__REPO__|$(pwd)|g" \
  deploy/torrentrelay.service | sudo tee /etc/systemd/system/torrentrelay.service
sudo systemctl daemon-reload
sudo systemctl enable --now torrentrelay
```

---

## Using it away from home
The steps above are LAN-only (phone and PC on the same Wi-Fi), which is the safest
default. To use it from anywhere, don't expose qBittorrent/the relay directly to the
internet — instead use a VPN back home (WireGuard / Tailscale) or a reverse proxy
with HTTPS + authentication. Ask and I can set up Tailscale or a Caddy proxy.

## API (for scripts / Shortcuts)
- `POST /api/add` — multipart form: `text` (magnet/URL) and/or `torrent` (file). Returns JSON.
- `POST /share` — the PWA share-target endpoint (redirects back to the page).
- `GET /healthz` — qBittorrent connectivity check.
