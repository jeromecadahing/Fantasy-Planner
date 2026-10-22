"""Render the plan as a static web page and a short text summary."""
from datetime import datetime
import json
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
.lift{margin:0 0 12px;font-size:1rem}.lift .cd{font-size:1.5rem;font-weight:700;color:var(--muted)}
.lift .strong{color:var(--good)}.arrow{color:var(--muted)}
.steps{list-style:none;margin:0;padding:0;display:grid;gap:0}
.step{border-left:3px solid var(--rule);padding:4px 0 12px 14px;position:relative}
.step::before{content:"";position:absolute;left:-7px;top:8px;width:11px;height:11px;border-radius:50%;background:var(--surface);border:2px solid var(--you)}
.sh{display:flex;align-items:center;gap:8px}.act{margin:2px 0 0}.step p{margin:2px 0 0;font-size:.93rem}.step p:not(.act){color:var(--muted)}
.tag{font:600 .75rem/1 Barlow,sans-serif;text-transform:uppercase;letter-spacing:.04em;padding:3px 6px;border-radius:4px;border:1px solid var(--rule);color:var(--muted)}
.alts{margin:6px 0 0;font-size:.9rem}.alts summary{cursor:pointer;color:var(--muted)}
.alts ul{margin:4px 0 0;padding-left:18px}.alts li{margin:2px 0}
.tag.now{background:var(--you);border-color:var(--you);color:var(--on-you)}
.foot{color:var(--muted);font-size:.86rem;margin-top:18px;max-width:70ch}
.wi{display:grid;grid-template-columns:minmax(9rem,.7fr) 1.3fr 1fr;gap:10px;margin-bottom:14px}
.wi label{display:grid;gap:4px;font-size:.88rem;color:var(--muted)}
.wi select{font:500 1rem/1.2 Barlow,"Segoe UI",system-ui,sans-serif;color:var(--ink);background:var(--field);
border:1px solid var(--rule);border-radius:8px;padding:9px 10px;width:100%;min-width:0}
.wi select:focus-visible{outline:2px solid var(--you);outline-offset:1px}
.wiout .lift{margin-bottom:6px}.wiout p{margin:0 0 8px;font-size:.93rem}
.cg{display:grid;grid-template-columns:repeat(9,1fr);gap:5px;margin:10px 0 4px}
.cc{border:1px solid var(--rule);border-radius:7px;padding:6px 2px;text-align:center;background:var(--field)}
.cc b{display:block;font:700 .95rem/1 "Barlow Condensed","Arial Narrow",sans-serif}
.cc span{display:block;font:600 1.05rem/1.2 "Barlow Condensed","Arial Narrow",sans-serif;font-variant-numeric:tabular-nums}
.cc small{display:block;font-size:.78rem;font-variant-numeric:tabular-nums}
.cc.pos{border-color:var(--good)}.cc.neg{border-color:var(--bad)}
.scn{border:1px solid var(--you);box-shadow:inset 3px 0 0 var(--you);border-radius:10px;padding:12px 14px;margin-bottom:16px}
.scn h3{margin:0 0 4px;font:700 1.15rem/1.1 "Barlow Condensed","Arial Narrow",sans-serif}
.scn p{margin:4px 0 0;font-size:.93rem}.scn .err{color:var(--bad)}
code{font-size:.88em;background:var(--field);padding:1px 5px;border-radius:4px}
@media (max-width:620px){.wi{grid-template-columns:1fr}.cg{grid-template-columns:repeat(5,1fr)}}
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


def _days_list(days):
    return ", ".join(days) if days else "no games"


def _alts(m):
    if not m.get("alts"):
        return ""
    rows = ""
    for a in m["alts"]:
        drop = f', drop {escape(a["drop"])}' if a["drop"] else ", use your open spot"
        perm = "" if not a["drop"] or a["drop_is_streamer"] else " (permanent cut)"
        gap = "about the same chance" if a["behind"] <= 0 else f'{a["behind"]} point{"s" if a["behind"] != 1 else ""} lower'
        rows += f'<li>Add {escape(a["add"])} <span class="dc">{escape(a["add_team"])}</span>{drop}{perm}: {gap}</li>'
    return f'<details class="alts"><summary>Other options this day</summary><ul>{rows}</ul></details>'


