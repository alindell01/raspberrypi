"""Torrent relay: receive magnet links / .torrent files from a phone and
hand them to qBittorrent's Web API on the PC.

Runs as its own tiny FastAPI app (separate from the scoreboard backend) so
it can live on whatever machine qBittorrent runs on. It serves an
installable PWA "share target" page: on Android you tap Share on a magnet
link and pick this app, and the link lands in qBittorrent automatically.
Magnet links can't go through a watch folder, which is why this exists --
for plain .torrent *files* the qBittorrent watch folder (see README) is
enough.
"""

import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("torrentrelay")

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

# Where to reach qBittorrent's Web UI and how to log in. Defaults match a
# fresh qBittorrent install; override with env vars (see deploy unit / README).
QB_URL      = os.getenv("QB_URL", "http://localhost:8080").rstrip("/")
QB_USERNAME = os.getenv("QB_USERNAME", "admin")
QB_PASSWORD = os.getenv("QB_PASSWORD", "adminadmin")
# Optional add-time overrides; blank means "use qBittorrent's defaults".
QB_SAVEPATH = os.getenv("QB_SAVEPATH", "")
QB_CATEGORY = os.getenv("QB_CATEGORY", "")
QB_PAUSED   = os.getenv("QB_PAUSED", "false")

MAGNET_RE      = re.compile(r"magnet:\?[^\s\"'<>]+", re.IGNORECASE)
TORRENT_URL_RE = re.compile(r"https?://[^\s\"'<>]+\.torrent\b[^\s\"'<>]*", re.IGNORECASE)


class QbError(Exception):
    """Something went wrong talking to qBittorrent."""


class QbClient:
    """Minimal async client for the qBittorrent Web API (v2)."""

    def __init__(self, base: str, username: str, password: str):
        self.base = base
        self.username = username
        self.password = password
        # qBittorrent rejects requests whose Referer host doesn't match, as
        # CSRF protection -- so we always send one.
        self._client = httpx.AsyncClient(timeout=30.0, headers={"Referer": base})
        self._logged_in = False

    async def login(self) -> None:
        try:
            r = await self._client.post(
                f"{self.base}/api/v2/auth/login",
                data={"username": self.username, "password": self.password},
            )
        except httpx.HTTPError as e:
            raise QbError(f"Can't reach qBittorrent at {self.base} ({e})") from e
        if r.status_code == 403:
            raise QbError("qBittorrent temporarily banned this client (too many failed logins)")
        if r.text.strip() != "Ok.":
            raise QbError("qBittorrent login failed -- check QB_USERNAME / QB_PASSWORD")
        self._logged_in = True

    async def _ensure_login(self) -> None:
        if not self._logged_in:
            await self.login()

    async def add(self, urls: list[str] | None = None,
                  files: list[tuple[str, bytes]] | None = None) -> None:
        await self._ensure_login()
        data: dict[str, str] = {"paused": QB_PAUSED}
        if urls:
            data["urls"] = "\n".join(urls)
        if QB_SAVEPATH:
            data["savepath"] = QB_SAVEPATH
        if QB_CATEGORY:
            data["category"] = QB_CATEGORY
        file_payload = None
        if files:
            file_payload = [
                ("torrents", (name, content, "application/x-bittorrent"))
                for name, content in files
            ]

        async def _post():
            return await self._client.post(
                f"{self.base}/api/v2/torrents/add", data=data, files=file_payload
            )

        try:
            r = await _post()
            if r.status_code == 403:  # session expired -- re-auth once and retry
                self._logged_in = False
                await self._ensure_login()
                r = await _post()
        except httpx.HTTPError as e:
            raise QbError(f"Can't reach qBittorrent at {self.base} ({e})") from e

        if r.status_code != 200 or r.text.strip().lower() == "fails.":
            raise QbError(f"qBittorrent rejected the torrent (HTTP {r.status_code})")

    async def version(self) -> str:
        await self._ensure_login()
        r = await self._client.get(f"{self.base}/api/v2/app/version")
        return r.text.strip()

    async def aclose(self) -> None:
        await self._client.aclose()


def _extract_links(*blobs: str | None) -> list[str]:
    """Pull magnet links and .torrent URLs out of shared text, de-duped."""
    found: list[str] = []
    for blob in blobs:
        if not blob:
            continue
        found += MAGNET_RE.findall(blob)
        found += TORRENT_URL_RE.findall(blob)
    seen: set[str] = set()
    ordered = []
    for link in found:
        if link not in seen:
            seen.add(link)
            ordered.append(link)
    return ordered


async def _collect_and_add(text: str | None, url: str | None,
                           upload: UploadFile | None) -> dict:
    links = _extract_links(text, url)
    files: list[tuple[str, bytes]] = []
    if upload is not None and upload.filename:
        content = await upload.read()
        if content:
            files.append((upload.filename, content))
    if not links and not files:
        raise HTTPException(400, "No magnet link or .torrent found in what you sent")
    await app.state.qb.add(urls=links or None, files=files or None)
    return {"ok": True, "added_links": links, "added_files": [f[0] for f in files]}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.qb = QbClient(QB_URL, QB_USERNAME, QB_PASSWORD)
    try:
        yield
    finally:
        await app.state.qb.aclose()


app = FastAPI(lifespan=lifespan, title="Torrent Relay")


@app.get("/healthz")
async def healthz():
    """Confirm qBittorrent is reachable and the credentials work."""
    try:
        version = await app.state.qb.version()
    except QbError as e:
        raise HTTPException(502, str(e))
    return {"ok": True, "qbittorrent": version, "qb_url": QB_URL}


@app.post("/api/add")
async def api_add(
    text: str | None = Form(default=None),
    torrent: UploadFile | None = File(default=None),
):
    """Used by the in-page paste box (returns JSON)."""
    try:
        return await _collect_and_add(text, None, torrent)
    except QbError as e:
        raise HTTPException(502, str(e))


@app.post("/share")
async def share_target(
    title: str | None = Form(default=None),
    text: str | None = Form(default=None),
    url: str | None = Form(default=None),
    torrent: UploadFile | None = File(default=None),
):
    """Android share-sheet target. Adds the torrent then bounces back to the
    page with a status so the user sees a confirmation."""
    try:
        result = await _collect_and_add(text or title, url, torrent)
    except HTTPException as e:
        return RedirectResponse(f"/?status=error&msg={e.detail}", status_code=303)
    except QbError as e:
        return RedirectResponse(f"/?status=error&msg={e}", status_code=303)
    count = len(result["added_links"]) + len(result["added_files"])
    return RedirectResponse(f"/?status=ok&count={count}", status_code=303)


# Serve the PWA from the root so the service worker scope covers "/" (needed
# for the share target). Mount last so the API routes above take priority.
app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")
