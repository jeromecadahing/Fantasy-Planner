"""Project next week's head-to-head against the opponent ESPN has scheduled.

Both rosters are taken as they stand today (before any moves either side makes), with each
player's next-week games and chance to play. Stats use the steadier season-long line, so this
week's recent-form tilt and USAGE_BOOST don't carry over. Lineups follow your league's position
slots, exactly as the this-week simulation does.
"""
import numpy as np

from .sim import EQUAL, compare, entries, sim_team, volume_table


def _shadow(players):
    """Copies of players that the simulator reads as next week's schedule."""
    out = []
    for p in players:
        if p.get("ir") or not p.get("next_games"):
            continue
        q = dict(p)
        q["games"], q["prob"] = p["next_games"], p["next_prob"]
        q["s"] = p.get("long") or p["s"]
        out.append(q)
    return out


def simulate(me_players, opp_players, n_days, slots, n=3000):
    """Next week's result for two rosters. The same seeds every time, so two versions of your
    roster (say, before and after a what-if) are compared on the same luck."""
    days = list(range(n_days))
    zero = [0.0] * 11
    opp = sim_team(entries(_shadow(opp_players), EQUAL), days, zero, n, np.random.default_rng(99), slots)
    me = sim_team(entries(_shadow(me_players), EQUAL), days, zero, n, np.random.default_rng(98), slots)
    res = compare(me, opp)
    res["opp_mean"] = opp.mean(0).tolist()
    res["games"] = [sum(sum(1 for g, pr in zip(p["next_games"], p["next_prob"]) if g and pr > 0)
                        for p in _shadow(ps)) for ps in (me_players, opp_players)]
    return res


def project(data, slots, n=3000):
    nm, nd = data.get("next_opp"), data.get("next_days") or []
    if not nm or not nd:
        return None
    res = simulate(data["me"]["players"], nm["players"], len(nd), slots, n)
    res["name"] = nm["name"]
    res["same"] = bool(nm.get("same"))
    return res


def volume(data, plan, nextweek_plan, slots):
    """Next week's starter games per day and 4-game players: your roster as it stands today, your roster
    after this week's streaming plan and the Set up next week moves, and next week's opponent."""
    nm, nd = data.get("next_opp"), data.get("next_days") or []
    if not nm or not nd:
        return None
    now = [p for p in data["me"]["players"] if not p["ir"]]
    es = plan.get("plan_entries")
    roster = [e.p for e in es if e.until >= 10 ** 6] if es else list(now)
    moves = (nextweek_plan or {}).get("moves") or []
    by_name = {p["name"]: p for p in data["fa"]}
    for m in moves:
        roster = [p for p in roster if p["name"] != m.get("drop")]
        if m["add"] in by_name:
            roster.append(by_name[m["add"]])
    changed = {p["name"] for p in roster} != {p["name"] for p in now}
    days = list(range(len(nd)))
    out = volume_table([d["label"] for d in nd], days, 0,
                       entries(_shadow(now), EQUAL), entries(_shadow(roster), EQUAL) if changed else None,
                       entries(_shadow(nm["players"]), EQUAL), slots)
    out["opp_name"] = nm["name"]
    return out
