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

# Full shell commands so users can plug in whatever fits their setup
# (systemd, pm2, raw chromium-kiosk, etc.). Defaults use systemctl.
KIOSK_START_CMD  = os.getenv("SCOREBOARD_KIOSK_START_CMD",  f"sudo -n systemctl start {KIOSK_SERVICE}")
KIOSK_STOP_CMD   = os.getenv("SCOREBOARD_KIOSK_STOP_CMD",   f"sudo -n systemctl stop {KIOSK_SERVICE}")
KIOSK_ACTIVE_CMD = os.getenv("SCOREBOARD_KIOSK_ACTIVE_CMD", f"sudo -n systemctl is-active {KIOSK_SERVICE}")

MIRROR_START_CMD  = os.getenv("MAGICMIRROR_START_CMD",  f"sudo -n systemctl start {MIRROR_SERVICE}")
MIRROR_STOP_CMD   = os.getenv("MAGICMIRROR_STOP_CMD",   f"sudo -n systemctl stop {MIRROR_SERVICE}")
MIRROR_ACTIVE_CMD = os.getenv("MAGICMIRROR_ACTIVE_CMD", f"sudo -n systemctl is-active {MIRROR_SERVICE}")


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


def _run_shell(cmd: str, timeout: int = 15) -> tuple[bool, str]:
    """Run a configured display-control shell command. Returns (ok, msg)."""
    if not cmd:
        return True, ""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0:
            return True, ""
        return False, (result.stderr or result.stdout).strip()
    except subprocess.TimeoutExpired:
        return False, "command timed out"
    except OSError as e:
        return False, str(e)


def _is_active(check_cmd: str) -> bool:
    if not check_cmd:
        return False
    try:
        result = subprocess.run(
            check_cmd, shell=True, capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return False
        out = (result.stdout or "").strip().lower()
        return out == "active" or out.startswith("active")
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
        "scoreboard":     _is_active(KIOSK_ACTIVE_CMD),
        "mirror":         _is_active(MIRROR_ACTIVE_CMD),
        "kiosk_service":  KIOSK_SERVICE,
        "mirror_service": MIRROR_SERVICE,
    }


@app.post("/api/display")
async def switch_display(req: DisplaySwitch):
    target = (req.target or "").lower()
    if target == "scoreboard":
        stop_cmd, start_cmd = MIRROR_STOP_CMD, KIOSK_START_CMD
    elif target == "mirror":
        stop_cmd, start_cmd = KIOSK_STOP_CMD, MIRROR_START_CMD
    else:
        raise HTTPException(400, "target must be 'scoreboard' or 'mirror'")

    _run_shell(stop_cmd)  # tolerate stop failures - target may not be running
    ok, msg = _run_shell(start_cmd)
    if not ok:
        raise HTTPException(500, f"Failed to start {target}: {msg}")
    return {"target": target}


@app.get("/control")
async def control_page():
    return FileResponse(FRONTEND / "control.html")


app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
