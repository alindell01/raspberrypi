from typing import Any

import httpx

BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"


def _team(competitor: dict) -> dict:
    team = competitor.get("team") or {}
    records = competitor.get("records") or []
    record = records[0].get("summary", "") if records else ""
    logos = team.get("logos") or []
    logo = team.get("logo") or (logos[0].get("href") if logos else "")
    return {
        "id": str(team.get("id", "")),
        "name": team.get("displayName") or team.get("name") or team.get("abbreviation", ""),
        "abbrev": team.get("abbreviation", ""),
        "logo": logo,
        "score": int(competitor.get("score", 0) or 0),
        "record": record,
        "timeouts": competitor.get("timeoutsUsed"),
    }


def _state(s: str) -> str:
    return {"in": "live", "post": "final", "pre": "pre"}.get((s or "pre").lower(), "pre")


def _period_label(status: dict) -> str:
    p = status.get("period")
    if not p:
        return ""
    if p >= 5:
        return "OT"
    return {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}.get(p, str(p))


def _situation(s: Any) -> dict:
    if not s or not isinstance(s, dict):
        return {}
    last = s.get("lastPlay") or {}
    return {
        "down_distance": s.get("downDistanceText", ""),
        "yardline": s.get("possessionText", ""),
        "possession": s.get("possession"),
        "last_play": last.get("text", "") if isinstance(last, dict) else "",
    }


def _summarize(event: dict) -> dict:
    comp = (event.get("competitions") or [{}])[0]
    competitors = comp.get("competitors", []) or []
    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), {})
    status = comp.get("status") or event.get("status") or {}
    type_state = ((status.get("type") or {}).get("state")) or "pre"
    venue = comp.get("venue") or {}

    return {
        "id": str(event.get("id", "")),
        "league": "nfl",
        "state": _state(type_state),
        "start_time": comp.get("date") or event.get("date"),
        "venue": venue.get("fullName", ""),
        "home": _team(home),
        "away": _team(away),
        "period": status.get("period"),
        "period_label": _period_label(status),
        "clock": status.get("displayClock"),
        "situation": _situation(comp.get("situation")),
    }


async def list_games(client: httpx.AsyncClient, date: str | None) -> list[dict]:
    params: dict[str, str] = {}
    if date:
        params["dates"] = date.replace("-", "")
    r = await client.get(f"{BASE}/scoreboard", params=params)
    r.raise_for_status()
    events = r.json().get("events", []) or []
    return [_summarize(e) for e in events]


async def get_game(client: httpx.AsyncClient, game_id: str) -> dict:
    r = await client.get(f"{BASE}/summary", params={"event": game_id})
    r.raise_for_status()
    data = r.json()
    header = data.get("header") or {}
    comps = header.get("competitions") or [{}]
    # Re-shape so _summarize can handle it identically.
    return _summarize({
        "id": header.get("id") or game_id,
        "competitions": comps,
        "date": comps[0].get("date") if comps else None,
    })