def _stream(plan):
    st = plan.get("stream") or {}
    if not st.get("moves"):
        return f'<p class="empty">{escape(st.get("note") or "No streaming moves this week.")}</p>'
    b, a = round(st["before"] * 100), round(st["after"] * 100)
    h = (f'<p class="lift"><span class="cd">{b}%</span> <span class="arrow">→</span> '
         f'<span class="cd strong">{a}%</span> chance to win the week if you make these moves. '
         f'Uses {st["adds_planned"]} add{"s" if st["adds_planned"] != 1 else ""}, leaving {st["adds_left_after"]}.</p><ol class="steps">')
    for m in st["moves"]:
        when = '<span class="tag now">Do today</span>' if m["today"] else '<span class="tag">Planned</span>'
        status = f' ({escape(m["add_status"])})' if m["add_status"] != "Healthy" else ""
        if m["drop"]:
            why = (f' after his {", ".join(m["drop_days_used"])} game{"s" if len(m["drop_days_used"]) != 1 else ""}'
                   if m["drop_days_used"] else "")
            drop = f'Drop {escape(m["drop"])}{why}.' + ("" if m["drop_is_streamer"] else " This one is a permanent cut.")
        else:
            drop = "Use your open roster spot."
        trend = f'<p>{escape(m["trend"])}</p>' if m.get("trend") else ""
        h += (f'<li class="step"><div class="sh"><span class="dn">{escape(m["day"])}</span>{when}</div>'
              f'<p class="act"><strong>Add {escape(m["add"])}</strong> <span class="dc">{escape(m["add_team"])}{status}</span></p>'
              f'<p>{drop} He plays {_days_list(m["add_days"])} for you'
              + (f', starting {escape(m["plays_from"])}' if m.get("plays_from") else "") + f'.</p>{trend}{_alts(m)}</li>')
    h += ('</ol><p class="hint" style="margin-top:10px">The plan is rebuilt on every run, so later steps can change '
          "as injuries and box scores come in. Make today’s move; treat the rest as the current best path.</p>")
    return h


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


def _signed(v, suffix=""):
    return (f"+{v}" if v > 0 else f"−{-v}" if v < 0 else "±0") + suffix


def _cat_grid(before, after):
    cells = ""
    for c, (label, _, _) in enumerate(CATS):
        b, a = round(before[c] * 100), round(after[c] * 100)
        d = a - b
        cls = " pos" if d >= 3 else " neg" if d <= -3 else ""
        tone = "pos" if d > 0 else "neg" if d < 0 else "flat"
        cells += f'<div class="cc{cls}"><b>{label}</b><span>{a}%</span><small class="{tone}">{_signed(d)}</small></div>'
    return f'<div class="cg">{cells}</div>'


def _scenario(sc):
    if not sc:
        return ""
    h = f'<div class="scn"><h3>Your scenario</h3><p class="dc">You asked: <code>{escape(sc["text"])}</code></p>'
    if not sc.get("ok"):
        h += "".join(f'<p class="err">{escape(e)}</p>' for e in sc["errors"])
        return h + "</div>"
    b, a = round(sc["before"]["win"] * 100), round(sc["after"]["win"] * 100)
    d = a - b
    cls = "pos" if d > 0 else "neg" if d < 0 else "flat"
    adds = ", ".join(f'{escape(x["name"])} ({escape(x["team"])}, {escape(x["owner"])}, {x["games"]} game{"s" if x["games"] != 1 else ""})'
                     for x in sc["adds"]) or "nobody"
    drops = ", ".join(f'{escape(x["name"])} ({x["games"]} game{"s" if x["games"] != 1 else ""} given up)' for x in sc["drops"])
    sd = sc["starts_delta"]
    h += (f'<p class="lift" style="margin-top:8px"><span class="cd">{b}%</span> <span class="arrow">→</span> '
          f'<span class="cd {cls}">{a}%</span> chance to win the week <span class="delta {cls}">{_signed(d, "%")}</span></p>'
          f'<p>Add {adds}{"; drop " + drops if drops else ""}, from {escape(sc["day"])}. '
          f'Expected categories {sc["before"]["cats"]:.1f} → {sc["after"]["cats"]:.1f}; '
          f'{"about the same number of" if abs(sd) < 0.5 else f"{sd:+.1f}"} starter games.</p>'
          + "".join(f'<p class="dc">{escape(n)}</p>' for n in sc["notes"])
          + _cat_grid(sc["before"]["catP"], sc["after"]["catP"]) + "</div>")
    return h


