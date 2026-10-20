"""Simulate the rest of the matchup, then build the lineup, pickup and strategy plan."""
import numpy as np

# (label, totals index or (makes, attempts), lower is better)
CATS = [("FG%", (0, 1), False), ("FT%", (2, 3), False), ("3PM", 4, False), ("PTS", 5, False),
        ("REB", 6, False), ("AST", 7, False), ("STL", 8, False), ("BLK", 9, False), ("TO", 10, True)]
EQUAL = [1.0] * 9


def value(s, w):
    """Per-game value of a stat line, weighted toward the categories that matter."""
    pts = 2 * s["fgm"] + s["tpm"] + s["ftm"]
    return (w[0] * (s["fgm"] - s["fga"] * 0.475) + w[1] * (s["ftm"] - s["fta"] * 0.78) / 0.6
            + w[2] * s["tpm"] + w[3] * pts / 6 + w[4] * s["reb"] / 2.5 + w[5] * s["ast"] / 2
            + w[6] * s["stl"] / 0.6 + w[7] * s["blk"] / 0.6 - w[8] * s["to"])


class Entry:
    __slots__ = ("p", "frm", "until", "prio")

    def __init__(self, p, w, frm=0, until=10 ** 6):
        self.p, self.frm, self.until, self.prio = p, frm, until, value(p["s"], w)


def entries(players, w, frm=0):
    es = [Entry(p, w, frm) for p in players if not p.get("ir")]
    return sorted(es, key=lambda e: -e.prio)


def _game_stats(s, k, rng):
    f = np.clip(1 + 0.18 * rng.standard_normal(k), 0.35, 1.6)
    fga = rng.poisson(s["fga"] * f)
    fgm = rng.binomial(fga, min(1.0, s["fgm"] / s["fga"]) if s["fga"] > 0 else 0.0)
    tpm = rng.binomial(fgm, min(1.0, s["tpm"] / s["fgm"]) if s["fgm"] > 0 else 0.0)
    fta = rng.poisson(s["fta"] * f)
    ftm = rng.binomial(fta, min(1.0, s["ftm"] / s["fta"]) if s["fta"] > 0 else 0.0)
    out = np.empty((k, 11))
    out[:, 0], out[:, 1], out[:, 2], out[:, 3], out[:, 4] = fgm, fga, ftm, fta, tpm
    out[:, 5] = 2 * fgm + tpm + ftm
    for col, key in ((6, "reb"), (7, "ast"), (8, "stl"), (9, "blk"), (10, "to")):
        out[:, col] = rng.poisson(s[key] * f)
    return out


def sim_team(es, days, sofar, n, rng, slots):
    """n simulated final stat totals. Each day the best available players fill the active slots."""
    tot = np.tile(np.asarray(sofar, float), (n, 1))
    for d in days:
        cand = [e for e in es if e.p["games"][d] and e.frm <= d < e.until and e.p["prob"][d] > 0]
        if not cand:
            continue
        probs = np.array([e.p["prob"][d] for e in cand])
        avail = rng.random((n, len(cand))) < probs
        started = avail & (np.cumsum(avail, axis=1) <= slots)
        for j, e in enumerate(cand):
            mask = started[:, j]
            k = int(mask.sum())
            if k:
                tot[mask] += _game_stats(e.p["s"], k, rng)
    return tot


def _cat(t, idx):
    if isinstance(idx, tuple):
        m, a = t[:, idx[0]], t[:, idx[1]]
        return np.divide(m, a, out=np.zeros_like(m), where=a > 0)
    return t[:, idx]


def compare(me, opp):
    res = np.zeros((len(me), 9))
    for c, (_, idx, low) in enumerate(CATS):
        a, b = _cat(me, idx), _cat(opp, idx)
        better = a < b if low else a > b
        res[:, c] = np.where(np.isclose(a, b), 0.5, better.astype(float))
    wins, losses = (res == 1).sum(1), (res == 0).sum(1)
    win = np.where(wins > losses, 1.0, np.where(wins == losses, 0.5, 0.0))
    return {"catP": res.mean(0).tolist(), "cats": float(res.sum(1).mean()), "win": float(win.mean()),
            "mean": me.mean(0).tolist()}


