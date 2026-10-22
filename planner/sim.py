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
    __slots__ = ("p", "frm", "until", "prio", "elig")

    def __init__(self, p, w, frm=0, until=10 ** 6):
        self.p, self.frm, self.until, self.prio = p, frm, until, value(p["s"], w)
        el = p.get("elig")
        self.elig = frozenset(el) if el else None  # None: fits any slot (no position data)


def n_slots(slots):
    return slots if isinstance(slots, int) else len(slots)


def fill_slots(elig, slots):
    """Which players start, given players in priority order and their eligible slots.

    slots is either a count (positions ignored) or a list of slot names like
    ["PG", "SG", "SF", "PF", "C", "G", "F", "UT", "UT", "UT"]. Each player in priority order gets a
    slot if one can be freed for him by moving players already placed (augmenting paths), so a
    better player is never benched just because the greedy order filled his only slot first.
    Returns (started flags, slot name for each starter or None).
    """
    k = len(elig)
    if isinstance(slots, int):
        return [i < slots for i in range(k)], [None] * k
    owner = [-1] * len(slots)  # slot index -> player index

    def fits(i, j):
        return elig[i] is None or slots[j] in elig[i]

    def place(i, seen):
        for j in range(len(slots)):
            if j in seen or not fits(i, j):
                continue
            seen.add(j)
            if owner[j] < 0 or place(owner[j], seen):
                owner[j] = i
                return True
        return False

    for i in range(k):
        if -1 not in owner:
            break
        place(i, set())
    at = {i: slots[j] for j, i in enumerate(owner) if i >= 0}
    return [i in at for i in range(k)], [at.get(i) for i in range(k)]


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
    sofar = np.asarray(sofar, float)
    tot = sofar.copy() if sofar.ndim == 2 else np.tile(sofar, (n, 1))  # 2-D: per-simulation starting totals
    for d in days:
        cand = [e for e in es if e.p["games"][d] and e.frm <= d < e.until and e.p["prob"][d] > 0]
        if not cand:
            continue
        probs = np.array([e.p["prob"][d] for e in cand])
        avail = rng.random((n, len(cand))) < probs
        if isinstance(slots, int) or len(cand) <= 0:
            started = avail & (np.cumsum(avail, axis=1) <= n_slots(slots))
        else:
            # Lineups depend on who's available; solve each distinct availability pattern once.
            pats, inv = np.unique(avail, axis=0, return_inverse=True)
            table = np.zeros_like(pats)
            for r, pat in enumerate(pats):
                idx = np.flatnonzero(pat)
                on, _ = fill_slots([cand[j].elig for j in idx], slots)
                table[r, idx[np.array(on, bool)]] = True
            started = table[inv.reshape(-1)]
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


def lineup_slots(data, cfg):
    """The league's active lineup slots by position, or a plain count if positions are unknown."""
    sl = list(cfg.lineup_slots or data.get("lineup_slots") or [])
    if not sl or not any(p.get("elig") for p in data["me"]["players"]):
        return cfg.active_slots
    return sl


def build_plan(data, cfg):
    from dataclasses import replace
    cfg = replace(cfg, active_slots=lineup_slots(data, cfg))
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

    picks, pick_note = _pickups(data, cfg, me_players, w, days_left, opp_tot)
    stream = _stream_plan(data, cfg, me_players, w, days_left, opp_tot)
    plan_es = sorted(stream.pop("entries", None) or my_es, key=lambda e: -e.prio)
    lineup = _lineups(data, plan_es, entries(opp_players, EQUAL), days_left, slots)
    from . import whatif
    return {"result": res, "weights": w, "lineup": lineup, "picks": picks, "pick_note": pick_note,
            "stream": stream, "notes": _notes(data, cfg, res, lineup), "trends": _trends(data),
            "whatif": whatif.grid(data, cfg, w, opp_tot), "scenario": whatif.scenario(data, cfg, w, opp_tot, res)}


