"""Fictional demo matchup, used with --demo to test without an ESPN league."""
import random
from datetime import date, datetime, timedelta, timezone

from .cards import LINE

SK = ["fgm", "fga", "ftm", "fta", "tpm", "reb", "ast", "stl", "blk", "to"]
SCHED = {"A": [1, 0, 1, 0, 1, 0, 1], "B": [0, 1, 0, 1, 0, 1, 0], "C": [1, 1, 0, 1, 0, 1, 0],
         "D": [0, 0, 1, 0, 1, 0, 1], "E": [1, 0, 1, 1, 0, 1, 0], "F": [0, 1, 0, 0, 1, 0, 1]}


ELIG = {"PG": ["PG", "G", "UT"], "SG": ["SG", "G", "UT"], "G": ["PG", "SG", "G", "UT"],
        "SF": ["SF", "F", "UT"], "PF": ["PF", "F", "UT"], "F": ["SF", "PF", "F", "UT"],
        "C": ["C", "UT"], "FC": ["PF", "C", "F", "UT"], "GF": ["SG", "SF", "G", "F", "UT"]}
POS = {"Marcus Vale": "PG", "Dorian Pike": "GF", "Theo Amari": "C", "Jalen Cross": "SG", "Rafi Okoye": "FC",
       "Cole Brennan": "G", "Isaiah Monroe": "C", "Nico Ferreira": "SF", "Andre Wells": "PG", "Malik Haynes": "PF",
       "Grant Sato": "SG", "Kofi Mensah": "FC", "Luca Varga": "PG", "Devin Royce": "GF",
       "Kai Laurent": "PG", "Bram Ostrowski": "SG", "Tariq Bell": "GF", "Owen Achebe": "C", "Ruben Diaz": "PG",
       "Sami Kowal": "PF", "Elijah Ford": "SG", "Victor Lunde": "C", "Jonah Pratt": "SF", "Tyrese Gamble": "G",
       "Felix Mora": "F", "Hugo Lindqvist": "PG", "Aaron Cobb": "C",
       "Zeke Holloway": "PG", "Bastian Kroll": "C", "Miles Okafor": "SG", "Paolo Rinaldi": "SF",
       "Desmond Hart": "FC", "Remy Tolbert": "PG", "Ivo Petrov": "C", "Calvin Brooks": "G",
       "Jordan Pace": "SF", "Marco Quill": "PF", "Eli Stroud": "SG"}


def _p(name, sched, stats, status="Healthy", prob=1.0, ir=False, trend=None):
    pos = POS.get(name, "G")
    return {"name": name, "team": "DEMO", "pos": pos, "elig": ELIG[pos], "status": status, "ir": ir, "trend": trend,
            "games": [bool(g) for g in SCHED[sched]], "prob": [prob] * 7, "sched": sched,
            "s": dict(zip(SK, stats))}


# Tip-off hour in UTC for each demo team: 23 is 7 pm Eastern, 2 is 10 pm Eastern (next UTC day).
TIP = {"A": 0, "B": 0.5, "C": 1, "D": 2, "E": 23.5, "F": 3}


def _tips(sched, day0, today):
    out = []
    for i, g in enumerate(SCHED[sched]):
        if not g:
            out.append(None)
            continue
        base = datetime(day0.year, day0.month, day0.day, tzinfo=timezone.utc) + timedelta(days=i)
        h = TIP[sched]
        base += timedelta(hours=h if h >= 12 else 24 + h)
        out.append(base.isoformat())
    return out


def _card(p, rng, days_back=10):
    """Fictional averages and a game log built around the player's stat line."""
    s = p["s"]
    season = {"GP": 18, "MIN": 22 + s["fga"], "PTS": 2 * s["fgm"] + s["tpm"] + s["ftm"], "REB": s["reb"], "AST": s["ast"],
              "STL": s["stl"], "BLK": s["blk"], "3PM": s["tpm"], "TO": s["to"], "FGM": s["fgm"], "FGA": s["fga"],
              "FTM": s["ftm"], "FTA": s["fta"]}

    def jitter(k, f):
        return {key: (v if key == "GP" else round(v * f * rng.uniform(0.85, 1.15), 1)) for key, v in season.items()} | {"GP": k}

    log = []
    for i in range(days_back):
        g = {k: max(0, round(season.get(k, 0) * rng.uniform(0.4, 1.6))) for k in LINE}
        g["FGM"], g["FTM"] = min(g["FGM"], g["FGA"]), min(g["FTM"], g["FTA"])
        g["PTS"] = 2 * g["FGM"] + g["3PM"] + g["FTM"]
        d = date.today() - timedelta(days=2 * i + 1)
        log.append({"date": d.strftime("%a %b %-d"), "opp": rng.choice(["BOS", "@MIA", "NYK", "@LAL", "DEN", "@PHX"]), **g})
    return {"avgs": {"Season": season, "Last 15": jitter(7, 1.05), "Last 7": jitter(3, rng.choice([0.8, 1.2])),
                     "Last season": jitter(70, 0.95)}, "log": log}