def fmt_cat(c, mean):
    _, idx, _ = CATS[c]
    if isinstance(idx, tuple):
        v = mean[idx[0]] / mean[idx[1]] if mean[idx[1]] else 0
        return f"{v:.3f}".lstrip("0")
    return f"{round(mean[idx])}"


def build_plan(data, cfg):
    days_left = list(range(data["today_index"], len(data["days"])))
    slots = cfg.active_slots
    me_players = [p for p in data["me"]["players"] if not p["ir"]]
    opp_players = [p for p in data["opp"]["players"] if not p["ir"]]

    opp_tot = sim_team(entries(opp_players, EQUAL), days_left, data["opp"]["sofar"], cfg.sims,
                       np.random.default_rng(4242), slots)
    first = compare(sim_team(entries(me_players, EQUAL), days_left, data["me"]["sofar"], cfg.sims,
                             np.random.default_rng(777), slots), opp_tot)
    w = [0.08 + 4 * p * (1 - p) for p in first["catP"]]
    my_es = entries(me_players, w)
    res = compare(sim_team(my_es, days_left, data["me"]["sofar"], cfg.sims, np.random.default_rng(777), slots), opp_tot)
    res["opp_mean"] = opp_tot.mean(0).tolist()

    lineup = _lineups(data, my_es, entries(opp_players, EQUAL), days_left, slots)
    picks, pick_note = _pickups(data, cfg, me_players, w, days_left, opp_tot)
    return {"result": res, "weights": w, "lineup": lineup, "picks": picks, "pick_note": pick_note,
            "notes": _notes(data, cfg, res, lineup), "trends": _trends(data)}


def _lineups(data, my_es, opp_es, days_left, slots):
    out = []
    for d in days_left:
        mine = [e for e in my_es if e.p["games"][d] and e.p["prob"][d] > 0]
        theirs = [e for e in opp_es if e.p["games"][d] and e.p["prob"][d] > 0]
        out.append({"day": data["days"][d]["label"],
                    "start": [(e.p["name"], e.p["prob"][d], e.p["status"]) for e in mine[:slots]],
                    "bench": [e.p["name"] for e in mine[slots:]],
                    "open": max(0, slots - len(mine)), "opp_games": min(slots, len(theirs))})
    return out


def _pickups(data, cfg, me_players, w, days_left, opp_tot):
    used = data.get("adds_used")
    left = cfg.max_adds - (used or 0)
    if left <= 0:
        return [], f"You've used all {cfg.max_adds} adds this week. Your lever now is the daily lineup."
    eff = data["today_index"] + cfg.add_delay_days
    if eff >= len(data["days"]):
        return [], "A new pickup wouldn't get a game in this matchup."
    eff_days = [d for d in days_left if d >= eff]

    def rem(p):
        return value(p["s"], w) * sum(p["prob"][d] for d in eff_days if p["games"][d])

    fas = sorted((p for p in data["fa"] if rem(p) > 0), key=rem, reverse=True)[:15]
    if not fas:
        return [], "No free agents with games left this week."
    core = {id(p) for p in sorted(me_players, key=lambda p: -value(p["s"], w))[:6]}
    keep = set(cfg.keep_players)
    drops = sorted((p for p in me_players if id(p) not in core and p["name"].lower() not in keep), key=rem)[:4]
    cands = ([None] if len(me_players) < cfg.roster_size else []) + drops
    if not cands:
        return [], "Every droppable player is on your KEEP_PLAYERS list."

    n = cfg.pickup_sims
    opp = opp_tot[:n]
    base = compare(sim_team(entries(me_players, w), days_left, data["me"]["sofar"], n,
                            np.random.default_rng(31), cfg.active_slots), opp)
    out = []
    for fa in fas:
        best = None
        for drop in cands:
            es = []
            for p in me_players:
                e = Entry(p, w)
                if p is drop:
                    e.until = eff
                es.append(e)
            es.append(Entry(fa, w, frm=eff))
            es.sort(key=lambda e: -e.prio)
            r = compare(sim_team(es, days_left, data["me"]["sofar"], n, np.random.default_rng(31), cfg.active_slots), opp)
            score = (r["win"] - base["win"]) + 0.02 * (r["cats"] - base["cats"])
            if best is None or score > best["score"]:
                best = {"score": score, "add": fa, "drop": drop, "r": r}
        out.append(best)
    out.sort(key=lambda x: -x["score"])

    picks = []
    for x in out[:5]:
        moves = [(CATS[c][0], round((x["r"]["catP"][c] - base["catP"][c]) * 100)) for c in range(9)]
        moves = sorted((m for m in moves if abs(m[1]) >= 3), key=lambda m: -m[1])
        picks.append({
            "add": x["add"]["name"], "add_team": x["add"]["team"], "trend": x["add"].get("trend"),
            "status": x["add"]["status"],
            "games": sum(1 for d in eff_days if x["add"]["games"][d]),
            "drop": x["drop"]["name"] if x["drop"] else None,
            "drop_games": sum(1 for d in eff_days if x["drop"]["games"][d]) if x["drop"] else 0,
            "win_delta": round((x["r"]["win"] - base["win"]) * 100),
            "cats_delta": x["r"]["cats"] - base["cats"],
            "up": [m for m in moves if m[1] > 0][:3], "down": [m for m in moves if m[1] < 0][-2:],
        })
    note = None
    if picks and picks[0]["win_delta"] < 1:
        note = "No pickup moves this matchup by much. Consider saving adds for injury news later in the week."
    if used is None:
        note = ((note + " ") if note else "") + "Couldn't read your adds used from ESPN, so this assumes you have adds left."
    return picks, note


