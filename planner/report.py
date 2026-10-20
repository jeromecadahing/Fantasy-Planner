"""Render the plan as a static web page and a short text summary."""
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from .sim import CATS, fmt_cat

CSS = """
:root{--bg:#EEF1F5;--surface:#FFF;--field:#F6F8FA;--ink:#16202D;--muted:#5A6777;--rule:#D3DAE3;
--you:#2445C4;--you-soft:#DDE4FB;--on-you:#FFF;--opp:#C2410C;--opp-soft:#FBE3D6;--on-opp:#FFF;
--good:#1D7A4C;--bad:#B4332A;--warn:#8F5E00;color-scheme:light;box-sizing:border-box;
padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
@media (prefers-color-scheme:dark){:root{--bg:#0F151E;--surface:#17202C;--field:#111923;--ink:#E6EBF2;
--muted:#94A1B2;--rule:#2A3646;--you:#8AA2FF;--you-soft:#1E2A52;--on-you:#0B1230;--opp:#FF8E55;
--opp-soft:#47250F;--on-opp:#2A1205;--good:#5FD49A;--bad:#FF7F75;--warn:#E7B04E;color-scheme:dark}}
*,*::before,*::after{box-sizing:inherit}
body{margin:0;background:var(--bg);color:var(--ink);font:400 16px/1.5 Barlow,"Segoe UI",system-ui,sans-serif}
.wrap{max-width:1120px;margin:0 auto;padding:20px 16px 56px}
.cd{font-family:"Barlow Condensed","Arial Narrow",Barlow,sans-serif}
h1{font:700 2.1rem/1 "Barlow Condensed","Arial Narrow",sans-serif;margin:0}
h2{font:700 1.45rem/1.1 "Barlow Condensed","Arial Narrow",sans-serif;margin:0 0 6px}
.sub,.hint,.empty{color:var(--muted)} .sub{margin:4px 0 16px} .hint{margin:0 0 12px;font-size:.92rem}
.panel,.board{background:var(--surface);border:1px solid var(--rule);border-radius:12px;padding:16px}
.board{border-radius:14px;padding:18px;margin-bottom:18px}
.score{display:grid;grid-template-columns:1fr auto 1fr;align-items:end;gap:8px}
.side{display:flex;flex-direction:column;min-width:0}.you{color:var(--you)}.opp{color:var(--opp);align-items:flex-end;text-align:right}
.team{font:600 1.15rem/1.1 "Barlow Condensed","Arial Narrow",sans-serif;color:var(--ink)}
.big{font:700 clamp(3.6rem,13vw,6.8rem)/.88 "Barlow Condensed","Arial Narrow",sans-serif;font-variant-numeric:tabular-nums}
.mid{color:var(--muted);text-align:center;padding-bottom:.9rem;font-size:.9rem}
.verdict{margin:12px 0 14px;font-size:1.1rem;font-weight:500}
.tug{display:grid;gap:5px}.row{display:grid;grid-template-columns:4rem 1fr 3.2rem 1fr 4rem;align-items:center;gap:8px}
.v{font:600 1.05rem/1 "Barlow Condensed","Arial Narrow",sans-serif;font-variant-numeric:tabular-nums}
.v.l{text-align:right;color:var(--you)}.v.r{color:var(--opp)}
.cat{text-align:center;font:700 1.05rem/1 "Barlow Condensed","Arial Narrow",sans-serif}
.bar{height:24px;background:var(--field);border-radius:4px;position:relative;overflow:hidden}
.bar i{position:absolute;top:0;bottom:0}.bar.y i{right:0;background:var(--you)}.bar.o i{left:0;background:var(--opp)}
.bar b{position:absolute;top:50%;transform:translateY(-50%);font:600 .85rem/1 "Barlow Condensed","Arial Narrow",sans-serif}
.plan{display:grid;grid-template-columns:1.05fr 1fr;gap:18px;align-items:start;margin-bottom:18px}.stack{display:grid;gap:18px}
.picks{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.pick{border:1px solid var(--rule);border-radius:10px;padding:10px 12px}.pick.top{border-color:var(--you);box-shadow:inset 3px 0 0 var(--you)}
.ph{display:flex;justify-content:space-between;gap:10px;align-items:baseline}
.delta{font:700 1.15rem/1 "Barlow Condensed","Arial Narrow",sans-serif;white-space:nowrap}.pos{color:var(--good)}.neg{color:var(--bad)}.flat{color:var(--muted)}
.pick p{margin:2px 0 0;font-size:.92rem;color:var(--muted)}
.moves{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.mv{font:600 .85rem/1 "Barlow Condensed","Arial Narrow",sans-serif;padding:4px 7px;border-radius:5px}
.up{background:var(--you-soft)}.down{background:var(--opp-soft)}
.notes{margin:0;padding-left:1.1rem;display:grid;gap:8px}
.day{border-top:1px solid var(--rule);padding:10px 0 8px}.day:first-of-type{border-top:0;padding-top:0}
.dh{display:flex;justify-content:space-between;gap:10px;margin-bottom:5px}.dn{font:700 1.15rem/1 "Barlow Condensed","Arial Narrow",sans-serif}
.dc{font-size:.85rem;color:var(--muted)}.warnc{color:var(--warn);font-weight:600}
.chip{display:inline-block;padding:2px 9px;border-radius:999px;background:var(--you-soft);margin:2px 3px 2px 0;font-size:.86rem}
.chip.bench{background:transparent;border:1px dashed var(--rule);color:var(--muted);text-decoration:line-through}
.chip small{color:var(--warn);font-weight:600;margin-left:3px}
table{border-collapse:collapse;width:100%;font-size:.92rem}td{padding:6px 4px;border-top:1px solid var(--rule);vertical-align:top}
td:first-child{color:var(--muted);white-space:nowrap}
.foot{color:var(--muted);font-size:.86rem;margin-top:18px;max-width:70ch}
@media (max-width:820px){.plan{grid-template-columns:1fr}}
@media (max-width:520px){.row{grid-template-columns:3.1rem 1fr 2.6rem 1fr 3.1rem;gap:5px}}
"""

