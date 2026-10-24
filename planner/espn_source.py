"""Pull the current matchup, rosters, free agents, schedules and injuries from ESPN."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from espn_api.basketball import League
from espn_api.basketball.constant import POSITION_MAP, PRO_TEAM_MAP

from . import cards
from .check import fingerprint

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
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
    """Map scoring period -> ET date, and NBA team -> set of scoring periods with a game.

    Also keeps each game's tip-off time (UTC ISO) and opponent, which the deadline reminder,
    the per-game stats tab and the injury tab use.
    """
    sp_date, team_games, team_tips, team_opp = {}, {}, {}, {}
    for pro_id, games in (lg.pro_schedule or {}).items():
        abbrev = PRO_TEAM_MAP.get(int(pro_id))
        for sp, glist in games.items():
            if not glist:
                continue
            sp = int(sp)
            g = glist[0]
            tip = datetime.fromtimestamp(g["date"] / 1000, tz=ET)
            d = tip.date()
            sp_date[sp] = min(sp_date.get(sp, d), d)
            team_games.setdefault(abbrev, set()).add(sp)
            team_tips.setdefault(abbrev, {})[sp] = tip.astimezone(UTC).isoformat()
            home = g.get("homeProTeamId") == int(pro_id)
            other = g.get("awayProTeamId") if home else g.get("homeProTeamId")
            if other is not None:
                team_opp.setdefault(abbrev, {})[sp] = ("" if home else "@") + PRO_TEAM_MAP.get(int(other), "?")
    return sp_date, team_games, team_tips, team_opp


def _today_sp(lg, sp_date):
    """ESPN's current scoring period, moved on to today's if ESPN hasn't rolled over yet.

    The main run happens overnight (UK morning), after the last game has finished. ESPN sometimes
    still reports yesterday as the current day at that point, which would make the plan count
    games that are already over. Once it's past midnight Eastern, yesterday is finished.
    """
    today_sp = lg.current_week
    now = datetime.now(ET).date()
    d = sp_date.get(today_sp)
    if d is not None and d < now:
        later = sorted(sp for sp, x in sp_date.items() if x >= now)
        if later:
            today_sp = later[0]
    return today_sp


def _matchup_days(lg, cfg, sp_date, day_tips):
    today_sp = _today_sp(lg, sp_date)
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
             "label": (sp_date.get(sp) or today).strftime("%a %b %-d"),
             "first_tip": day_tips.get(sp)} for sp in sps]
    today_index = next((i for i, d in enumerate(days) if d["sp"] >= today_sp), len(days))
    return days, today_index


def _next_days(cfg, sp_date, days):
    """The days of next week's matchup: the Monday to Sunday after this matchup ends, or up to NEXT_MATCHUP_END."""
    if not days:
        return []
    end = date.fromisoformat(days[-1]["date"])
    start = end + timedelta(days=1)
    stop = date.fromisoformat(cfg.next_matchup_end) if cfg.next_matchup_end else start + timedelta(days=6 - start.weekday())
    if stop < start:
        stop = start + timedelta(days=6)
    return [{"sp": sp, "date": d.isoformat(), "label": d.strftime("%a %b %-d")}
            for sp, d in sorted(sp_date.items()) if start <= d <= stop]


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


_CTX = {"team_tips": {}, "next_days": []}


def _player(p, year, days, today_index, team_games, ir=False, team_tips=None):
    team_tips = team_tips if team_tips is not None else _CTX["team_tips"]
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
            "trend": _trend(p, year),
            "tips": [((team_tips or {}).get(p.proTeam) or {}).get(d["sp"]) for d in days],
            "next_games": [d["sp"] in played for d in _CTX["next_days"]],
            "next_prob": [p_later if not (p_later == 0 and ret and date.fromisoformat(d["date"]) >= ret) else 0.6
                          for d in _CTX["next_days"]]}


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


def _slot_counts(lg):
    try:
        raw = lg.espn_request.league_get(params={"view": "mSettings"})
        return raw["settings"]["rosterSettings"]["lineupSlotCounts"]
    except Exception:
        return None


def _lineup_slots(counts):
    """Active lineup slots from the league settings, e.g. PG, SG, SF, PF, C, G, F, UT, UT, UT."""
    if not counts:
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


def _my_cards(lg, cards_raw, players, sp_date, team_opp, today_sp):
    """Attach averages and a recent game log to each of your players for the "My players" tab."""
    for x in players:
        e = cards_raw.get(x["id"])
        if not e:
            continue
        parsed = cards.parse(e, lg.year)
        x["card"] = {"avgs": parsed["avgs"],
                     "log": cards.game_log(parsed, sp_date, team_opp.get(x["team"], {}), today_sp)}