def _injured():
    today = date.today()
    star = {"PTS": 24.1, "REB": 6.0, "AST": 5.2, "STL": 1.5, "BLK": 0.4, "3PM": 1.1, "TO": 2.1,
            "FGM": 8.2, "FGA": 16.4, "FTM": 6.6, "FTA": 7.8, "GP": 62}
    mid = {"PTS": 15.3, "REB": 8.8, "AST": 2.1, "STL": 0.9, "BLK": 1.4, "3PM": 0.6, "TO": 1.4,
           "FGM": 6.0, "FGA": 11.0, "FTM": 2.7, "FTA": 3.6, "GP": 55}
    guard = {"PTS": 17.0, "REB": 3.2, "AST": 6.4, "STL": 1.2, "BLK": 0.2, "3PM": 2.3, "TO": 2.4,
             "FGM": 6.1, "FGA": 13.9, "FTM": 2.5, "FTA": 2.9, "GP": 40}
    from .cards import as_sim_line

    def w(name, team, status, owner, ret, line, src, own, ch, news, watch=False):
        return {"id": hash(name), "name": name, "team": team, "status": status, "owner": owner, "watch": watch,
                "mine": owner == "Your team", "ret": ret, "own": own, "own_change": ch, "line": line, "source": src,
                "s": as_sim_line(line), "games_left": 55, "news": news}
    return [
        w("Silas Brandt", "DEMO", "Out", "Free agent", (today + timedelta(days=40)).isoformat(), star, "last season", 31.0, 0.4,
          [{"published": today.isoformat(), "headline": "Brandt ramps up on-court work",
            "story": "Brandt has started shooting drills but remains without a firm timeline for contact work."}], watch=True),
        w("Tomas Reyes", "DEMO", "Day-to-day", "Free agent", None, guard, "this season", 44.0, 6.2,
          [{"published": today.isoformat(), "headline": "Reyes upgraded to day-to-day", "story": ""}]),
        w("Noah Whitfield", "DEMO", "Out", "On waivers", (today + timedelta(days=9)).isoformat(), mid, "last season", 22.0, 1.0, []),
        w("Devin Royce", "DEMO", "Out", "Your team", (today + timedelta(days=12)).isoformat(),
          {**star, "PTS": 20.0}, "this season", 88.0, -2.0, []),
    ]


def load():
    monday = date.today() - timedelta(days=date.today().weekday())
    days = [{"date": (monday + timedelta(days=i)).isoformat(),
             "label": (monday + timedelta(days=i)).strftime("%a %b %-d")} for i in range(7)]
    zero = [0.0] * 11
    data = _load(days, zero)
    rng = random.Random(7)
    for team in ("me", "opp"):
        for p in data[team]["players"]:
            p["tips"] = _tips(p["sched"], monday, date.today())
    for p in data["fa"]:
        p["tips"] = _tips(p["sched"], monday, date.today())
    for p in data["me"]["players"]:
        p["card"] = _card(p, rng)
    for i, d in enumerate(days):
        tips = [p["tips"][i] for p in data["me"]["players"] + data["opp"]["players"] if p["tips"][i]]
        d["first_tip"] = min(tips) if tips else None
    data["today_index"] = min(date.today().weekday(), 6)
    data["injury_watch"], data["watch_missing"] = _injured(), []
    data["ir_slots"], data["ir_used"] = 1, 1
    data["others"] = _others(data, rng)
    # Next week: a different mix of game days per demo schedule.
    nxt = {"A": [1, 1, 0, 1, 0, 1, 1], "B": [0, 1, 0, 0, 1, 0, 0], "C": [1, 0, 1, 0, 1, 0, 1],
           "D": [0, 1, 1, 0, 0, 1, 0], "E": [1, 0, 0, 1, 0, 0, 1], "F": [0, 0, 1, 1, 1, 1, 0]}
    data["next_days"] = [{"date": (monday + timedelta(days=7 + i)).isoformat(),
                          "label": (monday + timedelta(days=7 + i)).strftime("%a %b %-d")} for i in range(7)]
    names = ["ATL", "BOS", "CHI", "DEN", "GSW", "LAL", "MIA", "NYK", "OKC", "PHX"]
    data["team_sched"] = {t: {"last": bool(SCHED["ABCDEF"[i % 6]][6]),
                              "this": [bool(g) for g in SCHED["ABCDEF"[i % 6]][data["today_index"]:]], "next": [bool(g) for g in nxt["ABCDEF"[(i * 5) % 6]]]}
                          for i, t in enumerate(names)}
    for p in data["me"]["players"] + data["opp"]["players"] + data["fa"]:
        p["next_games"] = [bool(g) for g in nxt[p["sched"]]]
        p["next_prob"] = [0.0 if p["status"] == "Out" else 1.0] * 7
    for k, t in enumerate(data["others"]):
        for i, p in enumerate(t["players"]):
            p["next_games"] = [bool(g) for g in nxt["ABCDEF"[(i + k + 1) % 6]]]
            p["next_prob"] = [0.0 if p["status"] == "Out" else 1.0] * 7
    data["next_opp"] = {"name": data["others"][0]["name"], "players": data["others"][0]["players"]}
    return data


