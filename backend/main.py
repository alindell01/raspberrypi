from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.cache import TTLCache
from backend.providers import nfl, nhl

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

cache = TTLCache(ttl_seconds=5)


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


app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
