"""Free agents by day: for every day left this week and every day next week, who's available,
how much each would help if he played for you that day, and who's on a back-to-back.

For each day:
  - your lineup that day: how many of your players play and how many spots are open
  - the free agents with a game that day, quickly ranked, then the best few simulated against
    your opponent with him in your lineup for that day only (a one-day stream)
  - the change in your chance to win the week and in expected categories, and which categories move
  - back-to-backs: whether he also plays the day before (second night, rest risk) or after
  - his other games that week on days you have open spots, so a multi-day streamer stands out

Each pickup needs a roster spot. The simulation counts only what his game adds; it doesn't take
away the games of whoever you drop. The section names your weakest droppable player so you can
weigh that yourself.

This week uses your roster after this week's streaming plan and what's been earned so far.
Next week uses your roster after the "Set up next week" moves, next week's opponent, season-long
numbers, and nothing earned yet.
"""
import numpy as np

from .sim import EQUAL, Entry, compare, entries, fill_slots, n_slots, sim_team, value
from .whatif import _protected, _season_ranks, season_value

CATS = ["FG%", "FT%", "3PM", "PTS", "REB", "AST", "STL", "BLK", "TO"]
BIG = 10 ** 6
PER_DAY = 5       # free agents simulated per day


def _next_view(p):
    """A copy of a player that the simulator reads with next week's schedule."""
    q = dict(p)
    q["games"], q["prob"] = p.get("next_games") or [], p.get("next_prob") or []
    q["s"] = p.get("long") or p["s"]
    return q


def _plays(p, d):
    return d < len(p["games"]) and p["games"][d] and p["prob"][d] > 0


def _day_lineup(es, d, slots):
    """Who starts on day d: (starters, bench, open spots)."""
    cand = [e for e in es if _plays(e.p, d) and e.frm <= d < e.until]
    on, _ = fill_slots([e.elig for e in cand], slots)
    start = [e for e, ok in zip(cand, on) if ok]
    bench = [e for e, ok in zip(cand, on) if not ok]
    return start, bench, max(0, n_slots(slots) - len(start))


def _quick(fa, d, es, slots, w):
    """Fast estimate of what one game from this free agent adds on day d: his value if he'd fill an
    empty spot, otherwise how much better he is than the starter he'd push out."""
    trial = sorted(es + [Entry(fa, w, d, d + 1)], key=lambda e: -e.prio)
    start, _, _ = _day_lineup(trial, d, slots)
    if not any(e.p is fa for e in start):
        return 0.0
    before, _, _ = _day_lineup(es, d, slots)
    return sum(value(e.p["s"], w) for e in start) - sum(value(e.p["s"], w) for e in before)


def _b2b(p, d, prev_game, next_game):
    """'2nd night' if he played the day before, '1st night' if he plays the day after."""
    if prev_game:
        return "2nd night"
    if next_game:
        return "1st night"
    return None


def _week(label, days, today, me_es, opp_tot, sofar, fa_pool, slots, w, n, seed, edge_prev, edge_next):
    """One week's day-by-day results.

    days: day labels; today: first day to cover; edge_prev/edge_next: per free agent name, whether
    he plays the day before this week starts / the day after it ends (for back-to-backs at the edges).
    """
    base = compare(sim_team(me_es, range(today, len(days)), sofar, n, np.random.default_rng(seed), slots), opp_tot)
    out = {"label": label, "base_win": base["win"], "base_cats": base["cats"], "days": []}
    for d in range(today, len(days)):
        start, bench, open_ = _day_lineup(me_es, d, slots)
        weakest = min(start, key=lambda e: e.prio).p["name"] if start and not open_ else None
        scored = []
        for fa in fa_pool:
            if not _plays(fa, d):
                continue
            q = _quick(fa, d, me_es, slots, w)
            if q > 0:
                scored.append((q, fa))
        scored.sort(key=lambda x: -x[0])
        rows = []
        for q, fa in scored[:PER_DAY]:
            trial = sorted(me_es + [Entry(fa, w, d, d + 1)], key=lambda e: -e.prio)
            r = compare(sim_team(trial, range(today, len(days)), sofar, n, np.random.default_rng(seed), slots), opp_tot)
            moves = sorted(((CATS[c], r["catP"][c] - base["catP"][c]) for c in range(9)), key=lambda x: -abs(x[1]))
            prev_g = _plays(fa, d - 1) if d > 0 else edge_prev.get(fa["name"], False)
            next_g = _plays(fa, d + 1) if d + 1 < len(days) else edge_next.get(fa["name"], False)
            others = [days[k].split()[0] for k in range(today, len(days))
                      if k != d and _plays(fa, k) and _day_lineup(me_es, k, slots)[2] > 0]
            rows.append({
                "name": fa["name"], "team": fa["team"], "status": fa["status"], "waiver": fa.get("waiver") if label == "This week" else None,
                "win_delta": r["win"] - base["win"], "cats_delta": r["cats"] - base["cats"],
                "up": [(c, round(v * 100)) for c, v in moves if v >= 0.015][:3],
                "down": [(c, round(v * 100)) for c, v in moves if v <= -0.015][:2],
                "b2b": _b2b(fa, d, prev_g, next_g), "open_days": others,
                "fills": bool(open_), "trend": fa.get("trend"),
            })
        rows.sort(key=lambda x: (-x["win_delta"], -x["cats_delta"]))
        out["days"].append({"label": days[d], "playing": len(start) + len(bench), "open": open_,
                            "bench": [e.p["name"] for e in bench], "weakest": weakest,
                            "options": len(scored), "rows": rows})
    return out


