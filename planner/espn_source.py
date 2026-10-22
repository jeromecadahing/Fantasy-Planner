"""Pull the current matchup, rosters, free agents, schedules and injuries from ESPN."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from espn_api.basketball import League
from espn_api.basketball.constant import POSITION_MAP, PRO_TEAM_MAP

ET = ZoneInfo("America/New_York")
STAT_KEYS = {"fgm": "FGM", "fga": "FGA", "ftm": "FTM", "fta": "FTA", "tpm": "3PM",
             "reb": "REB", "ast": "AST", "stl": "STL", "blk": "BLK", "to": "TO"}
TOTAL_KEYS = ["FGM", "FGA", "FTM", "FTA", "3PM", "PTS", "REB", "AST", "STL", "BLK", "TO"]

# Chance a player suits up: (today, later this week)
STATUS = {
    "ACTIVE": ("Healthy", 1.0, 1.0), "NORMAL": ("Healthy", 1.0, 1.0), None: ("Healthy", 1.0, 1.0),
    "PROBABLE": ("Probable", 0.9, 0.95), "DAY_TO_DAY": ("Day-to-day", 0.6, 0.8),
    "QUESTIONABLE": ("Questionable", 0.5, 0.8), "DOUBTFUL": ("Doubtful", 0.2, 0.6),
    "OUT": ("Out", 0.0, 0.0), "INJURY_RESERVE": ("Out", 0.0, 0.0), "SUSPENSION": ("Suspended", 0.0, 0.0),
}


NOT_ACTIVE = {"BE", "IR", "Rookie", ""}


class SetupError(SystemExit):
    pass


def _connect(cfg):
    if not cfg.league_id or not cfg.team_id:
        raise SetupError("LEAGUE_ID and TEAM_ID are required. Find both in your ESPN team page URL: "
                         "...?leagueId=12345&teamId=3")
    try:
        return League(league_id=cfg.league_id, year=cfg.year,
                      espn_s2=cfg.espn_s2 or None, swid=cfg.swid or None)
    except Exception as exc:  # the library raises plain Exceptions for 401/404
        msg = str(exc)
        if "401" in msg or "access" in msg.lower():
            raise SetupError("ESPN refused access. Your league is private, so ESPN_S2 and SWID must be "
                             "set as GitHub secrets (see README). They expire occasionally; copy fresh ones.")
        if "404" in msg:
            raise SetupError(f"ESPN couldn't find league {cfg.league_id} for the {cfg.year} season. "
                             "Check LEAGUE_ID, and set YEAR if the season hasn't rolled over yet.")
        raise


def _game_dates(lg):
    """Map scoring period -> ET date, and NBA team -> set of scoring periods with a game."""
    sp_date, team_games = {}, {}
    for pro_id, games in (lg.pro_schedule or {}).items():
        abbrev = PRO_TEAM_MAP.get(int(pro_id))
        for sp, glist in games.items():
            if not glist:
                continue
            sp = int(sp)
            d = datetime.fromtimestamp(glist[0]["date"] / 1000, tz=ET).date()
            sp_date[sp] = min(sp_date.get(sp, d), d)
            team_games.setdefault(abbrev, set()).add(sp)
    return sp_date, team_games


def _matchup_days(lg, cfg, sp_date):
    today_sp = lg.current_week
    today = sp_date.get(today_sp) or datetime.now(ET).date()
    known = sorted(int(x) for x in lg.matchup_ids.get(lg.currentMatchupPeriod, []))
    start = sp_date.get(known[0], today) if known else today - timedelta(days=today.weekday())
    if cfg.matchup_end:
        end = date.fromisoformat(cfg.matchup_end)
    else:
        end = today + timedelta(days=6 - today.weekday())  # the Sunday ending this week
    if end < today:
        end = today + timedelta(days=6 - today.weekday())
    sps = sorted({sp for sp, d in sp_date.items() if start <= d <= end} | {today_sp} | set(known))
    sps = [sp for sp in sps if sp in sp_date or sp == today_sp]
    days = [{"sp": sp, "date": (sp_date.get(sp) or today).isoformat(),
             "label": (sp_date.get(sp) or today).strftime("%a %b %-d")} for sp in sps]
    today_index = next((i for i, d in enumerate(days) if d["sp"] >= today_sp), len(days))
    return days, today_index


def _split(p, year, key):
    return p.stats.get(f"{year}_{key}") or {}


def _gp(split):
    total, avg = split.get("total") or {}, split.get("avg") or {}
    return total.get("GP") or avg.get("GP") or 0


def _mpg(split):
    avg = split.get("avg") or {}
    return avg.get("MIN") or avg.get("MPG") or 0


def _avg(parts):
    wsum = sum(w for _, w in parts)
    return {k: round(sum((sp["avg"].get(v) or 0) * w for sp, w in parts) / wsum, 3) for k, v in STAT_KEYS.items()}


def _blend(p, year):
    """Per-game averages for this week, and a steadier season-long version.

    Early in the season a player's real numbers come from only a few games, so they're pulled
    toward ESPN's preseason projection until the sample is big enough to trust.
    The 7- and 15-day splits are only used once there's a real season behind them;
    before that they're the same few games counted twice.
    """
    season, l15, l7, proj = (_split(p, year, k) for k in ("total", "last_15", "last_7", "projected"))
    gps = _gp(season)
    real = []
    if gps >= 1 and season.get("avg"):
        real.append((season, 0.4 if gps >= 8 else 1.0))
        if gps >= 8 and _gp(l15) >= 3 and l15.get("avg"):
            real.append((l15, 0.4))
        if gps >= 8 and _gp(l7) >= 2 and l7.get("avg"):
            real.append((l7, 0.2))
    has_proj = bool(proj.get("avg"))
    if not real and not has_proj:
        return None, None

    def mix(k):  # projection weight shrinks as games are played: k games' worth of trust
        if not real:
            return _avg([(proj, 1.0)])
        if not has_proj:
            return _avg(real)
        pw = k / (gps + k)
        rsum = sum(w for _, w in real)
        return _avg([(sp, w / rsum * (1 - pw)) for sp, w in real] + [(proj, pw)])

    return mix(6), mix(15)


def _trend(p, year):
    season, l7 = _split(p, year, "total"), _split(p, year, "last_7")
    m7, ms = _mpg(l7), _mpg(season)
    if _gp(l7) >= 2 and ms and m7:
        if m7 - ms >= 4:
            return f"Minutes up: {m7:.1f} last 7 days vs {ms:.1f} season"
        if ms - m7 >= 5:
            return f"Minutes down: {m7:.1f} last 7 days vs {ms:.1f} season"
    return None


def _player(p, year, days, today_index, team_games, ir=False):
    stats, season_long = _blend(p, year)
    if stats is None:
        return None
    label, p_today, p_later = STATUS.get(p.injuryStatus, ("Healthy", 1.0, 1.0))
    ret = getattr(p, "expected_return_date", None)
    games, prob = [], []
    played = team_games.get(p.proTeam, set())
    for i, d in enumerate(days):
        games.append(d["sp"] in played)
        pr = p_today if i <= today_index else p_later
        if pr == 0 and ret and date.fromisoformat(d["date"]) >= ret:
            pr = 0.6
        prob.append(pr)
    elig = [x for x in (getattr(p, "eligibleSlots", None) or []) if x and x not in NOT_ACTIVE]
    return {"name": p.name, "id": p.playerId, "team": p.proTeam, "pos": p.position, "elig": elig,
            "status": label, "ir": ir, "games": games, "prob": prob, "s": stats, "long": season_long,
            "trend": _trend(p, year)}


def _with_stats(lg, players):
    """Roster and free-agent feeds sometimes omit stat splits; refetch those from player cards."""
    missing = [p.playerId for p in players if not p.stats.get(f"{lg.year}_total") and not p.stats.get(f"{lg.year}_projected")]
    if not missing:
        return players
    fresh = {}
    for i in range(0, len(missing), 50):
        got = lg.player_info(playerId=missing[i:i + 50]) or []
        for q in (got if isinstance(got, list) else [got]):
            fresh[q.playerId] = q
    out = []
    for p in players:
        q = fresh.get(p.playerId)
        if q is not None:
            q.lineupSlot = getattr(p, "lineupSlot", "")
            q.injuryStatus = p.injuryStatus or q.injuryStatus
            out.append(q)
        else:
            out.append(p)
    return out


def _sofar(stats, roster):
    """Category totals already earned this matchup, as [FGM, FGA, FTM, FTA, 3PM, PTS, REB, AST, STL, BLK, TO]."""
    val = {k: (v.get("value") if isinstance(v, dict) else v) for k, v in (stats or {}).items()}
    tot = [float(val.get(k) or 0) for k in TOTAL_KEYS]
    note = None
    pts = tot[5]
    if pts and (not tot[1] or not tot[3]):
        # League only tracks FG%/FT% as rates, so estimate attempts from points scored.
        s_pts = sum(2 * p["s"]["fgm"] + p["s"]["tpm"] + p["s"]["ftm"] for p in roster) or 1
        for m, a, rate_key, attempts_key in ((0, 1, "FG%", "fga"), (2, 3, "FT%", "fta")):
            rate = float(val.get(rate_key) or 0)
            rate = rate / 100 if rate > 1 else rate
            att = pts * sum(p["s"][attempts_key] for p in roster) / s_pts
            tot[a], tot[m] = att, att * rate
        note = "FG% and FT% so far use estimated attempts, because ESPN only reports them as percentages."
    return tot, note


def _lineup_slots(lg):
    """Active lineup slots from the league settings, e.g. PG, SG, SF, PF, C, G, F, UT, UT, UT."""
    try:
        raw = lg.espn_request.league_get(params={"view": "mSettings"})
        counts = raw["settings"]["rosterSettings"]["lineupSlotCounts"]
    except Exception:
        return []
    out = []
    for sid, k in sorted(counts.items(), key=lambda x: int(x[0])):
        name = POSITION_MAP.get(int(sid), "")
        if k and name not in NOT_ACTIVE:
            out += [name] * int(k)
    return out


def _adds_used(lg, cfg):
    try:
        raw = lg.espn_request.league_get(params={"view": "mTeam"})
        for t in raw.get("teams", []):
            if t.get("id") == cfg.team_id:
                totals = (t.get("transactionCounter") or {}).get("matchupAcquisitionTotals") or {}
                return int(totals.get(str(lg.currentMatchupPeriod), 0))
    except Exception:
        pass
    return None


def _what_if_players(lg, cfg, days, today_index, team_games, me, opp, fa):
    """Look up players named in WHAT_IF who aren't on either roster or in the free-agent pool:
    players on other teams in the league (trade targets) and deeper free agents."""
    if not cfg.what_if:
        return []
    from .whatif import match, parse
    adds, _, _ = parse(cfg.what_if)
    known = [p["name"] for p in me["players"] + opp["players"] + fa]
    wanted = [q for q in adds if not match(q, known)]
    if not wanted:
        return []
    owned = [(p, t.team_name) for t in lg.teams for p in t.roster
             if t.team_name not in (me["name"], opp["name"])]
    everyone = [k for k in (getattr(lg, "player_map", {}) or {}) if isinstance(k, str)]
    found = []
    for q in wanted:
        hits = match(q, [p.name for p, _ in owned])
        if hits:
            found += [owned[i] for i in hits[:4]]
            continue
        for i in match(q, everyone)[:4]:
            try:
                got = lg.player_info(playerId=lg.player_map[everyone[i]])
            except Exception:
                got = None
            for p in (got if isinstance(got, list) else [got] if got else []):
                found.append((p, "Free agent"))
    out = []
    players = _with_stats(lg, [p for p, _ in found])
    for p, (_, owner) in zip(players, found):
        x = _player(p, lg.year, days, today_index, team_games)
        if x:
            x["owner"] = owner
            out.append(x)
    return out


def load(cfg):
    lg = _connect(cfg)
    sp_date, team_games = _game_dates(lg)
    days, today_index = _matchup_days(lg, cfg, sp_date)

    box = next((b for b in lg.box_scores() if cfg.team_id in
                (getattr(b.home_team, "team_id", b.home_team), getattr(b.away_team, "team_id", b.away_team))), None)
    if box is None:
        raise SetupError(f"No matchup found for team {cfg.team_id} this week. Check TEAM_ID, or this may be a bye week.")
    home = getattr(box.home_team, "team_id", box.home_team) == cfg.team_id
    me_team, opp_team = (box.home_team, box.away_team) if home else (box.away_team, box.home_team)
    me_stats, opp_stats = (box.home_stats, box.away_stats) if home else (box.away_stats, box.home_stats)
    if isinstance(opp_team, int):
        raise SetupError("Your opponent's team couldn't be read from ESPN this week.")

    def side(team, stats):
        roster = _with_stats(lg, list(team.roster))
        players = [x for x in (_player(p, lg.year, days, today_index, team_games, ir=(p.lineupSlot == "IR"))
                               for p in roster) if x]
        sofar, note = _sofar(stats, [p for p in players if not p["ir"]])
        return {"name": team.team_name, "sofar": sofar, "players": players}, note

    me, note = side(me_team, me_stats)
    opp, _ = side(opp_team, opp_stats)

    fa_raw = _with_stats(lg, lg.free_agents(size=cfg.fa_pool))
    fa = [x for x in (_player(p, lg.year, days, today_index, team_games) for p in fa_raw) if x]

    extra = _what_if_players(lg, cfg, days, today_index, team_games, me, opp, fa)

    return {
        "league": {"name": lg.settings.name, "week": lg.currentMatchupPeriod},
        "days": days, "today_index": today_index,
        "adds_used": _adds_used(lg, cfg), "sofar_note": note, "lineup_slots": _lineup_slots(lg),
        "me": me, "opp": opp, "fa": fa, "extra": extra,
    }
