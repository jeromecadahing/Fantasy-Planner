"""Options for each injured player on your roster (Out, Doubtful or Suspended, not already on IR).

For each one, every realistic choice is simulated against your opponent for the rest of the week:
hold him, move him to IR and use the freed spot, keep him and cut your weakest player, or drop him.
Then two return scenarios show how much his timeline matters.
"""
import numpy as np

from .sim import CATS, Entry, compare, sim_team, value
from .whatif import _protected, _season_ranks, _starts, season_value

HURT = {"Out", "Suspended", "Doubtful"}


def _rem(p, days):
    return sum(p["prob"][d] for d in days if p["games"][d])


def _moves(r, base):
    m = [(CATS[c][0], round((r["catP"][c] - base["catP"][c]) * 100)) for c in range(9)]
    m = sorted((x for x in m if abs(x[1]) >= 3), key=lambda x: -x[1])
    return [x for x in m if x[1] > 0][:3], [x for x in m if x[1] < 0][-2:]


def build(data, cfg, plan):
    me = [p for p in data["me"]["players"] if not p["ir"]]
    hurt = [p for p in me if p["status"] in HURT]
    if not hurt:
        return []
    w, opp_tot, slots = plan["weights"], plan["opp_tot"], plan["slots"]
    ti = data["today_index"]
    days_left = list(range(ti, len(data["days"])))
    eff = ti + cfg.add_delay_days
    eff_days = [d for d in days_left if d >= eff]
    n = cfg.pickup_sims
    opp = opp_tot[:n]
    sofar = data["me"]["sofar"]
    adds_left = cfg.max_adds - (data.get("adds_used") or 0)
    ir_free = max(0, (data.get("ir_slots") or 0) - (data.get("ir_used") or 0))
    open_spots = max(0, cfg.roster_size - len(me))
    ranks = _season_ranks(me)

    def run(es):
        es = sorted(es, key=lambda e: -e.prio)
        return compare(sim_team(es, days_left, sofar, n, np.random.default_rng(91), slots), opp), _starts(es, days_left, slots)

    def roster(skip=(), cut_at=None, cut=()):
        out = []
        for p in me:
            if any(p is s for s in skip):
                continue
            e = Entry(p, w)
            if any(p is c for c in cut):
                e.until = cut_at
            out.append(e)
        return out

    fas = sorted((p for p in data["fa"] if _rem(p, eff_days) > 0 and eff < len(data["days"])),
                 key=lambda p: -value(p["s"], w) * _rem(p, eff_days))[:8]

    def best_add(base_es):
        """The free agent who raises your chance to win most on top of this roster."""
        best = None
        for fa in fas:
            r, st = run(base_es + [Entry(fa, w, frm=eff)])
            if best is None or r["win"] + 0.02 * r["cats"] > best[1]["win"] + 0.02 * best[1]["cats"]:
                best = (fa, r, st)
        return best

    base, base_starts = run(roster())
    out = []
    for p in hurt:
        my_games = sum(1 for d in days_left if p["games"][d])
        exp_games = round(_rem(p, days_left), 1)
        opts = []

        def opt(kind, title, r, st, text, add=None, warn=None):
            up, down = _moves(r, base)
            opts.append({"kind": kind, "title": title, "win": round(r["win"] * 100),
                         "delta": round((r["win"] - base["win"]) * 100), "cats": round(r["cats"], 2),
                         "starts": round(st - base_starts, 1), "text": text, "warn": warn,
                         "add": add["name"] if add else None, "add_team": add["team"] if add else None,
                         "waiver": bool(add and add.get("waiver")), "up": up, "down": down})

        opt("hold", f"Keep {p['name']} on your bench", base, base_starts,
            f"No move. {p.get('out_note') or ''}".strip())

        can_add = adds_left > 0 and fas
        ir_ok = p["status"] == "Out"  # ESPN only lets Out players onto IR
        if ir_ok and ir_free and can_add:
            b = best_add(roster(skip=[p]))
            if b:
                fa, r, st = b
                opt("ir", f"Move him to IR, add {fa['name']}", r, st,
                    f"Costs one add and nobody leaves your team. Move {p['name']} back from IR when he’s cleared; "
                    f"you’ll need a free bench spot then, so plan to drop a streamer.", fa)
        if open_spots and can_add:
            b = best_add(roster())
            if b:
                fa, r, st = b
                opt("open", f"Use your open spot, add {fa['name']}", r, st, "Costs one add; nobody leaves your team.", fa)

        cuttable = sorted((q for q in me if q is not p and q["status"] not in HURT and not _protected(q, ranks, cfg)),
                          key=lambda q: season_value(q))
        if cuttable and can_add:
            weak = cuttable[0]
            b = best_add(roster(cut=[weak], cut_at=eff))
            if b:
                fa, r, st = b
                opt("cover", f"Keep him, drop {weak['name']} for {fa['name']}", r, st,
                    f"{weak['name']} is your weakest player over the season, so this covers {p['name']}’s missed "
                    f"games without giving up on him.", fa)

        if can_add:
            b = best_add(roster(cut=[p], cut_at=eff))
            if b:
                fa, r, st = b
                gap = season_value(p) - season_value(fa)
                warn = None
                rank = ranks.get(id(p), 99)
                if gap > 0:
                    warn = (f"Permanent. He’s your #{rank} player over the season and {fa['name']} isn’t as good, so "
                            "only do this if he’s out for weeks.")
                opt("drop", f"Drop him for {fa['name']}", r, st,
                    "Frees his spot for good; another manager can pick him up.", fa, warn)

        if not can_add:
            note = (f"You’ve used all {cfg.max_adds} adds this matchup, so your only levers are IR and your lineup."
                    if adds_left <= 0 else "No free agent has a game left in this matchup.")
        else:
            note = None
        if ir_ok and not ir_free and data.get("ir_slots"):
            note = ((note + " ") if note else "") + "Your IR slot is already taken, so moving him there means activating that player first."
        elif not ir_ok and p["status"] == "Doubtful":
            note = ((note + " ") if note else "") + "ESPN only allows IR for players listed Out, so IR isn’t an option yet."
        elif ir_ok and not data.get("ir_slots"):
            note = ((note + " ") if note else "") + "Your league has no IR slot."

        # How much his timeline matters: back for his next game vs out the whole week.
        scen = []
        orig = p["prob"]
        nxt = next((d for d in days_left if p["games"][d]), None)
        if nxt is not None:
            for label, probs in (
                    (f"If he plays his next game ({data['days'][nxt]['label']})",
                     [1.0 if (i >= nxt and p["games"][i]) else x for i, x in enumerate(orig)]),
                    ("If he misses every game this week",
                     [0.0 if i >= ti else x for i, x in enumerate(orig)])):
                p["prob"] = probs
                r, _ = run(roster())
                scen.append({"label": label, "win": round(r["win"] * 100)})
            p["prob"] = orig

        valid = [o for o in opts if o["kind"] != "hold"]
        best = max(valid, key=lambda o: (o["warn"] is None, o["delta"]), default=None)
        if best and best["delta"] >= 2 and best["warn"] is None:
            rec = best["kind"]
        elif best and best["delta"] >= 6:
            rec = best["kind"]
        else:
            rec = "hold"
        for o in opts:
            o["best"] = o["kind"] == rec
        out.append({"name": p["name"], "team": p["team"], "status": p["status"], "ret": p.get("ret"),
                    "games": my_games, "exp_games": exp_games, "note": note, "options": opts, "scenarios": scen,
                    "rank": ranks.get(id(p))})
    return out