def _lineups(data, my_es, opp_es, days_left, slots):
    out = []
    for d in days_left:
        mine = [e for e in my_es if e.p["games"][d] and e.p["prob"][d] > 0 and e.frm <= d < e.until]
        theirs = [e for e in opp_es if e.p["games"][d] and e.p["prob"][d] > 0]
        on, at = fill_slots([e.elig for e in mine], slots)
        start = [e for e, x in zip(mine, on) if x]
        bench = [e for e, x in zip(mine, on) if not x]
        # Benched although a slot is empty: no open slot he's eligible for.
        squeezed = [e.p["name"] for e in bench] if len(start) < n_slots(slots) else []
        out.append({"day": data["days"][d]["label"],
                    "start": [(e.p["name"], e.p["prob"][d], e.p["status"]) for e in start],
                    "slot": [a for a, x in zip(at, on) if x],
                    "bench": [e.p["name"] for e in bench], "squeezed": squeezed,
                    "open": max(0, n_slots(slots) - len(start)),
                    "opp_games": sum(fill_slots([e.elig for e in theirs], slots)[0])})
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
            if drop is not None and not _cuttable(drop, fa):
                continue
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
        if best is not None:
            out.append(best)
    if not out:
        return [], "Every pickup would mean cutting a regular who's better than him over the season."
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


