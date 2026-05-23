from typing import Any
import asyncio

import httpx

BASE = "https://api-web.nhle.com/v1"

# Static venue → photo map. Add more arenas as we collect official-CDN URLs.
# The Pi browser fetches these directly; the dev container can't (egress
# allowlist), but that's fine.
VENUE_IMAGES: dict[str, str] = {
    "KeyBank Center": "https://media.d3.nhle.com/image/private/t_ratio16_9-size50/prd/cppi5ukgfjdmtvl4wlra.jpg",
}


def _name(value: Any) -> str:
    if isinstance(value, dict):
        return value.get("default", "") or ""
    return value or ""


def _team(payload: dict, side: str) -> dict:
    t = payload.get(f"{side}Team", {}) or {}
    record = t.get("record") or ""
    return {
        "id": str(t.get("id", "")),
        "name": _name(t.get("name")) or _name(t.get("commonName")) or t.get("abbrev", ""),
        "abbrev": t.get("abbrev", ""),
        "logo": t.get("logo", ""),
        "score": t.get("score", 0) or 0,
        "shots": t.get("sog", 0) or 0,
        "record": record,
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
    venue_name = _name(venue)
    return {
        "id": str(g.get("id", "")),
        "league": "nhl",
        "state": _state(g.get("gameState", "")),
        "start_time": g.get("startTimeUTC"),
        "venue": venue_name,
        "venue_image": VENUE_IMAGES.get(venue_name, ""),
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
        focus = data.get("focusedDate")
        for day in data["gamesByDate"]:
            if focus and day.get("date") != focus:
                continue
            raw.extend(day.get("games", []))
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


def _extract_series(landing: dict) -> dict | None:
    """Playoff round / game-of-series info, if present."""
    s = landing.get("seriesStatus") or {}
    rnd = s.get("round")
    game_no = s.get("gameNumberOfSeries") or s.get("gameNumber")
    if not rnd and not game_no:
        return None
    top_wins = s.get("topSeedWins")
    bot_wins = s.get("bottomSeedWins")
    top = (s.get("topSeedTeam") or {}).get("abbrev") or ""
    bot = (s.get("bottomSeedTeam") or {}).get("abbrev") or ""
    label_parts = []
    if rnd:
        label_parts.append(f"ROUND {rnd}")
    if game_no:
        label_parts.append(f"GAME {game_no}")
    out: dict[str, Any] = {"label": " · ".join(label_parts)}
    if top and bot and top_wins is not None and bot_wins is not None:
        out["series_score"] = f"{top} {top_wins} – {bot_wins} {bot}"
    return out


def _person_name(value: Any) -> str:
    """Normalize NHL person-name fields, which appear as either
    {default: 'Lindy Ruff'}, {firstName: {default}, lastName: {default}},
    or a plain string."""
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ""
    if "default" in value:
        v = value.get("default")
        return v.strip() if isinstance(v, str) else ""
    first = value.get("firstName") or {}
    last = value.get("lastName") or {}
    if isinstance(first, dict): first = first.get("default", "")
    if isinstance(last,  dict): last  = last.get("default", "")
    return f"{first or ''} {last or ''}".strip()


def _preview_from_landing(landing: dict) -> dict | None:
    """Pregame info from the matchup section: head coaches, scratches,
    last-10 records, head-to-head season series, and — for playoffs —
    the series round / game number / series score."""
    matchup = landing.get("matchup") or {}
    gi = (matchup.get("gameInfo") or {})

    def scratches(side: dict) -> list[dict]:
        out = []
        for s in (side.get("scratches") or []):
            name = _person_name(s) or _person_name({
                "firstName": s.get("firstName"),
                "lastName":  s.get("lastName"),
            })
            if name:
                out.append({"name": name, "position": s.get("position", "")})
        return out

    away_gi = gi.get("awayTeam") or {}
    home_gi = gi.get("homeTeam") or {}

    last10 = matchup.get("last10Record") or {}
    season = matchup.get("season") or {}

    def side(team_key: str, gi_side: dict) -> dict:
        return {
            "coach":         _person_name(gi_side.get("headCoach")),
            "scratches":     scratches(gi_side),
            "last10":        (last10.get(team_key) or {}).get("record", ""),
            "season_record": (season.get(team_key) or {}).get("record", ""),
        }

    away = side("awayTeam", away_gi)
    home = side("homeTeam", home_gi)

    # Playoff series info (round, game number, series score).
    series = _extract_series(landing)

    any_data = (
        series
        or any(
            v for s in (away, home) for k, v in s.items()
            if (v if not isinstance(v, list) else len(v) > 0)
        )
    )
    if not any_data:
        return None

    result: dict[str, Any] = {"away": away, "home": home}
    if series:
        result["series"] = series
    return result


def _stat_index(items: list[dict]) -> dict[str, dict]:
    """Map right-rail teamGameStats list → {category: row}."""
    return {(it.get("category") or "").lower(): it for it in items or []}


def _team_stats_from_right_rail(rr: dict) -> dict:
    rows = _stat_index((rr or {}).get("teamGameStats") or [])

    def pair(cat: str) -> tuple[Any, Any]:
        row = rows.get(cat.lower()) or {}
        return row.get("awayValue"), row.get("homeValue")

    def pct(v: Any) -> str:
        try:
            return f"{round(float(v) * 100)}%"
        except (TypeError, ValueError):
            return str(v) if v is not None else ""

    sog_a, sog_h = pair("sog")
    hits_a, hits_h = pair("hits")
    blocks_a, blocks_h = pair("blockedShots")
    fo_a, fo_h = pair("faceoffWinningPctg")
    pp_a, pp_h = pair("powerPlay")          # e.g. "1/3"
    pim_a, pim_h = pair("pim")
    give_a, give_h = pair("giveaways")
    take_a, take_h = pair("takeaways")

    def side(s, h, b, f, p, pi, gi, ta):
        out: dict[str, str] = {}
        if s  is not None: out["sog"]      = str(s)
        if h  is not None: out["hits"]     = str(h)
        if b  is not None: out["blocks"]   = str(b)
        if f  is not None: out["fo_pct"]   = pct(f)
        if p  is not None: out["pp"]       = str(p)
        if pi is not None: out["pim"]      = str(pi)
        if gi is not None: out["giveaways"] = str(gi)
        if ta is not None: out["takeaways"] = str(ta)
        return out

    return {
        "away": side(sog_a, hits_a, blocks_a, fo_a, pp_a, pim_a, give_a, take_a),
        "home": side(sog_h, hits_h, blocks_h, fo_h, pp_h, pim_h, give_h, take_h),
    }


def _line_score_from_right_rail(rr: dict) -> dict | None:
    ls = (rr or {}).get("linescore") or {}
    periods = ls.get("byPeriod") or []
    if not periods:
        return None
    cols: list[dict] = []
    for p in periods:
        pd = p.get("periodDescriptor") or {}
        n = pd.get("number")
        pt = (pd.get("periodType") or "REG").upper()
        if pt == "OT":
            label = "OT"
        elif pt == "SO":
            label = "SO"
        else:
            label = {1: "1", 2: "2", 3: "3"}.get(n, str(n) if n else "?")
        cols.append({"label": label, "away": p.get("away", 0), "home": p.get("home", 0)})
    totals = ls.get("totals") or {}
    return {
        "periods": cols,
        "totals": {"away": totals.get("away"), "home": totals.get("home")},
    }


def _power_play_from_boxscore(box: dict) -> dict | None:
    sit = box.get("situation") or {}
    if not sit:
        return None
    home = sit.get("homeTeam") or {}
    away = sit.get("awayTeam") or {}
    h_strength = home.get("strength") or 5
    a_strength = away.get("strength") or 5
    # PP team = whichever side has more skaters on the ice.
    if h_strength > a_strength:
        pp_team = home.get("abbrev") or box.get("homeTeam", {}).get("abbrev", "")
        kind = "POWER PLAY"
    elif a_strength > h_strength:
        pp_team = away.get("abbrev") or box.get("awayTeam", {}).get("abbrev", "")
        kind = "POWER PLAY"
    else:
        # equal strength — could be 4-on-4 or 3-on-3. Surface that.
        if h_strength and h_strength < 5:
            return {
                "kind": f"{h_strength}-ON-{a_strength}",
                "team": "",
                "time_remaining": sit.get("timeRemaining") or "",
            }
        return None
    return {
        "kind": kind,
        "team": pp_team,
        "time_remaining": sit.get("timeRemaining") or "",
    }


def _goalie_from_side(side_stats: dict) -> dict | None:
    goalies = side_stats.get("goalies") or []
    if not goalies:
        return None
    # Pick the goalie currently in net: prefer one whose TOI is non-zero and
    # largest; otherwise fall back to the last entry (typical sub-in order).
    def toi_seconds(g: dict) -> int:
        toi = g.get("toi") or "0:00"
        try:
            m, s = toi.split(":")
            return int(m) * 60 + int(s)
        except (ValueError, AttributeError):
            return 0
    active = max(goalies, key=toi_seconds) if any(toi_seconds(g) for g in goalies) else goalies[-1]
    name = _name(active.get("name"))
    sv_pct = active.get("savePctg") or active.get("savePercentage")
    saves_line = active.get("saveShotsAgainst") or ""  # "20/22"
    sv_pct_str = ""
    if sv_pct not in (None, ""):
        try:
            sv_pct_str = f".{round(float(sv_pct) * 1000):03d}"
        except (TypeError, ValueError):
            sv_pct_str = str(sv_pct)
    return {
        "name": name,
        "sv_pct": sv_pct_str,
        "saves": saves_line,
        "number": active.get("sweaterNumber"),
    }


def _goalies_from_boxscore(box: dict) -> dict:
    pbg = box.get("playerByGameStats") or {}
    return {
        "away": _goalie_from_side(pbg.get("awayTeam") or {}),
        "home": _goalie_from_side(pbg.get("homeTeam") or {}),
    }


# Skater stat keys to surface as "leaders". Map UI label → boxscore key.
_LEADER_CATEGORIES: list[tuple[str, str]] = [
    ("goals",   "goals"),
    ("assists", "assists"),
    ("points",  "points"),
    ("shots",   "shots"),
    ("hits",    "hits"),
    ("blocks",  "blockedShots"),
]


def _leaders_from_side(side_stats: dict, season: str, team_abbrev: str) -> dict:
    skaters = (side_stats.get("forwards") or []) + (side_stats.get("defense") or [])
    out: dict[str, dict] = {}
    for label, key in _LEADER_CATEGORIES:
        best = None
        best_val = 0
        for p in skaters:
            v = p.get(key, 0)
            if not isinstance(v, (int, float)):
                continue
            if v > best_val:
                best_val = v
                best = p
        if best and best_val > 0:
            leader = {
                "name":   _name(best.get("name")),
                "number": best.get("sweaterNumber"),
                "value":  best_val,
            }
            pid = best.get("playerId")
            if pid and season and team_abbrev:
                leader["photo"] = (
                    f"https://assets.nhle.com/mugs/nhl/{season}/{team_abbrev}/{pid}.png"
                )
            out[label] = leader
    return out


def _team_leaders(box: dict) -> dict:
    pbg = box.get("playerByGameStats") or {}
    season = str(box.get("season") or "")
    away_abbrev = (box.get("awayTeam") or {}).get("abbrev", "")
    home_abbrev = (box.get("homeTeam") or {}).get("abbrev", "")
    return {
        "away": _leaders_from_side(pbg.get("awayTeam") or {}, season, away_abbrev),
        "home": _leaders_from_side(pbg.get("homeTeam") or {}, season, home_abbrev),
    }


def _roster_from_side(side: dict, season: str, team_abbrev: str) -> list[dict]:
    players = (
        (side.get("forwards") or [])
        + (side.get("defense") or [])
        + (side.get("goalies") or [])
    )
    out: list[dict] = []
    for p in players:
        pid = p.get("playerId")
        name = _name(p.get("name"))
        if not pid or not name:
            continue
        entry: dict[str, Any] = {
            "id":       pid,
            "name":     name,
            "number":   p.get("sweaterNumber"),
            "position": p.get("position", ""),
        }
        if season and team_abbrev:
            entry["photo"] = (
                f"https://assets.nhle.com/mugs/nhl/{season}/{team_abbrev}/{pid}.png"
            )
        out.append(entry)
    return out


def _rosters_from_boxscore(box: dict) -> dict:
    pbg = box.get("playerByGameStats") or {}
    season = str(box.get("season") or "")
    away_abbrev = (box.get("awayTeam") or {}).get("abbrev", "")
    home_abbrev = (box.get("homeTeam") or {}).get("abbrev", "")
    return {
        "away": _roster_from_side(pbg.get("awayTeam") or {}, season, away_abbrev),
        "home": _roster_from_side(pbg.get("homeTeam") or {}, season, home_abbrev),
    }


async def get_game(client: httpx.AsyncClient, game_id: str) -> dict:
    box_url     = f"{BASE}/gamecenter/{game_id}/boxscore"
    landing_url = f"{BASE}/gamecenter/{game_id}/landing"
    rr_url      = f"{BASE}/gamecenter/{game_id}/right-rail"

    box_r, landing_r, rr_r = await asyncio.gather(
        client.get(box_url),
        client.get(landing_url),
        client.get(rr_url),
        return_exceptions=True,
    )

    if isinstance(box_r, Exception):
        raise box_r
    box_r.raise_for_status()
    box_json = box_r.json()
    game = _summarize(box_json)

    pp = _power_play_from_boxscore(box_json)
    if pp:
        game["power_play"] = pp

    goalies = _goalies_from_boxscore(box_json)
    if goalies.get("home") or goalies.get("away"):
        game["goalies"] = goalies

    leaders = _team_leaders(box_json)
    if leaders.get("home") or leaders.get("away"):
        game["leaders"] = leaders

    rosters = _rosters_from_boxscore(box_json)
    if rosters.get("home") or rosters.get("away"):
        game["rosters"] = rosters

    if not isinstance(landing_r, Exception) and landing_r.status_code == 200:
        try:
            landing = landing_r.json()
            game["last_goal"]    = _extract_last_goal(landing)
            game["last_penalty"] = _extract_last_penalty(landing)
            series = _extract_series(landing)
            if series:
                game["series"] = series
            preview = _preview_from_landing(landing)
            if preview:
                game["preview"] = preview
        except Exception:
            pass

    if not isinstance(rr_r, Exception) and rr_r.status_code == 200:
        try:
            rr = rr_r.json()
            game["team_stats"] = _team_stats_from_right_rail(rr)
            ls = _line_score_from_right_rail(rr)
            if ls:
                game["line_score"] = ls
        except Exception:
            pass

    return game
