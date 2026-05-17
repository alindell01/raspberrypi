from typing import Any
import asyncio

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
        # /scoreboard/now returns a window of days. Pin to NHL's "focused"
        # date so we don't surface last week's games when today has none.
        focus = data.get("focusedDate")
        for day in data["gamesByDate"]:
            if focus and day.get("date") != focus:
                continue
            raw.extend(day.get("games", []))
        # Fall back to all days if the focused-date filter produced nothing
        # (shouldn't happen, but don't show a blank picker on a quirky day).
        if not raw:
            for day in data["gamesByDate"]:
                raw.extend(day.get("games", []))
    elif "games" in data:
        raw = data["games"]
    return [_summarize(g) for g in raw]


def _initials(first: Any, last: Any) -> str:
    first = _name(first)
    last = _name(last)
    if first and last:
        return f"{first[0]}. {last}"
    return last or first or ""


def _extract_last_goal(landing: dict) -> str | None:
    scoring = (landing.get("summary") or {}).get("scoring") or []
    for period in reversed(scoring):
        goals = period.get("goals") or []
        for goal in reversed(goals):
            scorer = _initials(goal.get("firstName"), goal.get("lastName"))
            team_abbrev = goal.get("teamAbbrev")
            team = _name(team_abbrev) if isinstance(team_abbrev, dict) else (team_abbrev or "")
            total = goal.get("goalsToDate")
            assists = goal.get("assists") or []
            names = [
                _initials(a.get("firstName"), a.get("lastName"))
                for a in assists
                if _initials(a.get("firstName"), a.get("lastName"))
            ]
            head = f"{team} GOAL" if team else "GOAL"
            scorer_part = f"{scorer} ({total})" if total else scorer
            assist_part = f" — A: {', '.join(names)}" if names else " (unassisted)"
            return f"{head}: {scorer_part}{assist_part}".strip()
    return None


def _extract_last_penalty(landing: dict) -> str | None:
    pens = (landing.get("summary") or {}).get("penalties") or []
    for period in reversed(pens):
        items = period.get("penalties") or []
        for p in reversed(items):
            committed = _initials(p.get("committedByPlayer", {}).get("firstName"),
                                  p.get("committedByPlayer", {}).get("lastName"))
            team_abbrev = p.get("teamAbbrev")
            team = _name(team_abbrev) if isinstance(team_abbrev, dict) else (team_abbrev or "")
            duration = p.get("duration") or p.get("durationMinutes")
            desc = _name(p.get("descKey")) or p.get("type") or "penalty"
            return f"{team} PENALTY: {committed} — {desc} ({duration}m)".strip()
    return None


async def get_game(client: httpx.AsyncClient, game_id: str) -> dict:
    box_url = f"{BASE}/gamecenter/{game_id}/boxscore"
    landing_url = f"{BASE}/gamecenter/{game_id}/landing"
    box_r, landing_r = await asyncio.gather(
        client.get(box_url),
        client.get(landing_url),
        return_exceptions=True,
    )
    if isinstance(box_r, Exception):
        raise box_r
    box_r.raise_for_status()
    game = _summarize(box_r.json())

    if not isinstance(landing_r, Exception) and landing_r.status_code == 200:
        try:
            landing = landing_r.json()
            game["last_goal"] = _extract_last_goal(landing)
            game["last_penalty"] = _extract_last_penalty(landing)
        except Exception:
            pass
    return game
