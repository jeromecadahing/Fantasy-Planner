"""Fictional demo matchup, used with --demo to test without an ESPN league."""
from datetime import date, timedelta

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
       "Desmond Hart": "FC", "Remy Tolbert": "PG", "Ivo Petrov": "C", "Calvin Brooks": "G"}


def _p(name, sched, stats, status="Healthy", prob=1.0, ir=False, trend=None):
    pos = POS.get(name, "G")
    return {"name": name, "team": "DEMO", "pos": pos, "elig": ELIG[pos], "status": status, "ir": ir, "trend": trend,
            "games": [bool(g) for g in SCHED[sched]], "prob": [prob] * 7,
            "s": dict(zip(SK, stats))}


def load():
    monday = date.today() - timedelta(days=date.today().weekday())
    days = [{"date": (monday + timedelta(days=i)).isoformat(),
             "label": (monday + timedelta(days=i)).strftime("%a %b %-d")} for i in range(7)]
    zero = [0.0] * 11
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
        ],
    }
