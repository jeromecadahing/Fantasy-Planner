"""Stash simulator: if you pick up an injured player now, what does it do for you, depending on when he's back?

For each injured player worth stashing (the Injury watch tab's free agents, waiver players and your own
injured players), and each way of making room for him (a free IR slot, an open roster spot, or dropping one
of your weakest players), this simulates every possible return day: each remaining day of this matchup,
each day of next week, and "not back before next week ends". The page then lets you pick a player, a drop
and a return day and shows your chance to win this week and next week instantly.

Everything is simulated when the page is built, with the same random numbers for every option, so the
differences between options come from the player and the dates, not from luck.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np

from . import nextmatch
from .sim import Entry, compare, entries, sim_team
from .whatif import _protected, _season_ranks, season_value

# Chance he suits up on a given night once he's back. Players returning from injury often sit one
# night of a back-to-back or come off the bench at first, so this is a little under a healthy player's.
RETURN_PROB = 0.85
# The second night of a back-to-back: teams often rest a player who's just back from injury.
B2B_PROB = 0.55
MAX_PLAYERS = 8
MAX_DROPS = 3


def _sched(team, data, n_days, n_next):
    s = (data.get("team_sched") or {}).get(team)
    if not s:
        return None, None
    t = data["today_index"]
    this = ([False] * t + [bool(g) for g in s.get("this") or []] + [False] * n_days)[:n_days]
    nxt = ([bool(g) for g in s.get("next") or []] + [False] * n_next)[:n_next]
    return this, nxt


def _options(data):
    """Return-day choices: each remaining day this week, each day next week, then 'later'."""
    t, days, nd = data["today_index"], data["days"], data.get("next_days") or []
    opts = [{"week": "this", "i": d, "label": days[d]["label"], "date": days[d]["date"], "today": d == t}
            for d in range(t, len(days))]
    opts += [{"week": "next", "i": j, "label": x["label"], "date": x["date"], "today": False} for j, x in enumerate(nd)]
    last = (nd[-1]["label"] if nd else days[-1]["label"]) if days else ""
    opts.append({"week": "later", "i": None, "label": f"After {last}", "date": None, "today": False})
    return opts


def _default(opts, x):
    """The option matching ESPN's return estimate."""
    ret = x.get("ret")
    if not ret:
        return len(opts) - 1 if x.get("status") == "Out" else 0
    for k, o in enumerate(opts):
        if o["date"] and o["date"] >= ret:
            return k
    return len(opts) - 1


def _claim_blocks(x, data):
    """For a player on waivers, the first day index this week and next week he could play once claimed."""
    days, nd, t = data["days"], data.get("next_days") or [], data["today_index"]
    if x.get("owner") != "On waivers":
        return 0, 0
    if not x.get("waiver_clears"):
        return t + 2, max(0, t + 2 - len(days))  # ESPN's usual two-day wait
    clears = datetime.fromisoformat(x["waiver_clears"]).astimezone(ZoneInfo("America/New_York")).date().isoformat()
    a = next((d for d in range(len(days)) if days[d]["date"] > clears), len(days))
    b = next((j for j in range(len(nd)) if nd[j]["date"] > clears), len(nd))
    return a, b


def _b2b_second(games, dates):
    """For each day, True if it's the second night of a back-to-back (a game the calendar day before)."""
    out = []
    for i, g in enumerate(games):
        prev = i > 0 and games[i - 1] and dates[i - 1] and dates[i] and \
            (date.fromisoformat(dates[i]) - date.fromisoformat(dates[i - 1])).days == 1
        out.append(bool(g and prev))
    return out