SHORT = {"Probable": "Prob", "Day-to-day": "DTD", "Questionable": "GTD", "Doubtful": "Doubt"}


def _pct(x):
    return f"{round(x * 100)}%"


def _tug(res):
    rows = []
    for c, (label, _, _) in enumerate(CATS):
        p = res["catP"][c]
        y, o = p * 100, (1 - p) * 100
        yl = (f'<b style="right:6px;color:var(--on-you)">{_pct(p)}</b>' if y >= 22
              else f'<b style="right:calc({y:.1f}% + 6px);color:var(--you)">{_pct(p)}</b>')
        ol = (f'<b style="left:6px;color:var(--on-opp)">{_pct(1 - p)}</b>' if o >= 22
              else f'<b style="left:calc({o:.1f}% + 6px);color:var(--opp)">{_pct(1 - p)}</b>')
        rows.append(f'<div class="row"><span class="v l">{fmt_cat(c, res["mean"])}</span>'
                    f'<div class="bar y"><i style="width:{y:.1f}%"></i>{yl}</div><span class="cat">{label}</span>'
                    f'<div class="bar o"><i style="width:{o:.1f}%"></i>{ol}</div>'
                    f'<span class="v r">{fmt_cat(c, res["opp_mean"])}</span></div>')
    return "".join(rows)


def _picks(plan):
    if not plan["picks"]:
        return f'<p class="empty">{escape(plan["pick_note"] or "No pickups to suggest.")}</p>'
    h = f'<p class="hint">{escape(plan["pick_note"])}</p>' if plan["pick_note"] else ""
    items = []
    for i, x in enumerate(plan["picks"]):
        d = x["win_delta"]
        cls = "pos" if d > 0 else "neg" if d < 0 else "flat"
        drop = (f'Drop {escape(x["drop"])} ({x["drop_games"]} game{"s" if x["drop_games"] != 1 else ""} left).'
                if x["drop"] else "Use your open roster spot.")
        extra = f' {escape(x["status"])}.' if x["status"] != "Healthy" else ""
        trend = f'<p>{escape(x["trend"])}</p>' if x.get("trend") else ""
        moves = "".join(f'<span class="mv up">{l} +{v}%</span>' for l, v in x["up"]) + \
            "".join(f'<span class="mv down">{l} {v}%</span>' for l, v in x["down"])
        items.append(f'<li class="pick{" top" if i == 0 and d > 0 else ""}"><div class="ph"><strong>Add {escape(x["add"])}'
                     f' <span class="dc">{escape(x["add_team"])}</span></strong><span class="delta {cls}">{d:+d}%</span></div>'
                     f'<p>{drop} {x["games"]} game{"s" if x["games"] != 1 else ""} left for him.{extra} '
                     f'Expected categories {x["cats_delta"]:+.2f}.</p>{trend}'
                     f'{f"<div class=moves>{moves}</div>" if moves else ""}</li>')
    return (h + '<ol class="picks">' + "".join(items) + "</ol>"
            '<p class="hint" style="margin-top:10px">The big number is the change in your chance to win the week. '
            "The chips show how each category’s win chance moves.</p>")