def _join(xs):
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def _notes(data, cfg, res, lineup):
    p = res["catP"]
    safe = [CATS[i][0] for i in range(9) if p[i] >= 0.8]
    lost = [CATS[i][0] for i in range(9) if p[i] < 0.2]
    swing = [CATS[i][0] for i in range(9) if 0.2 <= p[i] < 0.8]
    n = []
    if swing:
        n.append(f"Swing categories: {_join(swing)}. Pickups and start/sit choices are aimed at these.")
    if safe:
        n.append(f"{_join(safe)} {'are' if len(safe) > 1 else 'is'} safe. Don’t spend adds on {'them' if len(safe) > 1 else 'it'}.")
    if lost:
        n.append(f"Concede {_join(lost)}. Your chance is under 20%, so the plan stops chasing {'them' if len(lost) > 1 else 'it'}.")
    my_g = sum(len(d["start"]) for d in lineup)
    op_g = sum(d["opp_games"] for d in lineup)
    v = f"You have {my_g} starter games left; {data['opp']['name']} has {op_g}."
    if my_g < op_g - 2:
        v += " You’re short on volume, so streaming players with games on your open days is the fastest fix."
    elif my_g > op_g + 2:
        v += " The volume edge is yours. Keep every lineup spot filled to hold it."
    n.append(v)
    wasted = sum(len(d["bench"]) for d in lineup)
    open_ = sum(d["open"] for d in lineup)
    if wasted:
        n.append(f"{wasted} of your games land on days when every active spot is already full, so they’ll sit on the bench.")
    if open_:
        n.append(f"You have {open_} empty lineup spots across the rest of the week. A streamer who plays on those days adds pure volume.")
    if 0.4 <= p[0] < 0.8:
        n.append("FG% is close. Late in the week, avoid starting low-percentage, high-volume shooters if you’re ahead.")
    if 0.4 <= p[1] < 0.8:
        n.append("FT% is close. Late in the week, be careful starting poor free-throw shooters who get to the line a lot.")
    if 0.4 <= p[8] < 0.8:
        n.append("TO is close. If you’re protecting it on the last day, bench your most turnover-prone guard.")
    if data.get("sofar_note"):
        n.append(data["sofar_note"])
    return n


def _trends(data):
    rows = []
    for who, players in (("Your team", data["me"]["players"]), (data["opp"]["name"], data["opp"]["players"])):
        for p in players:
            if p["ir"]:
                continue
            if p["status"] != "Healthy":
                rows.append((who, p["name"], p["status"]))
            if p.get("trend"):
                rows.append((who, p["name"], p["trend"]))
    for p in data["fa"][:40]:
        if p.get("trend", "") and p["trend"].startswith("Minutes up"):
            rows.append(("Free agent", p["name"], p["trend"]))
    return rows[:30]
