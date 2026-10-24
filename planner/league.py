"""Project every team's 9-category totals for this matchup week and rank you against the league.

Each team's week is simulated the same way as your matchup: stats already earned this week, plus
the rest of the week with each day's best available players filling the lineup. Teams are compared
on their expected final totals, and you get your chance of beating each one head-to-head.
"""
import numpy as np

from .sim import CATS, EQUAL, compare, entries, fmt_cat, sim_team


def _value(c, mean):
    _, idx, _ = CATS[c]
    if isinstance(idx, tuple):
        return mean[idx[0]] / mean[idx[1]] if mean[idx[1]] else 0.0
    return mean[idx]


def _ranks(values, c):
    """1 is best. Turnovers rank lowest-first. Ties share a rank."""
    low = CATS[c][2]
    return [1 + sum(1 for v in values if (v < x if low else v > x) and not np.isclose(v, x)) for x in values]


def table(data, cfg, plan, slots, n=1000):
    others = data.get("others") or []
    days_left = list(range(data["today_index"], len(data["days"])))
    if not days_left and not any(any(t["sofar"]) for t in others):
        return None
    me_players = [p for p in data["me"]["players"] if not p["ir"]]

    def sim(players, sofar, seed, w=EQUAL, es=None):
        es = es or entries([p for p in players if not p["ir"]], w)
        return sim_team(es, days_left, sofar, n, np.random.default_rng(seed), slots)

    mine = sim(me_players, data["me"]["sofar"], 777, w=plan["weights"])
    teams = [{"name": data["me"]["name"], "me": True, "tot": mine},
             {"name": data["opp"]["name"], "opp": True, "tot": sim(data["opp"]["players"], data["opp"]["sofar"], 4242)}]
    for i, t in enumerate(others):
        teams.append({"name": t["name"], "tot": sim(t["players"], t["sofar"], 1000 + i)})

    with_plan = None
    if plan.get("plan_entries") and (plan.get("stream") or {}).get("moves"):
        with_plan = sim(None, data["me"]["sofar"], 777, es=plan["plan_entries"])

    for t in teams:
        t["mean"] = t["tot"].mean(0).tolist()
        t["vals"] = [_value(c, t["mean"]) for c in range(9)]
        t["shown"] = [fmt_cat(c, t["mean"]) for c in range(9)]
    for c in range(9):
        for t, r in zip(teams, _ranks([t["vals"][c] for t in teams], c)):
            t.setdefault("ranks", [None] * 9)[c] = r

    plan_row = None
    if with_plan is not None:
        mean = with_plan.mean(0).tolist()
        vals = [_value(c, mean) for c in range(9)]
        # Rank the planned version of you against the other teams only.
        ranks = [_ranks([vals[c]] + [t["vals"][c] for t in teams if not t.get("me")], c)[0] for c in range(9)]
        plan_row = {"name": "With your streaming plan", "plan": True, "mean": mean, "vals": vals,
                    "shown": [fmt_cat(c, mean) for c in range(9)], "ranks": ranks}

    for t in teams:
        if t.get("me"):
            continue
        r = compare(mine, t["tot"])
        t["win"], t["cats"] = r["win"], r["cats"]
        if with_plan is not None:
            t["win_plan"] = compare(with_plan, t["tot"])["win"]

    # Your actual opponent: use the main plan's numbers, which come from a bigger simulation,
    # so this table always agrees with the scoreboard and the streaming plan.
    opp = teams[1]
    opp["win"], opp["cats"] = plan["result"]["win"], plan["result"]["cats"]
    st = plan.get("stream") or {}
    if with_plan is not None and st.get("after") is not None:
        opp["win_plan"] = st["after"]

    me = teams[0]
    rivals = [t for t in teams if not t.get("me")]
    return {
        "teams": [{k: v for k, v in t.items() if k != "tot"} for t in teams],
        "plan_row": plan_row,
        "n_teams": len(teams),
        "beats": sum(1 for t in rivals if t["win"] > 0.5),
        "beats_plan": sum(1 for t in rivals if t.get("win_plan", 0) > 0.5) if with_plan is not None else None,
        "avg_rank": sum(me["ranks"]) / 9,
        "partial": not others,
    }