WI_JS = r"""(function(){
var D=JSON.parse(document.getElementById('wi-data').textContent);
var T=document.getElementById('wi-day'),A=document.getElementById('wi-add'),R=document.getElementById('wi-drop'),O=document.getElementById('wi-out');
function opt(sel,t,v){var o=document.createElement('option');o.value=v;o.textContent=t;sel.appendChild(o);}
function gm(k){return k+' game'+(k==1?'':'s');}
D.days.forEach(function(d,i){opt(T,(d.today?'Today, ':'')+d.label,i);});
function fill(){
 var d=D.days[+T.value],ka=A.value,kr=R.value;A.innerHTML='';R.innerHTML='';
 D.adds.forEach(function(p,i){opt(A,p.name+' ('+p.team+', '+(d.add_games[i]?gm(d.add_games[i]):'no games left')+(p.status!=='Healthy'?', '+p.status:'')+')',i);});
 D.drops.forEach(function(p,i){opt(R,p.open?p.name:p.name+' ('+gm(d.drop_games[i])+' left)',i);});
 if(ka!=='')A.value=ka; if(kr!=='')R.value=kr;
}
function sg(v,s){return (v>0?'+':v<0?'\u2212':'\u00b1')+Math.abs(v)+(s||'');}
function tone(v){return v>0?'pos':v<0?'neg':'flat';}
function show(){
 var d=D.days[+T.value],a=+A.value,r=+R.value,p=D.adds[a],dp=D.drops[r],row=d.rows[a];
 if(!row){O.innerHTML='<p class="empty">'+p.name+' has no games left from '+d.label+', so adding him then wouldn\u2019t change anything. Pick an earlier day.</p>';return;}
 var x=row[r],b=Math.round(D.base.win*100),aw=Math.max(0,Math.min(100,b+Math.round(x[0]/10))),dw=aw-b;
 var cats=(D.base.cats+x[1]/100).toFixed(1),st=x[3]/10,cells='';
 D.cats.forEach(function(c,i){var bb=Math.round(D.base.catP[i]*100),aa=Math.max(0,Math.min(100,bb+x[2][i])),dd=aa-bb;
  cells+='<div class="cc'+(dd>=3?' pos':dd<=-3?' neg':'')+'"><b>'+c+'</b><span>'+aa+'%</span><small class="'+tone(dd)+'">'+sg(dd)+'</small></div>';});
 var g=d.drop_games[r],who=dp.open?'using your open roster spot':'dropping '+dp.name+(g?' (he gives up '+gm(g)+')':' (no games left to give up)');
 O.innerHTML='<p class="lift"><span class="cd">'+b+'%</span> <span class="arrow">\u2192</span> <span class="cd '+tone(dw)+'">'+aw+'%</span> chance to win the week <span class="delta '+tone(dw)+'">'+sg(dw,'%')+'</span></p>'
  +'<p>Adding '+p.name+' to play from '+d.label+' ('+gm(d.add_games[a])+') and '+who+'. '
  +(d.act?'Make the move in ESPN on '+d.act+'. ':'')+'Expected categories '+D.base.cats.toFixed(1)+' \u2192 '+cats+'; '
  +(Math.abs(st)<0.5?'about the same number of':(st>0?'+':'')+st.toFixed(1))+' starter games.</p>'
  +(p.trend?'<p class="dc">'+p.trend+'</p>':'')+'<div class="cg">'+cells+'</div>';
}
T.addEventListener('change',function(){fill();show();});A.addEventListener('change',show);R.addEventListener('change',show);fill();show();
})();"""


