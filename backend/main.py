import os
import shutil
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.cache import TTLCache
from backend.providers import nfl, nhl

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

cache = TTLCache(ttl_seconds=5)

KIOSK_SERVICE = os.getenv("SCOREBOARD_KIOSK_SERVICE", "scoreboard-kiosk")
MIRROR_SERVICE = os.getenv("MAGICMIRROR_SERVICE", "magicmirror")


class ConfigUpdate(BaseModel):
    league: str | None = None
    date: str | None = None
    game_id: str | None = None
    theme: str | None = None
    delay_seconds: int | None = None
    running: bool | None = None


class DisplaySwitch(BaseModel):
    target: str  # "scoreboard" or "mirror"


_config_state = {
    "version": 0,
    "config": {
        "league": "nhl",
        "date": None,
        "game_id": None,
        "theme": "auto",
        "delay_seconds": 0,
        "running": False,
    },
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(
        timeout=10.0,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        yield
    finally:
        await app.state.http.aclose()


app = FastAPI(lifespan=lifespan, title="Pi Scoreboard")


@app.exception_handler(httpx.HTTPError)
async def upstream_error(_request, exc: httpx.HTTPError):
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return JSONResponse(
        status_code=502,
        content={"error": "upstream_unavailable", "upstream_status": status, "detail": str(exc)},
    )


@app.get("/api/games")
async def games(league: str = "nhl", date: str | None = None):
    key = f"games:{league}:{date or 'today'}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    if league == "nhl":
        result = await nhl.list_games(app.state.http, date)
    elif league == "nfl":
        result = await nfl.list_games(app.state.http, date)
    else:
        raise HTTPException(400, "Unknown league")
    cache.set(key, result)
    return result


@app.get("/api/game/{league}/{game_id}")
async def game(league: str, game_id: str):
    key = f"game:{league}:{game_id}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    if league == "nhl":
        result = await nhl.get_game(app.state.http, game_id)
    elif league == "nfl":
        result = await nfl.get_game(app.state.http, game_id)
    else:
        raise HTTPException(400, "Unknown league")
    cache.set(key, result)
    return result


@app.get("/api/config")
async def get_config():
    return _config_state


@app.post("/api/config")
async def set_config(update: ConfigUpdate):
    data = update.model_dump(exclude_none=True)
    for key, value in data.items():
        _config_state["config"][key] = value
    _config_state["version"] += 1
    return _config_state


def _systemctl_is_active(service: str) -> bool:
    systemctl = shutil.which("systemctl")
    if not systemctl:
        return False
    try:
        result = subprocess.run(
            [systemctl, "is-active", service],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() == "active"
    except (subprocess.TimeoutExpired, OSError):
        return False


def _run_systemctl(action: str, service: str) -> tuple[bool, str]:
    """Returns (success, message). Tries sudo systemctl first."""
    systemctl = shutil.which("systemctl") or "/bin/systemctl"
    cmd = ["sudo", "-n", systemctl, action, service]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return True, ""
        return False, (result.stderr or result.stdout).strip()
    except subprocess.TimeoutExpired:
        return False, "systemctl timed out"
    except OSError as e:
        return False, str(e)


@app.get("/api/display")
async def get_display():
    return {
        "scoreboard": _systemctl_is_active(KIOSK_SERVICE),
        "mirror":     _systemctl_is_active(MIRROR_SERVICE),
        "kiosk_service":  KIOSK_SERVICE,
        "mirror_service": MIRROR_SERVICE,
    }


@app.post("/api/display")
async def switch_display(req: DisplaySwitch):
    target = (req.target or "").lower()
    if target == "scoreboard":
        stop_svc, start_svc = MIRROR_SERVICE, KIOSK_SERVICE
    elif target == "mirror":
        stop_svc, start_svc = KIOSK_SERVICE, MIRROR_SERVICE
    else:
        raise HTTPException(400, "target must be 'scoreboard' or 'mirror'")

    _run_systemctl("stop", stop_svc)  # ignore stop failures (svc may be missing)
    ok, msg = _run_systemctl("start", start_svc)
    if not ok:
        raise HTTPException(500, f"Failed to start {start_svc}: {msg}")
    return {"target": target, "stopped": stop_svc, "started": start_svc}


@app.get("/control")
async def control_page():
    return FileResponse(FRONTEND / "control.html")


app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