def build(data, cfg, plan, nextweek_plan=None):
    """Day-by-day free agents for the rest of this week and for next week."""
    slots = plan["slots"]
    n = max(200, getattr(cfg, "whatif_sims", 600))
    mine = {p["name"] for p in data["me"]["players"]}
    out = {"weeks": []}

    # ----- this week, from today
    es = plan.get("plan_entries")
    me_players = [p for p in data["me"]["players"] if not p["ir"]]
    taken = mine | ({e.p["name"] for e in es} if es else set())
    w = plan.get("weights") or EQUAL
    me_es = sorted([Entry(e.p, w, e.frm, e.until) for e in es] if es else entries(me_players, w), key=lambda e: -e.prio)
    opp_players = [p for p in data["opp"]["players"] if not p["ir"]]
    days = [d["label"] for d in data["days"]]
    today = data["today_index"]
    if today < len(days):
        opp_tot = sim_team(entries(opp_players, EQUAL), range(today, len(days)), data["opp"]["sofar"], n,
                           np.random.default_rng(4242), slots)
        pool = [p for p in data["fa"] if p["name"] not in taken and p["status"] != "Out"]
        edge_next = {p["name"]: bool((p.get("next_games") or [False])[0]) for p in pool}
        out["weeks"].append(_week("This week", days, today, me_es, opp_tot, data["me"]["sofar"], pool, slots, w,
                                  n, 777, {}, edge_next))

    # ----- next week
    nm, nd = data.get("next_opp"), data.get("next_days") or []
    if nm and nd:
        roster = [e.p for e in es if e.until >= BIG] if es else list(me_players)
        by_name = {p["name"]: p for p in data["fa"]}
        for m in (nextweek_plan or {}).get("moves") or []:
            roster = [p for p in roster if p["name"] != m.get("drop")]
            if m["add"] in by_name:
                roster.append(by_name[m["add"]])
        roster_names = {p["name"] for p in roster}
        my_next = [_next_view(p) for p in roster if p.get("next_games")]
        opp_next = [_next_view(p) for p in nm["players"] if not p.get("ir") and p.get("next_games")]
        zero = [0.0] * 11
        n_days = len(nd)
        opp_tot = sim_team(entries(opp_next, EQUAL), range(n_days), zero, n, np.random.default_rng(99), slots)
        first = compare(sim_team(entries(my_next, EQUAL), range(n_days), zero, n, np.random.default_rng(98), slots), opp_tot)
        w2 = [0.08 + 4 * p * (1 - p) for p in first["catP"]]  # lean toward the close categories, as this week does
        my_es2 = entries(my_next, w2)
        pool = [_next_view(p) for p in data["fa"] if p.get("next_games") and p["name"] not in mine | roster_names
                and p["status"] != "Out"]
        last = len(data["days"]) - 1
        edge_prev = {p["name"]: bool(p["games"][last]) for p in data["fa"] if p.get("games")}
        out["weeks"].append(_week("Next week", [d["label"] for d in nd], 0, my_es2, opp_tot, zero, pool, slots, w2,
                                  n, 98, edge_prev, {}))
        out["next_opp"] = nm["name"]

    # Weakest player you could cut for a stream spot (never a protected regular).
    ranks = _season_ranks(me_players)
    cuttable = sorted((p for p in me_players if not _protected(p, ranks, cfg)), key=season_value)
    out["cut"] = cuttable[0]["name"] if cuttable else None
    return out
