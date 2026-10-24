"""Per-game stats and injury details from ESPN player cards.

One player-card request returns, for a batch of players: every game this season, season / last-15 /
last-7 averages, last season's averages, ESPN's projection, ownership and injury details. This module
turns that raw JSON into plain dicts for the "My players" and "Injury watch" tabs.
Everything here is best-effort: if ESPN leaves something out, that part of the page is just empty.
"""
import html
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

ET = ZoneInfo("America/New_York")
STAT_IDS = {"0": "PTS", "1": "BLK", "2": "STL", "3": "AST", "6": "REB", "11": "TO", "13": "FGM", "14": "FGA",
            "15": "FTM", "16": "FTA", "17": "3PM", "40": "MIN", "42": "GP"}
LINE = ["MIN", "PTS", "REB", "AST", "STL", "BLK", "3PM", "TO", "FGM", "FGA", "FTM", "FTA"]
INJURED = {"OUT", "INJURY_RESERVE", "DOUBTFUL", "QUESTIONABLE", "DAY_TO_DAY", "SUSPENSION"}
STATUS_LABEL = {"OUT": "Out", "INJURY_RESERVE": "Out", "DOUBTFUL": "Doubtful", "QUESTIONABLE": "Questionable",
                "DAY_TO_DAY": "Day-to-day", "SUSPENSION": "Suspended", "PROBABLE": "Probable"}
# statSplitTypeId: 0 season, 1 last 7 days, 2 last 15, 3 last 30, 5 a single game.
SPLITS = {0: "Season", 1: "Last 7", 2: "Last 15"}


def _named(d):
    return {STAT_IDS[k]: float(v) for k, v in (d or {}).items() if k in STAT_IDS and v is not None}


def _ids(split):
    """(source, split type) for a stat block, from its fields or, failing that, its id like '052027'."""
    src, typ = split.get("statSourceId"), split.get("statSplitTypeId")
    sid = str(split.get("id", ""))
    if src is None and len(sid) >= 2 and sid[:2].isdigit():
        src, typ = int(sid[0]), int(sid[1])
    return src, typ


def parse(entry, year):
    """Split one raw player-card entry into averages and a game log."""
    pl = entry.get("player", entry) if isinstance(entry, dict) else {}
    out = {"avgs": {}, "games": {}, "proj": None}
    for s in pl.get("stats") or []:
        src, typ = _ids(s)
        season = s.get("seasonId")
        if src == 0 and typ == 5 and season == year:
            line = _named(s.get("stats"))
            if line.get("MIN", 0) > 0 or line.get("FGA", 0) > 0 or line.get("PTS", 0) > 0:
                out["games"][int(s.get("scoringPeriodId") or 0)] = line
        elif src == 0 and typ in SPLITS and s.get("averageStats"):
            label = SPLITS[typ] if season == year else ("Last season" if typ == 0 and season == year - 1 else None)
            if label:
                avg = _named(s["averageStats"])
                avg["GP"] = _named(s.get("stats")).get("GP", avg.get("GP", 0))
                out["avgs"][label] = avg
        elif src == 1 and typ == 0 and season == year and s.get("averageStats"):
            out["proj"] = _named(s["averageStats"])
    own = pl.get("ownership") or {}
    out["own"] = own.get("percentOwned")
    out["own_change"] = own.get("percentChange")
    ret = pl.get("expectedReturnDate")
    out["ret"] = None
    if isinstance(ret, (list, tuple)) and len(ret) >= 3:
        try:
            out["ret"] = date(*[int(x) for x in ret[:3]]).isoformat()
        except (TypeError, ValueError):
            pass
    out["injury"] = pl.get("injuryStatus")
    out["injured"] = bool(pl.get("injured"))
    out["status"] = entry.get("status") if isinstance(entry, dict) else None  # FREEAGENT, WAIVERS, ONTEAM
    out["on_team"] = entry.get("onTeamId") if isinstance(entry, dict) else None
    return out


def fetch(lg, ids):
    """Raw player cards for these player ids, keyed by id. Adds last season and recent splits."""
    out = {}
    extra = [f"00{lg.year - 1}", f"01{lg.year}", f"02{lg.year}"]
    ids = [i for i in dict.fromkeys(ids) if i is not None]
    for i in range(0, len(ids), 40):
        try:
            data = lg.espn_request.get_player_card(ids[i:i + 40], lg.finalScoringPeriod, additional_filters=extra)
        except Exception as exc:  # one failed batch shouldn't sink the whole page
            print(f"Player cards unavailable: {exc}")
            continue
        for e in (data or {}).get("players", []):
            pid = e.get("id") or (e.get("player") or {}).get("id")
            if pid is not None:
                out[pid] = e
    return out


def news(lg, pid, limit=3):
    """Latest ESPN news blurbs for a player, newest first. Empty if the feed is unavailable."""
    try:
        endpoint = lg.espn_request.NEWS_ENDPOINT
        r = requests.get(endpoint, params={"playerId": pid, "limit": limit},
                         cookies=getattr(lg.espn_request, "cookies", None), timeout=12)
        data = r.json() if r.ok else {}
    except Exception:
        return []
    feed = data.get("feed") or (data.get("news") or {}).get("feed") or []
    items = []
    for it in feed[:limit]:
        story = re.sub(r"<[^>]+>", " ", html.unescape(it.get("story") or it.get("description") or ""))
        story = " ".join(story.split())
        if len(story) > 320:
            story = story[:317].rsplit(" ", 1)[0] + "…"
        items.append({"published": (it.get("published") or it.get("lastModified") or "")[:10],
                      "headline": it.get("headline", ""), "story": story})
    return items


def game_log(parsed, sp_date, opp_by_sp, today_sp, n=10):
    """Most recent games first: date, opponent and the stat line."""
    rows = []
    for sp in sorted((sp for sp in parsed["games"] if sp < today_sp or today_sp is None), reverse=True)[:n]:
        d = sp_date.get(sp)
        rows.append({"date": d.strftime("%a %b %-d") if d else f"Day {sp}",
                     "opp": opp_by_sp.get(sp, ""), **{k: parsed["games"][sp].get(k, 0) for k in LINE}})
    return rows


def as_sim_line(avg):
    """Convert an ESPN averages dict to the planner's per-game stat format."""
    return {"fgm": avg.get("FGM", 0), "fga": avg.get("FGA", 0), "ftm": avg.get("FTM", 0), "fta": avg.get("FTA", 0),
            "tpm": avg.get("3PM", 0), "reb": avg.get("REB", 0), "ast": avg.get("AST", 0), "stl": avg.get("STL", 0),
            "blk": avg.get("BLK", 0), "to": avg.get("TO", 0)}


def best_basis(parsed):
    """The most trustworthy per-game line for judging a player's real level, and where it came from.

    An injured star often has few or no games this season, so last season is the better guide.
    """
    a = parsed["avgs"]
    this, last = a.get("Season"), a.get("Last season")
    if this and this.get("GP", 0) >= 15:
        return this, "this season"
    if last and last.get("GP", 0) >= 10:
        if this and this.get("GP", 0) >= 5:
            return this, "this season"
        return last, "last season"
    if this and this.get("GP", 0) >= 1:
        return this, "this season"
    if parsed.get("proj"):
        return parsed["proj"], "ESPN projection"
    return None, None


def games_after(team_games, sp_date, team, from_date):
    """NBA games his team has left on or after a date."""
    d0 = date.fromisoformat(from_date) if isinstance(from_date, str) else from_date
    return sum(1 for sp in team_games.get(team, ()) if sp_date.get(sp) and sp_date[sp] >= d0)
