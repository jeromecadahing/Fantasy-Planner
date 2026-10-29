"""Project next week's head-to-head against the opponent ESPN has scheduled.

Both rosters are taken as they stand today (before any moves either side makes), with each
player's next-week games and chance to play. Stats use the steadier season-long line, so this
week's recent-form tilt and USAGE_BOOST don't carry over. Lineups follow your league's position
slots, exactly as the this-week simulation does.
"""
import numpy as np

from .sim import EQUAL, compare, entries, sim_team


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


def project(data, slots, n=3000):
    nm, nd = data.get("next_opp"), data.get("next_days") or []
    if not nm or not nd:
        return None
    days = list(range(len(nd)))
    zero = [0.0] * 11
    opp = sim_team(entries(_shadow(nm["players"]), EQUAL), days, zero, n, np.random.default_rng(99), slots)
    me = sim_team(entries(_shadow(data["me"]["players"]), EQUAL), days, zero, n, np.random.default_rng(98), slots)
    res = compare(me, opp)
    res["opp_mean"] = opp.mean(0).tolist()
    res["name"] = nm["name"]
    res["same"] = bool(nm.get("same"))
    res["games"] = [sum(sum(1 for g, pr in zip(p["next_games"], p["next_prob"]) if g and pr > 0)
                        for p in _shadow(ps)) for ps in (data["me"]["players"], nm["players"])]
    return res