def _days(plan):
    if not plan["lineup"]:
        return '<p class="empty">No days left in this matchup.</p>'
    out = []
    for d in plan["lineup"]:
        cnt = f'You {len(d["start"])}, them {d["opp_games"]}'
        if d["bench"]:
            cnt += f', <span class="warnc">{len(d["bench"])} benched</span>'
        elif d["open"] and d["start"]:
            cnt += f', {d["open"]} open'
        chips = "".join(f'<span class="chip">{escape(n)}{f"<small>{SHORT.get(s, s)}</small>" if pr < 1 else ""}</span>'
                        for n, pr, s in d["start"])
        chips += "".join(f'<span class="chip bench">{escape(n)}</span>' for n in d["bench"])
        out.append(f'<div class="day"><div class="dh"><span class="dn">{escape(d["day"])}</span>'
                   f'<span class="dc">{cnt}</span></div><div>{chips or "<span class=empty>No games</span>"}</div></div>')
    return "".join(out)


def render(data, plan):
    res = plan["result"]
    me, opp = data["me"]["name"], data["opp"]["name"]
    win = round(res["win"] * 100)
    verdict = f"{win}% chance you win the week." + ("" if win >= 50 else f" {escape(opp)} is the favorite right now.")
    now = datetime.now(ZoneInfo("America/New_York")).strftime("%a %b %-d, %-I:%M %p ET")
    trends = "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td><td>{escape(c)}</td></tr>" for a, b, c in plan["trends"])
    notes = "".join(f"<li>{escape(n)}</li>" for n in plan["notes"])
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Matchup plan: {escape(me)} vs {escape(opp)}</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🏀</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Barlow+Condensed:wght@500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">
<h1>Matchup plan</h1>
<p class="sub">{escape(data["league"]["name"])}, week {data["league"]["week"]}. Updated {now}.</p>
<section class="board"><div class="score">
<div class="side you"><span class="team">{escape(me)}</span><span class="big">{res["cats"]:.1f}</span></div>
<div class="mid">categories<br>won</div>
<div class="side opp"><span class="team">{escape(opp)}</span><span class="big">{9 - res["cats"]:.1f}</span></div></div>
<p class="verdict">{verdict}</p><div class="tug">{_tug(res)}</div></section>
<div class="plan"><div class="stack">
<section class="panel"><h2>Best pickups for this matchup</h2>{_picks(plan)}</section>
<section class="panel"><h2>Game plan</h2><ul class="notes">{notes}</ul></section></div>
<section class="panel"><h2>Daily lineup</h2><p class="hint">Who to start in your active spots each day,
ordered by how much they help the categories still up for grabs.</p>{_days(plan)}</section></div>
{f'<section class="panel"><h2>Injuries and minutes trends</h2><table>{trends}</table></section>' if trends else ""}
<p class="foot">Each remaining game is simulated thousands of times from recent per-game averages, with
injury status setting each player’s chance to play. Positions are ignored, so any healthy player can fill an
active spot. Always check ESPN for late scratches before games lock.</p>
</div></body></html>"""


def summary(data, plan):
    res = plan["result"]
    lines = [f"{data['me']['name']} vs {data['opp']['name']}: projected {res['cats']:.1f} to {9 - res['cats']:.1f} "
             f"categories, {round(res['win'] * 100)}% to win."]
    swing = [CATS[i][0] for i in range(9) if 0.2 <= res["catP"][i] < 0.8]
    if swing:
        lines.append("Swing: " + ", ".join(swing))
    if plan["picks"] and plan["picks"][0]["win_delta"] > 0:
        x = plan["picks"][0]
        drop = f", drop {x['drop']}" if x["drop"] else ""
        lines.append(f"Top add: {x['add']}{drop} ({x['win_delta']:+d}% win chance)")
    elif plan["pick_note"]:
        lines.append(plan["pick_note"])
    return "\n".join(lines)