def _stream_plan(data, cfg, me_players, w, days_left, opp_tot):
    """Greedy week-long streaming schedule: each step adds the single add/drop (on any remaining day)
    that raises the chance of winning the week the most, until adds run out or nothing helps."""
    used = data.get("adds_used") or 0
    budget = cfg.max_adds - used - cfg.reserve_adds
    eff0 = data["today_index"] + cfg.add_delay_days
    out = {"moves": [], "before": None, "after": None, "note": None}
    if budget <= 0:
        out["note"] = (f"No adds to plan with: {used} of {cfg.max_adds} used"
                       + (f" and {cfg.reserve_adds} kept in reserve for injuries." if cfg.reserve_adds else "."))
        return out
    if eff0 >= len(data["days"]):
        out["note"] = "No days left for a streamer to play in this matchup."
        return out

    n, BIG = cfg.plan_sims, 10 ** 6
    opp = opp_tot[:n]
    sofar = data["me"]["sofar"]

    def evaluate(items, sims=n, opp_rows=opp):
        es = sorted((Entry(i["p"], w, i["frm"], i["until"]) for i in items), key=lambda e: -e.prio)
        return compare(sim_team(es, days_left, sofar, sims, np.random.default_rng(57), cfg.active_slots), opp_rows)

    def score(r):
        return r["win"] + 0.02 * r["cats"]

    def games_from(p, t, until=BIG):
        return sum(p["prob"][d] for d in days_left if t <= d < until and p["games"][d])

    items = [{"p": p, "frm": 0, "until": BIG, "stream": False} for p in me_players]
    core = {id(p) for p in sorted(me_players, key=lambda p: -value(p["s"], w))[:6]}
    keep = set(cfg.keep_players)
    regular_drops = sorted((i for i in items if id(i["p"]) not in core and i["p"]["name"].lower() not in keep),
                           key=lambda i: value(i["p"]["s"], w) * games_from(i["p"], eff0))[:4]
    fas = sorted((p for p in data["fa"] if games_from(p, eff0) > 0),
                 key=lambda p: -value(p["s"], w) * games_from(p, eff0))[:12]
    if not fas:
        out["note"] = "No free agents with games left this week."
        return out

    def fits(cand):
        for d in days_left:
            if sum(1 for i in cand if i["frm"] <= d < i["until"]) > cfg.roster_size:
                return False
        return True

    current = evaluate(items)
    start = current
    used_fa = set()
    for _ in range(budget):
        best, options = None, []
        regular_ids = {id(i["p"]) for i in regular_drops}
        drop_pool = [k for k, i in enumerate(items) if i["until"] == BIG and (i["stream"] or id(i["p"]) in regular_ids)]
        for fa in fas:
            if id(fa) in used_fa:
                continue
            for t in (d for d in days_left if d >= eff0 and fa["games"][d] and fa["prob"][d] > 0):
                for k in drop_pool + [None]:
                    drop = items[k] if k is not None else None
                    if drop is not None and drop["stream"] and drop["frm"] >= t:
                        continue
                    if drop is not None and not drop["stream"] and not _cuttable(drop["p"], fa):
                        continue
                    cand = [dict(i) for i in items]
                    if drop is not None:
                        cand[k]["until"] = t
                    cand.append({"p": fa, "frm": t, "until": BIG, "stream": True})
                    if not fits(cand):
                        continue
                    r = evaluate(cand)
                    # Cutting a regular is permanent, so it has to beat recycling a streamer spot clearly.
                    gain = score(r) - score(current) - (0.025 if drop is not None and not drop["stream"] else 0)
                    options.append((gain, r["win"], fa, t, drop))
                    if best is None or gain > best[0]:
                        best = (gain, cand, r, fa, t, drop)
        if best is None or best[0] <= 0 or best[2]["win"] - current["win"] < 0.01:
            break
        gain, items, current, fa, t, drop = best
        used_fa.add(id(fa))
        # Runner-up moves on the same day: a different add, or the same add with a different drop.
        alts, seen = [], {(id(fa), id(drop["p"]) if drop else None)}
        for g, win, afa, at, adrop in sorted(options, key=lambda o: -o[0]):
            key = (id(afa), id(adrop["p"]) if adrop else None)
            if at != t or key in seen or g <= 0:
                continue
            seen.add(key)
            alts.append({"add": afa["name"], "add_team": afa["team"],
                         "drop": adrop["p"]["name"] if adrop else None,
                         "drop_is_streamer": bool(adrop and adrop["stream"]),
                         "behind": round((current["win"] - win) * 100)})
            if len(alts) == 3:
                break
        out["moves"].append({"day": t, "add": fa, "drop": drop["p"] if drop else None, "alts": alts})

    if not out["moves"]:
        out["note"] = "No streaming moves raise your chance of winning by at least 1 point. Hold your adds for injury news."
        return out

    # Re-check the finished plan with the full simulation count.
    before = evaluate([{"p": p, "frm": 0, "until": BIG} for p in me_players], cfg.sims, opp_tot)
    after = evaluate(items, cfg.sims, opp_tot)
    out["before"], out["after"] = before["win"], after["win"]
    out["cats_before"], out["cats_after"] = before["cats"], after["cats"]
    final_until = {id(i["p"]): i["until"] for i in items}
    moves = []
    for m in sorted(out["moves"], key=lambda m: m["day"]):
        fa, t = m["add"], m["day"]
        until = final_until.get(id(fa), BIG)
        add_days = [data["days"][d]["label"].split()[0] for d in days_left if t <= d < until and fa["games"][d]]
        drop = m["drop"]
        drop_days = []
        if drop is not None:
            frm = next((i["frm"] for i in items if i["p"] is drop), 0)
            drop_days = [data["days"][d]["label"].split()[0] for d in days_left if max(frm, data["today_index"]) <= d < t and drop["games"][d]]
        act = max(data["today_index"], t - cfg.add_delay_days)  # day you make the move in ESPN
        moves.append({"day": data["days"][act]["label"], "today": act == data["today_index"],
                      "plays_from": data["days"][t]["label"] if act != t else None,
                      "add": fa["name"], "add_team": fa["team"], "add_status": fa["status"], "add_days": add_days,
                      "trend": fa.get("trend"), "drop": drop["name"] if drop else None, "drop_days_used": drop_days,
                      "drop_is_streamer": bool(drop is not None and any(x["add"] is drop for x in out["moves"])),
                      "alts": m["alts"]})
    out["moves"] = moves
    out["adds_planned"] = len(moves)
    out["adds_left_after"] = cfg.max_adds - used - len(moves)
    out["entries"] = [Entry(i["p"], w, i["frm"], i["until"]) for i in items]
    return out


def _cuttable(drop, fa):
    """A regular can be cut for good only if the incoming player is at least as good over a whole season."""
    return value(drop.get("long") or drop["s"], EQUAL) <= value(fa.get("long") or fa["s"], EQUAL)


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