def _others(data, rng):
    """Fictional rest-of-league teams, built by reshuffling and rescaling the opponent's players."""
    out = []
    for k, (name, f) in enumerate((("Dunk Dynasty", 1.06), ("Splash Bros Inc", 0.97), ("Board Men", 1.02),
                                    ("Fast Break Fund", 0.92), ("Glass Cleaners", 1.0))):
        players = []
        for i, p in enumerate(data["opp"]["players"]):
            q = dict(p)
            q["name"] = f"{name.split()[0]} player {i + 1}"
            q["s"] = {key: round(v * f * rng.uniform(0.85, 1.15), 2) for key, v in p["s"].items()}
            sched = "ABCDEF"[(i + k) % 6]
            q["games"] = [bool(g) for g in SCHED[sched]]
            players.append(q)
        out.append({"name": name, "sofar": [0.0] * 11, "players": players})
    return out


def _load(days, zero):
    return {
        "league": {"name": "Demo league", "week": 1},
        "days": days, "today_index": 0, "lineup_slots": ["PG", "SG", "SF", "PF", "C", "G", "F", "UT", "UT", "UT"], "adds_used": 0, "sofar_note": None,
        "me": {"name": "Your team", "sofar": zero, "players": [
            _p("Marcus Vale", "A", [8.5, 18.2, 5.1, 5.8, 2.6, 4.4, 8.9, 1.3, 0.3, 3.1]),
            _p("Dorian Pike", "B", [7.9, 16.5, 4.2, 5.0, 2.1, 6.8, 3.9, 1.1, 0.6, 2.2]),
            _p("Theo Amari", "C", [7.2, 12.6, 3.0, 4.8, 0.2, 11.4, 2.5, 0.8, 2.1, 1.9]),
            _p("Jalen Cross", "D", [6.1, 14.0, 2.8, 3.3, 3.1, 3.6, 3.2, 1.0, 0.3, 1.5]),
            _p("Rafi Okoye", "E", [5.8, 11.1, 2.4, 3.5, 0.9, 8.2, 2.1, 0.7, 1.2, 1.3]),
            _p("Cole Brennan", "F", [5.0, 11.8, 1.9, 2.2, 2.4, 3.0, 5.6, 1.2, 0.2, 1.8]),
            _p("Isaiah Monroe", "A", [4.6, 8.0, 1.6, 2.8, 0.0, 9.1, 1.4, 0.6, 1.8, 1.2]),
            _p("Nico Ferreira", "C", [4.4, 10.0, 1.5, 1.9, 2.0, 4.3, 1.8, 0.9, 0.4, 1.0]),
            _p("Andre Wells", "B", [4.1, 9.8, 2.2, 2.6, 1.5, 2.7, 6.1, 1.0, 0.2, 2.0]),
            _p("Malik Haynes", "E", [3.9, 8.3, 1.4, 2.0, 1.2, 5.6, 1.5, 0.8, 0.9, 0.9]),
            _p("Grant Sato", "D", [3.6, 8.4, 1.1, 1.3, 2.2, 2.4, 1.9, 0.7, 0.2, 0.8]),
            _p("Kofi Mensah", "F", [3.4, 7.2, 1.0, 1.6, 0.8, 5.0, 1.3, 0.9, 0.7, 0.9], "Day-to-day", 0.6),
            _p("Luca Varga", "A", [3.0, 7.1, 1.2, 1.4, 1.4, 2.1, 3.0, 0.8, 0.1, 1.1]),
            _p("Devin Royce", "B", [8.0, 16.9, 4.5, 5.4, 2.3, 6.0, 3.4, 1.2, 0.5, 2.4], "Out", 0.0, ir=True),
        ]},
        "opp": {"name": "Opponent", "sofar": zero, "players": [
            _p("Kai Laurent", "C", [9.0, 19.5, 6.0, 6.8, 2.8, 5.1, 9.8, 1.6, 0.4, 3.6]),
            _p("Bram Ostrowski", "A", [7.4, 16.0, 3.9, 4.4, 3.0, 4.0, 4.3, 1.4, 0.3, 2.3]),
            _p("Tariq Bell", "E", [6.8, 14.2, 3.1, 3.9, 1.9, 6.1, 3.0, 1.5, 0.7, 1.9]),
            _p("Owen Achebe", "B", [6.5, 11.0, 2.6, 4.4, 0.4, 10.2, 2.2, 0.9, 1.9, 1.7]),
            _p("Ruben Diaz", "D", [5.5, 12.6, 2.8, 3.2, 2.0, 3.3, 7.0, 1.5, 0.2, 2.4]),
            _p("Sami Kowal", "F", [5.2, 10.4, 2.0, 2.7, 1.3, 6.9, 2.0, 0.8, 0.9, 1.2]),
            _p("Elijah Ford", "C", [4.8, 11.0, 2.2, 2.6, 2.3, 3.1, 4.1, 1.3, 0.3, 1.4]),
            _p("Victor Lunde", "D", [4.0, 7.4, 1.3, 2.4, 0.1, 7.8, 1.2, 0.5, 1.5, 1.0]),
            _p("Jonah Pratt", "A", [4.2, 9.6, 1.4, 1.7, 1.8, 4.0, 2.0, 1.1, 0.5, 0.9]),
            _p("Tyrese Gamble", "E", [3.8, 9.0, 1.8, 2.1, 1.9, 2.6, 2.4, 1.0, 0.2, 1.0]),
            _p("Felix Mora", "B", [3.5, 7.6, 1.2, 1.6, 1.0, 4.6, 1.6, 0.9, 0.6, 0.8]),
            _p("Hugo Lindqvist", "F", [3.2, 7.8, 1.4, 1.7, 1.3, 2.2, 4.4, 1.1, 0.1, 1.3]),
            _p("Aaron Cobb", "A", [3.1, 5.6, 0.9, 1.6, 0.0, 6.3, 0.9, 0.4, 1.2, 0.7]),
        ]},
        "fa": [
            _p("Zeke Holloway", "E", [4.5, 10.5, 2.0, 2.4, 1.6, 3.0, 5.9, 1.4, 0.2, 1.9], trend="Minutes up: 31.2 last 7 days vs 24.0 season"),
            _p("Bastian Kroll", "C", [4.0, 7.0, 1.5, 2.5, 0.2, 8.4, 1.3, 0.6, 1.6, 1.1]),
            _p("Miles Okafor", "A", [4.2, 10.2, 1.6, 1.9, 2.6, 2.9, 2.1, 1.3, 0.3, 1.0]),
            _p("Paolo Rinaldi", "B", [3.6, 8.0, 1.4, 1.8, 1.4, 4.6, 2.2, 1.6, 0.6, 1.0]),
            _p("Desmond Hart", "F", [3.8, 7.5, 1.9, 2.8, 0.6, 6.6, 1.6, 0.7, 1.0, 1.0]),
            _p("Remy Tolbert", "D", [3.3, 8.2, 1.3, 1.5, 1.9, 2.4, 4.8, 1.2, 0.2, 1.4]),
            _p("Ivo Petrov", "E", [3.5, 6.1, 1.2, 2.2, 0.0, 7.4, 1.0, 0.5, 1.4, 0.9]),
            _p("Calvin Brooks", "C", [3.9, 9.3, 2.1, 2.4, 2.1, 2.7, 2.8, 0.9, 0.2, 1.1]),
            _p("Jordan Pace", "F", [4.6, 9.9, 2.3, 2.9, 1.8, 5.2, 2.6, 1.1, 0.6, 1.3]),
            _p("Marco Quill", "F", [4.1, 8.6, 1.7, 2.1, 1.5, 6.4, 1.9, 0.8, 0.9, 1.0]),
            _p("Eli Stroud", "B", [3.7, 8.1, 1.5, 1.8, 2.0, 3.1, 3.8, 1.2, 0.3, 1.3]),
        ],
    }
