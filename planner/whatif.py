"""What-if scenarios: how would adding (and dropping) certain players change this matchup?

Two pieces:
- grid(): every free agent in the pool crossed with every possible drop, simulated at build time so
  the page can show any combination instantly from two dropdowns.
- scenario(): a custom move typed into the WHAT_IF setting or the "Run workflow" box, for players who
  aren't in the free-agent pool (trade targets, your opponent's players, deeper waiver names).
  Format:  add: Jalen Brunson, Naz Reid; drop: Grant Sato, Luca Varga; day: Wed
"""
import re
import unicodedata

import numpy as np

from .sim import CATS, EQUAL, Entry, compare, entries, fill_slots, sim_team, value


# ---------- parsing and name matching ----------

def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower().replace("-", " ")
    return " ".join(re.sub(r"[^a-z0-9 ]", "", s).split())


def match(query, names):
    """Indices of names matching query: an exact match wins, else every word must start a word in the name."""
    q = norm(query)
    exact = [i for i, n in enumerate(names) if norm(n) == q]
    if exact:
        return exact
    qt = q.split()
    return [i for i, n in enumerate(names) if qt and all(any(w.startswith(t) for w in norm(n).split()) for t in qt)]


def parse(text):
    adds, drops, day = [], [], None
    for part in re.split(r"[;\n]", text or ""):
        if ":" not in part:
            continue
        key, val = part.split(":", 1)
        key = key.strip().lower()
        names = [n.strip() for n in val.split(",") if n.strip()]
        if key.startswith(("add", "get", "trade for", "pick")):
            adds += names
        elif key.startswith(("drop", "cut", "give", "trade away")):
            drops += names
        elif key in ("day", "from", "on", "when"):
            day = val.strip()
    return adds, drops, day


# ---------- shared helpers ----------

def season_value(p):
    """Per-game value over the whole season (the steadier blend), all categories equal."""
    return value(p.get("long") or p["s"], EQUAL)


def _season_ranks(players):
    """1-based rank of each player on the roster by season-long value, keyed by id()."""
    ranked = sorted(players, key=season_value, reverse=True)
    return {id(p): i + 1 for i, p in enumerate(ranked)}


def _protected(p, ranks, cfg):
    """Players the planner never suggests cutting: your top 6 over the season and KEEP_PLAYERS."""
    return ranks.get(id(p), 99) <= 6 or p["name"].lower() in set(cfg.keep_players)


def _games(p, days, frm, until=10 ** 6):
    return sum(1 for d in days if frm <= d < until and p["games"][d] and p["prob"][d] > 0)


def _starts(es, days, slots):
    """Expected starter games: on each day the best players with a game fill the active slots."""
    total = 0.0
    for d in days:
        cand = sorted((e for e in es if e.p["games"][d] and e.frm <= d < e.until and e.p["prob"][d] > 0),
                      key=lambda e: -e.prio)
        on, _ = fill_slots([e.elig for e in cand], slots)
        total += sum(e.p["prob"][d] for e, x in zip(cand, on) if x)
    return total


def _my_entries(me_players, w, drops, adds, t):
    es = []
    for p in me_players:
        e = Entry(p, w)
        if any(p is x for x in drops):
            e.until = t
        es.append(e)
    es += [Entry(p, w, frm=t) for p in adds]
    return sorted(es, key=lambda e: -e.prio)


# ---------- the precomputed picker ----------