def _variant(base, this, nxt, opt, n_days, blocks=(0, 0), b2b=None):
    """A copy of the player who's out until the chosen return day, then plays most nights
    (fewer on the second night of a back-to-back)."""
    q = dict(base)
    q["ir"] = False
    q["games"], q["next_games"] = list(this), list(nxt)
    if opt["week"] == "this":
        q["prob"] = [RETURN_PROB if d >= opt["i"] else 0.0 for d in range(n_days)]
        q["next_prob"] = [RETURN_PROB] * len(nxt)
    elif opt["week"] == "next":
        q["prob"] = [0.0] * n_days
        q["next_prob"] = [RETURN_PROB if j >= opt["i"] else 0.0 for j in range(len(nxt))]
    else:
        q["prob"], q["next_prob"] = [0.0] * n_days, [0.0] * len(nxt)
    q["prob"] = [0.0 if d < blocks[0] else pr for d, pr in enumerate(q["prob"])]
    q["next_prob"] = [0.0 if j < blocks[1] else pr for j, pr in enumerate(q["next_prob"])]
    if b2b:
        q["prob"] = [min(pr, B2B_PROB) if pr and b2b[0][d] else pr for d, pr in enumerate(q["prob"])]
        q["next_prob"] = [min(pr, B2B_PROB) if pr and b2b[1][j] else pr for j, pr in enumerate(q["next_prob"])]
    return q