def _whatif(plan):
    g = plan.get("whatif") or {}
    sc = _scenario(plan.get("scenario"))
    help_ = ('<p class="hint" style="margin-top:12px">Want someone who isn’t listed, like a trade target or a player on '
             'your opponent’s team? In GitHub go to <strong>Actions → Daily matchup plan → Run workflow</strong> and '
             'type a scenario such as <code>add: Jalen Brunson; drop: Grant Sato</code>. Add <code>day: Thu</code> to '
             'start it later in the week. Separate several names with commas.</p>')
    if not g.get("adds"):
        return sc + f'<p class="empty">{escape(g.get("note") or "No free agents to test.")}</p>' + help_
    data = dict(g)
    res = plan["result"]
    data["base"] = {"win": res["win"], "cats": res["cats"], "catP": res["catP"]}
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    return (sc + '<p class="hint">Pick a day, a free agent and who you’d drop to see how the rest of this matchup changes. '
            'Every combination was simulated when the page was built, and compares against making no moves.</p>'
            '<div class="wi"><label>Starting<select id="wi-day"></select></label><label>Add<select id="wi-add"></select></label>'
            '<label>Drop<select id="wi-drop"></select></label></div><div class="wiout" id="wi-out" aria-live="polite"></div>'
            f'<script type="application/json" id="wi-data">{blob}</script><script>{WI_JS}</script>' + help_)


def render(data, plan):
    res = plan["result"]
    me, opp = data["me"]["name"], data["opp"]["name"]
    win = round(res["win"] * 100)
    verdict = f"{win}% chance you win the week." + ("" if win >= 50 else f" {escape(opp)} is the favorite right now.")
    utc = datetime.now(ZoneInfo("UTC"))
    et, uk = utc.astimezone(ZoneInfo("America/New_York")), utc.astimezone(ZoneInfo("Europe/London"))
    now = f'{et.strftime("%a %b %-d, %-I:%M %p")} ET ({uk.strftime("%-I:%M %p")} UK)'
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
<section class="panel"><h2>Streaming plan for the week</h2>{_stream(plan)}</section>
<section class="panel"><h2>Other pickup options right now</h2>{_picks(plan)}</section>
<section class="panel"><h2>Game plan</h2><ul class="notes">{notes}</ul></section></div>
<section class="panel"><h2>Daily lineup</h2><p class="hint">Who to start in your active spots each day with the
streaming plan in place, ordered by how much they help the categories still up for grabs.</p>{_days(plan)}</section></div>
<section class="panel" style="margin-bottom:18px"><h2>What if…</h2>{_whatif(plan)}</section>
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
    sc = plan.get("scenario")
    if sc and sc.get("ok"):
        lines.append(f"What-if ({sc['text']}): {round(sc['before']['win'] * 100)}% -> {round(sc['after']['win'] * 100)}% to win")
    elif sc:
        lines.append("What-if couldn't run: " + " ".join(sc["errors"]))
    st = plan.get("stream") or {}
    if st.get("moves"):
        lines.append(f"Streaming plan: {round(st['before'] * 100)}% -> {round(st['after'] * 100)}% to win")
        for m in st["moves"]:
            drop = f", drop {m['drop']}" if m["drop"] else ""
            lines.append(f"{'TODAY ' if m['today'] else ''}{m['day']}: add {m['add']}{drop}")
        return "\n".join(lines)
    if plan["picks"] and plan["picks"][0]["win_delta"] > 0:
        x = plan["picks"][0]
        drop = f", drop {x['drop']}" if x["drop"] else ""
        lines.append(f"Top add: {x['add']}{drop} ({x['win_delta']:+d}% win chance)")
    elif plan["pick_note"]:
        lines.append(plan["pick_note"])
    return "\n".join(lines)