def grid(data, cfg, w, opp_tot):
    """Every free agent x every drop x every start day left. The days before a move are the same as
    standing pat, so they're simulated once per start day and only the days after are re-run per move."""
    days_left = list(range(data["today_index"], len(data["days"])))
    eff = data["today_index"] + cfg.add_delay_days
    me_players = [p for p in data["me"]["players"] if not p["ir"]]
    if eff >= len(data["days"]):
        return {"note": "A new pickup wouldn't get a game in this matchup."}
    fas = [p for p in data["fa"] if _games(p, days_left, eff) > 0]
    if not fas:
        return {"note": "No free agents with games left this week."}

    n, slots, sofar = cfg.whatif_sims, cfg.active_slots, data["me"]["sofar"]
    opp = opp_tot[:n]
    base_es = entries(me_players, w)
    base = compare(sim_team(base_es, days_left, sofar, n, np.random.default_rng(91), slots), opp)
    base_starts = _starts(base_es, days_left, slots)
    room = len(me_players) < cfg.roster_size
    drops = ([None] if room else []) + sorted(me_players, key=lambda p: p["name"])
    ranks = _season_ranks(me_players)

    starts = [t for t in days_left if t >= eff]
    by_day = []
    for t in starts:
        before = [d for d in days_left if d < t]
        after = [d for d in days_left if d >= t]
        pre = sim_team(base_es, before, sofar, n, np.random.default_rng(91), slots)

        def run(es):  # same luck for every move starting this day
            return sim_team(es, after, pre, n, np.random.default_rng(500 + t), slots)

        ref = compare(run(base_es), opp)  # standing pat, with this day's luck
        rows = []
        for fa in fas:
            if _games(fa, days_left, t) == 0:
                rows.append(None)
                continue
            row = []
            for drop in drops:
                es = _my_entries(me_players, w, [drop] if drop else [], [fa], t)
                r = compare(run(es), opp)
                row.append([round((r["win"] - ref["win"]) * 1000), round((r["cats"] - ref["cats"]) * 100),
                            [round((r["catP"][c] - ref["catP"][c]) * 100) for c in range(9)],
                            round((_starts(es, days_left, slots) - base_starts) * 10)])
            rows.append(row)
        act = max(data["today_index"], t - cfg.add_delay_days)
        by_day.append({"label": data["days"][t]["label"], "t": t, "today": t == data["today_index"], "act": data["days"][act]["label"] if act != t else None,
                       "add_games": [_games(p, days_left, t) for p in fas],
                       "drop_games": [0 if d is None else _games(d, days_left, t) for d in drops],
                       "rows": rows})

    def game_days(p):
        return [d for d in days_left if p["games"][d] and p["prob"][d] > 0]

    return {
        "adds": [{"name": p["name"], "team": p["team"], "status": p["status"], "trend": p.get("trend"),
                  "g": game_days(p), "sv": round(season_value(p), 3)} for p in fas],
        "drops": [{"name": "Nobody (open roster spot)", "open": True, "g": []} if d is None else
                  {"name": d["name"], "g": game_days(d), "sv": round(season_value(d), 3),
                   "rank": ranks[id(d)], "keep": _protected(d, ranks, cfg)} for d in drops],
        "dl": [{"l": x["label"].split()[0], "dt": x["date"]} for x in data["days"]],
        "days": by_day, "cats": [c[0] for c in CATS],
    }


# ---------- a custom scenario ----------