def build(data, cfg, plan, opp_tot):
    days, nd = data["days"], data.get("next_days") or []
    watch = [x for x in data.get("injury_watch") or []
             if x.get("s") and (x.get("mine") or x["owner"] in ("Free agent", "On waivers"))]
    if not watch or not days:
        return None
    watch = sorted(watch, key=lambda x: (x.get("bucket", 9), x.get("rank") or 99))[:MAX_PLAYERS]

    t, n_days, slots, w = data["today_index"], len(days), plan["slots"], plan["weights"]
    days_left = list(range(t, n_days))
    eff = min(t + cfg.add_delay_days, n_days)
    n_this, n_next = cfg.whatif_sims, max(cfg.whatif_sims, 1200)
    opp_rows = opp_tot[:n_this]
    sofar = data["me"]["sofar"]
    nm = data.get("next_opp")
    all_mine = data["me"]["players"]
    me_active = [p for p in all_mine if not p["ir"]]

    def this_week(players_es):
        r = compare(sim_team(sorted(players_es, key=lambda e: -e.prio), days_left, sofar, n_this,
                             np.random.default_rng(123), slots), opp_rows)
        return r["win"], r["cats"]

    def next_week(roster):
        if not nm or not nd:
            return None, None
        r = nextmatch.simulate(roster, nm["players"], len(nd), slots, n_next)
        return r["win"], r["cats"]

    base_w, base_c = this_week(entries(me_active, w))
    base_nw, base_nc = next_week(all_mine)

    ranks = _season_ranks(me_active)
    droppable = sorted((p for p in me_active if not _protected(p, ranks, cfg)), key=season_value)[:MAX_DROPS]
    ir_slots = data.get("ir_slots") or 0
    ir_free = max(0, ir_slots - (data.get("ir_used") or 0))
    ir_names = [p["name"] for p in all_mine if p["ir"]]
    open_spot = len(me_active) < cfg.roster_size

    opts = _options(data)
    players = []
    for x in watch:
        mine = bool(x.get("mine"))
        own = next((p for p in all_mine if p["name"] == x["name"]), None) if mine else None
        team = (own or x)["team"]
        this, nxt = _sched(team, data, n_days, len(nd))
        if this is None:
            continue
        blocks = _claim_blocks(x, data)
        # Back-to-backs, judged across the join between this week and next (Sun then Mon counts).
        all_dates = [d["date"] for d in days] + [d["date"] for d in nd]
        sec = _b2b_second(list(this) + list(nxt), all_dates)
        b2b = (sec[:n_days], sec[n_days:])
        base = dict(own) if own else {"name": x["name"], "team": team, "id": x.get("id"), "elig": None,
                                      "status": x["status"], "s": x["s"], "long": x["s"], "tips": [None] * n_days}

        if mine:
            drops = [{"label": "He’s already on your team", "kind": "mine", "lost": 0, "lost_next": 0}]
        else:
            drops = []
            # IR is always offered, so you can see what a stash costs when nobody has to go. If it isn't
            # possible right now, the page says why.
            why_not = []
            if not ir_slots:
                why_not.append("ESPN didn’t report an IR slot in your league")
            elif not ir_free:
                why_not.append(f"your IR slot{'s are' if ir_slots > 1 else ' is'} taken by {', '.join(ir_names) or 'someone'}")
            if x["status"] != "Out":
                why_not.append(f"ESPN only allows Out players on IR and he’s listed as {x['status']}")
            drops.append({"label": "Put him on IR (no drop)" + ("" if not why_not else " – not possible right now"),
                          "kind": "ir", "why_not": why_not})
            if open_spot:
                drops.append({"label": "Use your open roster spot", "kind": "open"})
            for p in droppable:
                drops.append({"label": f"Drop {p['name']}", "kind": "drop", "p": p})
            for dp in drops:
                p = dp.get("p")
                dp["lost"] = sum(1 for d in days_left if d >= eff and p["games"][d] and p["prob"][d] > 0) if p else 0
                dp["lost_next"] = sum(1 for g, pr in zip(p.get("next_games") or [], p.get("next_prob") or [])
                                      if g and pr > 0) if p else 0

        res = []
        for dp in drops:
            drop = dp.get("p")
            others_es = []
            for p in me_active:
                if own is not None and p is own:
                    continue  # replaced by the variant below
                e = Entry(p, w)
                if p is drop:
                    e.until = eff
                others_es.append(e)
            others_next = [p for p in all_mine if p is not drop and p is not own]

            # This week: every return day from next week on is the same (he doesn't play), and next week:
            # every return day this week is the same (back for the whole week). Simulate each once.
            tw, nw = {}, {}
            row = {"w": [], "c": [], "nw": [], "nc": []}
            for o in opts:
                v = _variant(base, this, nxt, o, n_days, blocks, b2b)
                k_this = o["i"] if o["week"] == "this" else "out"
                if k_this not in tw:
                    tw[k_this] = this_week(others_es + [Entry(v, w, frm=0 if mine else eff)])
                k_next = "all" if o["week"] == "this" else (o["i"] if o["week"] == "next" else "out")
                if k_next not in nw:
                    nw[k_next] = next_week(others_next + [v])
                a, c = tw[k_this]
                b, d = nw[k_next]
                row["w"].append(round(a * 1000))
                row["c"].append(round(c * 100))
                row["nw"].append(None if b is None else round(b * 1000))
                row["nc"].append(None if d is None else round(d * 100))
            res.append(row)

        g_this, g_next = [], []
        for o in opts:
            v = _variant(base, this, nxt, o, n_days, blocks, b2b)
            g_this.append(sum(1 for d in days_left if v["games"][d] and v["prob"][d] > 0 and (mine or d >= eff)))
            g_next.append(sum(1 for g, pr in zip(v["next_games"], v["next_prob"]) if g and pr > 0))
        col_games, col_b2b = [], []
        for o in opts:
            if o["week"] == "this":
                col_games.append(bool(this[o["i"]])); col_b2b.append(b2b[0][o["i"]])
            elif o["week"] == "next":
                col_games.append(bool(nxt[o["i"]])); col_b2b.append(b2b[1][o["i"]])
            else:
                col_games.append(False); col_b2b.append(False)
        ret_label = date.fromisoformat(x["ret"]).strftime("%a %b %-d") if x.get("ret") else None
        players.append({
            "name": x["name"], "team": team, "owner": x["owner"], "status": x["status"], "mine": mine,
            "verdict": x.get("verdict"), "ret": ret_label, "default": _default(opts, x),
            "clears": x.get("waiver_clears"),
            "drops": [{k: v for k, v in dp.items() if k != "p"} for dp in drops],
            "res": res, "g": g_this, "ng": g_next, "games": col_games, "b2b": col_b2b,
        })
    if not players:
        return None
    return {"opts": [{k: o[k] for k in ("week", "label", "today")} for o in opts], "players": players,
            "base": {"w": round(base_w * 1000), "c": round(base_c * 100),
                     "nw": None if base_nw is None else round(base_nw * 1000),
                     "nc": None if base_nc is None else round(base_nc * 100)},
            "next_name": nm["name"] if nm else None, "return_prob": RETURN_PROB, "b2b_prob": B2B_PROB}
