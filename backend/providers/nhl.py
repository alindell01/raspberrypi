from typing import Any

import httpx

BASE = "https://api-web.nhle.com/v1"


def _name(value: Any) -> str:
    if isinstance(value, dict):
        return value.get("default", "") or ""
    return value or ""


def _team(payload: dict, side: str) -> dict:
    t = payload.get(f"{side}Team", {}) or {}
    return {
        "name": _name(t.get("name")) or _name(t.get("commonName")) or t.get("abbrev", ""),
        "abbrev": t.get("abbrev", ""),
        "logo": t.get("logo", ""),
        "score": t.get("score", 0) or 0,
        "shots": t.get("sog", 0) or 0,
    }


def _state(s: str) -> str:
    s = (s or "").upper()
    if s in ("LIVE", "CRIT"):
        return "live"
    if s in ("FINAL", "OFF"):
        return "final"
    return "pre"


def _period_label(g: dict) -> str:
    pd = g.get("periodDescriptor") or {}
    n = pd.get("number")
    pt = (pd.get("periodType") or "REG").upper()
    if n is None:
        return ""
    if pt == "OT":
        return "OT"
    if pt == "SO":
        return "SO"
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, str(n))


def _summarize(g: dict) -> dict:
    clock = g.get("clock") or {}
    venue = g.get("venue")
    return {
        "id": str(g.get("id", "")),
        "league": "nhl",
        "state": _state(g.get("gameState", "")),
        "start_time": g.get("startTimeUTC"),
        "venue": _name(venue),
        "home": _team(g, "home"),
        "away": _team(g, "away"),
        "period": (g.get("periodDescriptor") or {}).get("number"),
        "period_label": _period_label(g),
        "clock": clock.get("timeRemaining"),
        "in_intermission": bool(clock.get("inIntermission")),
    }


async def list_games(client: httpx.AsyncClient, date: str | None) -> list[dict]:
    url = f"{BASE}/scoreboard/now" if date is None else f"{BASE}/score/{date}"
    r = await client.get(url)
    r.raise_for_status()
    data = r.json()

    raw: list[dict] = []
    if "gamesByDate" in data:
        for day in data["gamesByDate"]:
            raw.extend(day.get("games", []))
    elif "games" in data:
        raw = data["games"]
    return [_summarize(g) for g in raw]


async def get_game(client: httpx.AsyncClient, game_id: str) -> dict:
    url = f"{BASE}/gamecenter/{game_id}/boxscore"
    r = await client.get(url)
    r.raise_for_status()
    return _summarize(r.json())