def scenario(data, cfg, w, opp_tot, res):
    if not cfg.what_if:
        return None
    adds_q, drops_q, day_q = parse(cfg.what_if)
    out = {"text": cfg.what_if, "errors": [], "notes": []}
    if not adds_q and not drops_q:
        out["errors"].append('Couldn\'t read that. Write it like "add: Jalen Brunson; drop: Grant Sato".')
        return out

    me_all = data["me"]["players"]
    opp_players = data["opp"]["players"]
    pool = ([(p, "Free agent") for p in data["fa"]] + [(p, data["opp"]["name"]) for p in opp_players]
            + [(p, p.get("owner") or "Free agent") for p in data.get("extra", [])])

    adds, owners = [], []
    for q in adds_q:
        if match(q, [p["name"] for p in me_all]) and not match(q, [p["name"] for p, _ in pool]):
            out["errors"].append(f"{q} is already on your team.")
            continue
        hits = match(q, [p["name"] for p, _ in pool])
        uniq = {}
        for i in hits:
            uniq.setdefault(pool[i][0].get("id", pool[i][0]["name"]), i)
        hits = list(uniq.values())
        if not hits:
            out["errors"].append(f"Couldn't find {q}. Check the spelling against ESPN.")
        elif len(hits) > 1:
            out["errors"].append(f"{q} matches {', '.join(pool[i][0]['name'] for i in hits[:4])}. Use the full name.")
        else:
            adds.append(pool[hits[0]][0])
            owners.append(pool[hits[0]][1])

    drops = []
    for q in drops_q:
        hits = match(q, [p["name"] for p in me_all])
        if not hits:
            out["errors"].append(f"{q} isn't on your roster.")
        elif len(hits) > 1:
            out["errors"].append(f"{q} matches {', '.join(me_all[i]['name'] for i in hits[:4])}. Use the full name.")
        else:
            drops.append(me_all[hits[0]])
    if out["errors"] or not (adds or drops):
        return out

    days_left = list(range(data["today_index"], len(data["days"])))
    eff = data["today_index"] + cfg.add_delay_days
    t = eff
    if day_q:
        found = [d for d in days_left if data["days"][d]["label"].lower().startswith(day_q.strip().lower()[:3])]
        if not found:
            out["notes"].append(f'"{day_q}" isn\'t a day left in this matchup, so the move starts as soon as possible.')
        elif found[0] < eff:
            out["notes"].append(f"Pickups can't play until {data['days'][eff]['label']}, so the move starts then.")
        else:
            t = found[0]
    if t >= len(data["days"]):
        out["errors"].append("There are no days left in this matchup for the new players to play.")
        return out

    me_players = [p for p in me_all if not p["ir"]]
    ranks = _season_ranks(me_players)
    best_add = max((season_value(a) for a in adds), default=None)
    for p in drops:
        if p["ir"]:
            continue
        worse = best_add is None or season_value(p) > best_add
        if worse or _protected(p, ranks, cfg):
            why = (f"he's your #{ranks[id(p)]} player over the season"
                   + (" and better long-term than anyone you're adding" if worse and adds else ""))
            out["notes"].append(f"Long-term check: {p['name']} is a keeper ({why}). The numbers below only cover "
                                "this matchup, and dropping him is permanent.")
    size = len(me_players) - sum(1 for p in drops if not p["ir"]) + len(adds)
    if size > cfg.roster_size:
        out["notes"].append(f"This leaves you {size - cfg.roster_size} over your {cfg.roster_size}-man roster. "
                            "The numbers assume it's allowed; add a drop to make it real.")

    slots, sofar = cfg.active_slots, data["me"]["sofar"]
    my_es = _my_entries(me_players, w, drops, adds, t)
    opp_after = opp_tot
    trade = any(any(a is p for p in opp_players) for a in adds)
    if trade:
        opp_es = []
        for p in opp_players:
            if p["ir"]:
                continue
            e = Entry(p, [1.0] * 9)
            if any(p is a for a in adds):
                e.until = t
            opp_es.append(e)
        opp_es += [Entry(p, [1.0] * 9, frm=t) for p in drops if not p["ir"]]
        opp_es.sort(key=lambda e: -e.prio)
        opp_after = sim_team(opp_es, days_left, data["opp"]["sofar"], cfg.sims, np.random.default_rng(4242), slots)
        out["notes"].append(f"Treated as a trade with {data['opp']['name']}: they lose "
                            + ", ".join(a["name"] for a in adds if any(a is p for p in opp_players))
                            + (" and get " + ", ".join(p["name"] for p in drops) if drops else "") + ".")

    after = compare(sim_team(my_es, days_left, sofar, cfg.sims, np.random.default_rng(777), slots), opp_after)
    starts_before = _starts(entries(me_players, w), days_left, slots)
    starts_after = _starts(my_es, days_left, slots)
    out.update({
        "ok": True, "day": data["days"][t]["label"], "trade": trade,
        "adds": [{"name": a["name"], "team": a["team"], "status": a["status"], "owner": o,
                  "games": _games(a, days_left, t)} for a, o in zip(adds, owners)],
        "drops": [{"name": p["name"], "games": _games(p, days_left, t)} for p in drops],
        "before": {"win": res["win"], "cats": res["cats"], "catP": res["catP"]},
        "after": {"win": after["win"], "cats": after["cats"], "catP": after["catP"]},
        "starts_delta": starts_after - starts_before,
    })
    return out
