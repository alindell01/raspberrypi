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


class ConfigUpdate(BaseModel):
    league: str | None = None
    date: str | None = None
    game_id: str | None = None
    theme: str | None = None
    delay_seconds: int | None = None
    running: bool | None = None


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


@app.get("/control")
async def control_page():
    return FileResponse(FRONTEND / "control.html")


app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