def _injury_watch(lg, cfg, me_team, me_players, fa_pool, sp_date, team_games, today_sp):
    """Injured players worth tracking: your watch list, injured free agents, and your own injured players."""
    owners = {t.team_id: t.team_name for t in lg.teams}
    wanted = {}  # id -> why we're tracking him
    for p in me_team.roster:
        if p.injuryStatus in cards.INJURED or p.lineupSlot == "IR":
            wanted[p.playerId] = "mine"
    for p in fa_pool:
        if p.injuryStatus in cards.INJURED or getattr(p, "injured", False):
            wanted.setdefault(p.playerId, "fa")
    from .whatif import match
    names = [k for k in (getattr(lg, "player_map", {}) or {}) if isinstance(k, str)]
    missing = []
    for q in cfg.watch_players:
        hits = match(q, names)
        if hits:
            wanted[lg.player_map[names[hits[0]]]] = "watch"
        else:
            missing.append(q)
    raw = cards.fetch(lg, list(wanted))
    team_of = {}
    for t in lg.teams:
        for p in t.roster:
            team_of[p.playerId] = p.proTeam
    for p in fa_pool:
        team_of[p.playerId] = p.proTeam

    out = []
    for pid, why in wanted.items():
        e = raw.get(pid)
        if not e:
            continue
        pl = e.get("player") or {}
        parsed = cards.parse(e, lg.year)
        basis, source = cards.best_basis(parsed)
        team = team_of.get(pid) or PRO_TEAM_MAP.get(pl.get("proTeamId"), "")
        status = cards.STATUS_LABEL.get(parsed["injury"], "Healthy" if not parsed["injured"] else "Injured")
        if why == "fa" and status == "Healthy":
            continue
        on = parsed["on_team"]
        if why == "mine" or on == cfg.team_id:
            owner = "Your team"
        elif on and on in owners:
            owner = owners[on]
        else:
            owner = "On waivers" if parsed["status"] == "WAIVERS" else "Free agent"
        ret = parsed["ret"]
        start = ret or datetime.now(ET).date().isoformat()
        x = {"id": pid, "name": pl.get("fullName") or lg.player_map.get(pid, str(pid)), "team": team,
             "status": status, "owner": owner, "watch": why == "watch", "mine": owner == "Your team",
             "ret": ret, "own": parsed["own"], "own_change": parsed["own_change"],
             "line": basis, "source": source, "s": cards.as_sim_line(basis) if basis else None,
             "games_left": cards.games_after(team_games, sp_date, team, start), "news": []}
        out.append(x)

    # Keep injured free agents only if, healthy, they'd be at least as good as your weakest starter.
    from .sim import EQUAL, value
    from .whatif import season_value
    mine = sorted((season_value(p) for p in me_players if not p["ir"]), reverse=True)
    bar = mine[min(len(mine), max(cfg.active_slots, 1)) - 1] if mine else 0
    fas = sorted((x for x in out if not x["mine"] and not x["watch"] and x["s"]),
                 key=lambda x: -value(x["s"], EQUAL))
    keep_fa = {id(x) for x in [f for f in fas if value(f["s"], EQUAL) >= bar * 0.9][:8]}
    out = [x for x in out if x["mine"] or x["watch"] or id(x) in keep_fa]
    for x in out:
        x["news"] = cards.news(lg, x["id"])
    return out, missing


def load(cfg):
    lg = _connect(cfg)
    sp_date, team_games, team_tips, team_opp = _game_dates(lg)
    day_tips = {}
    for tips in team_tips.values():
        for sp, iso in tips.items():
            day_tips[sp] = min(day_tips.get(sp, iso), iso)
    days, today_index = _matchup_days(lg, cfg, sp_date, day_tips)
    today_sp = _today_sp(lg, sp_date)
    _CTX["team_tips"] = team_tips
    _CTX["next_days"] = _next_days(cfg, sp_date, days)

    boxes = list(lg.box_scores())
    box = next((b for b in boxes if cfg.team_id in
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
        players = [x for x in (_player(p, lg.year, days, today_index, team_games, ir=(p.lineupSlot == "IR"),
                                       team_tips=team_tips) for p in roster) if x]
        sofar, note = _sofar(stats, [p for p in players if not p["ir"]])
        return {"name": team.team_name, "sofar": sofar, "players": players}, note

    me, note = side(me_team, me_stats)
    opp, _ = side(opp_team, opp_stats)

    # Every other team in the league, for the league-wide weekly projection.
    stats_by_team = {}
    for b in boxes:
        for t, st in ((b.home_team, b.home_stats), (b.away_team, b.away_stats)):
            tid = getattr(t, "team_id", t)
            if tid is not None:
                stats_by_team[tid] = st
    others = []
    for t in lg.teams:
        if t.team_id in (cfg.team_id, getattr(opp_team, "team_id", None)):
            continue
        try:
            o, _ = side(t, stats_by_team.get(t.team_id))
            others.append(o)
        except Exception as exc:  # one odd roster shouldn't stop the whole plan
            print(f"Skipped {t.team_name} in the league projection: {exc}")

    fa_raw = _with_stats(lg, lg.free_agents(size=cfg.fa_pool))
    fa = [x for x in (_player(p, lg.year, days, today_index, team_games, team_tips=team_tips) for p in fa_raw) if x]

    extra = _what_if_players(lg, cfg, days, today_index, team_games, me, opp, fa)

    # My players tab: game logs and splits from one batch of player cards.
    _my_cards(lg, cards.fetch(lg, [x["id"] for x in me["players"]]), me["players"], sp_date, team_opp, today_sp)

    # Injury watch tab: a deeper free-agent pool, so injured stars further down the list are found too.
    try:
        deep = lg.free_agents(size=max(cfg.fa_pool, 150))
    except Exception:
        deep = fa_raw
    watch, missing = _injury_watch(lg, cfg, me_team, me["players"], deep, sp_date, team_games, today_sp)

    counts = _slot_counts(lg) or {}
    return {
        "league": {"name": lg.settings.name, "week": lg.currentMatchupPeriod},
        "days": days, "today_index": today_index,
        "adds_used": _adds_used(lg, cfg), "sofar_note": note, "lineup_slots": _lineup_slots(counts),
        "ir_slots": int(counts.get("13", 0) or 0), "ir_used": sum(1 for p in me_team.roster if p.lineupSlot == "IR"),
        "injury_watch": watch, "watch_missing": missing,
        "me": me, "opp": opp, "fa": fa, "extra": extra, "others": others, "next_days": _CTX["next_days"],
        "roster_fp": fingerprint((p.playerId, p.lineupSlot == "IR") for p in me_team.roster),
    }
