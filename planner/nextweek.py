"""Use spare adds on the last day of the matchup to set up next week.

Adds reset when the new matchup starts, so any left over on the final day are free. This picks
the free agents who add the most to next week's lineup (games on days you have room for, weighted
by how good they are), and who to drop for them without hurting this week:
- a player whose last game this matchup is still to come is dropped only after that game;
- a regular is only cut for someone at least as good over the season, as elsewhere in the planner;
  streamers you picked up this week can always go.
"""
from datetime import datetime, timedelta

from .sim import EQUAL, fill_slots, value
from .whatif import _protected, _season_ranks, season_value

BIG = 10 ** 6


def _week(players, n_days, slots):
    """Expected starter games and stat value next week, filling the lineup each day with the best available."""
    starts = val = 0.0
    for d in range(n_days):
        cand = sorted((p for p in players if p.get("next_games") and p["next_games"][d] and p["next_prob"][d] > 0),
                      key=lambda p: -season_value(p))
        on, _ = fill_slots([frozenset(p["elig"]) if p.get("elig") else None for p in cand], slots)
        for p, ok in zip(cand, on):
            if ok:
                starts += p["next_prob"][d]
                val += p["next_prob"][d] * value(p.get("long") or p["s"], EQUAL)
    return starts, val


def _days(p, next_days):
    return [next_days[d]["label"].split()[0] for d in range(len(next_days)) if p["next_games"][d] and p["next_prob"][d] > 0]


def plan(data, cfg, plan_):
    days, nd = data["days"], data.get("next_days") or []
    out = {"moves": [], "note": None, "day": days[-1]["label"] if days else None,
           "range": f'{nd[0]["label"]} to {nd[-1]["label"]}' if nd else None}
    if not days or not nd or not any(p.get("next_games") for p in data["me"]["players"]):
        out["note"] = "Next week’s schedule isn’t available yet."
        return out
    last = len(days) - 1
    out["today"] = data["today_index"] == last
    st = plan_.get("stream") or {}
    adds_left = st["adds_left_after"] if st.get("moves") else cfg.max_adds - (data.get("adds_used") or 0)
    out["adds_left"] = max(0, adds_left)

    # Your roster as it will stand at the end of this week, after the streaming plan.
    es = plan_.get("plan_entries")
    if es:
        roster = [e.p for e in es if e.until >= BIG]
        streamers = {id(e.p) for e in es if e.until >= BIG and e.frm > 0}
    else:
        roster = [p for p in data["me"]["players"] if not p["ir"]]
        streamers = set()
    slots = plan_["slots"]
    n = len(nd)
    out["open_spots"] = max(0, cfg.roster_size - len(roster))
    base_starts, base_val = _week(roster, n, slots)
    out["base_starts"] = base_starts
    out["roster_games"] = sorted(((p["name"], len(_days(p, nd))) for p in roster), key=lambda x: x[1])

    if adds_left <= 0:
        out["note"] = ("You’ll have no adds left after this week’s streaming plan, so start next week with your "
                       "current roster and use Monday’s fresh adds.")
        return out

    # Anyone on your roster now, or picked up or dropped by this week's plan, is off the table:
    # a player you drop goes on waivers and usually can't be re-added straight away.
    touched = [e.p for e in es] if es else []
    taken = {p["name"] for p in roster + touched + data["me"]["players"]}
    pool = [p for p in data["fa"] if p.get("next_games") and p["name"] not in taken]
    pool.sort(key=lambda p: -season_value(p) * sum(g * pr for g, pr in zip(p["next_games"], p["next_prob"])))
    pool = pool[:20]
    keep = set(cfg.keep_players)
    open_spots = out["open_spots"]
    cur, cur_starts, cur_val = list(roster), base_starts, base_val
    min_gain = max(2.0, 0.03 * base_val)  # ignore swaps that barely move next week

    for _ in range(min(adds_left, 4)):
        ranks = _season_ranks(cur)
        drops = [None] if open_spots > 0 else []
        drops += [p for p in cur if id(p) in streamers or not _protected(p, ranks, cfg)]
        best = None
        for fa in pool:
            for dp in drops:
                if dp is not None and dp["name"].lower() in keep:
                    continue
                if dp is not None and id(dp) not in streamers and season_value(dp) > season_value(fa):
                    continue  # a permanent cut has to be for a better player
                trial = [p for p in cur if p is not dp] + [fa]
                s_, v_ = _week(trial, n, slots)
                gain = v_ - cur_val
                # Dropping someone who still plays on the last day means waiting until his game ends,
                # often late at night UK time, so it has to be clearly better than a drop you can do any time.
                waits = bool(dp and dp["games"][last] and dp["prob"][last] > 0)
                score = gain - (min_gain if waits else 0)
                if gain >= min_gain and score > 0 and (best is None or score > best[0]):
                    best = (score, fa, dp, s_, v_, gain)
        if best is None:
            break
        _, fa, dp, s_, v_, gain = best
        plays_last = bool(dp and dp["games"][last] and dp["prob"][last] > 0)
        tip = (dp.get("tips") or [None] * len(days))[last] if plays_last else None
        free_from = (datetime.fromisoformat(tip) + timedelta(hours=2, minutes=45)).isoformat() if tip else None
        out["moves"].append({
            "add": fa["name"], "add_team": fa["team"], "add_status": fa["status"], "add_days": _days(fa, nd),
            "drop": dp["name"] if dp else None, "drop_days": _days(dp, nd) if dp else [],
            "drop_after_game": plays_last, "free_from": free_from, "drop_is_streamer": bool(dp and id(dp) in streamers),
            "starts_gain": s_ - cur_starts, "trend": fa.get("trend"),
        })
        cur = [p for p in cur if p is not dp] + [fa]
        pool = [p for p in pool if p is not fa]
        if dp is None:
            open_spots -= 1
        cur_starts, cur_val = s_, v_
    out["after_starts"] = cur_starts
    out["adds_spare"] = out["adds_left"] - len(out["moves"])
    if not out["moves"]:
        out["note"] = ("No free agent improves next week’s lineup by enough to be worth it. "
                       "Keep the adds for a late injury this week instead.")
    stash = [x["name"] for x in data.get("injury_watch") or []
             if x.get("bucket", 9) <= 1 and x["owner"] in ("Free agent", "On waivers")]
    out["stash"] = stash if out["adds_spare"] > 0 else []
    return out
