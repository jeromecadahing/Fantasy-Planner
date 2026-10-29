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
