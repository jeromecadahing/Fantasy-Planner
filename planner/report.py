"""Render the plan as a static web page and a short text summary."""
from datetime import date, datetime, timedelta
import json
from html import escape
from zoneinfo import ZoneInfo

from .extras import clock
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
.v small{display:block;font:500 .72rem/1.3 Barlow,sans-serif;color:var(--muted);margin-top:2px}
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
.chip i{font-style:normal;font-size:.72rem;color:var(--muted);margin-right:5px;letter-spacing:.03em}
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
.wibest p{margin:0 0 12px;font-size:.95rem}
.wib{font:600 .85rem/1 Barlow,sans-serif;color:var(--on-you);background:var(--you);border:0;border-radius:6px;padding:6px 10px;margin-left:6px;cursor:pointer}
.wib:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
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
.warn{margin:10px 0 0;padding:8px 10px;border-left:3px solid var(--bad);background:color-mix(in srgb,var(--bad) 8%,transparent);border-radius:4px;font-size:.93rem}
code{font-size:.88em;background:var(--field);padding:1px 5px;border-radius:4px}
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--rule);margin:0 0 18px;overflow-x:auto;scrollbar-width:none}
.tabs button{font:600 1.1rem/1 "Barlow Condensed","Arial Narrow",sans-serif;color:var(--muted);background:none;border:0;
border-bottom:3px solid transparent;padding:10px 12px 9px;cursor:pointer;white-space:nowrap}
.tabs button[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--you)}
.tabs button:focus-visible{outline:2px solid var(--you);outline-offset:-2px;border-radius:4px}
.tabs .n{font:600 .78rem/1 Barlow,sans-serif;background:var(--opp-soft);color:var(--ink);border-radius:999px;padding:2px 6px;margin-left:5px;vertical-align:2px}
.lock{display:grid;grid-template-columns:auto 1fr;gap:6px 18px;align-items:center;background:var(--surface);
border:1px solid var(--rule);border-left:5px solid var(--you);border-radius:12px;padding:14px 16px;margin-bottom:16px}
.lock.soon{border-left-color:var(--opp)}.lock.past{border-left-color:var(--rule)}
.lk-time{font:700 clamp(2rem,7vw,2.8rem)/.95 "Barlow Condensed","Arial Narrow",sans-serif;font-variant-numeric:tabular-nums}
.lk-left{font:600 1.05rem/1.1 "Barlow Condensed","Arial Narrow",sans-serif;color:var(--you)}.lock.soon .lk-left{color:var(--opp)}
.lk-body p{margin:0 0 4px}.lk-body .dc{margin:0}
.lk-todo{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}
.lk-todo span{font:600 .92rem/1 Barlow,sans-serif;padding:5px 8px;border-radius:6px;background:var(--you-soft)}
.lk-next{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:6px 14px;border-top:1px solid var(--rule);padding-top:8px;font-size:.88rem;color:var(--muted)}
.lk-next b{color:var(--ink);font-weight:600}
.lk-next a{color:var(--you);font-weight:600}
@media (max-width:560px){.lock{grid-template-columns:1fr}.lk-cal{margin-left:0}
.tabs{gap:0}.tabs button{font-size:1rem;padding:10px 8px 9px}}
.seg{display:inline-flex;border:1px solid var(--rule);border-radius:8px;overflow:hidden;margin:0 0 12px}
.seg button{font:600 .92rem/1 Barlow,sans-serif;background:var(--field);color:var(--muted);border:0;padding:8px 12px;cursor:pointer}
.seg button+button{border-left:1px solid var(--rule)}
.seg button[aria-pressed="true"]{background:var(--you);color:var(--on-you)}
.seg button:focus-visible{outline:2px solid var(--ink);outline-offset:-2px}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;max-width:100%}
table.st{font-size:.92rem;min-width:640px}
table.st th{font:700 .95rem/1 "Barlow Condensed","Arial Narrow",sans-serif;text-align:right;padding:6px 6px 8px;color:var(--muted);white-space:nowrap}
table.st td{text-align:right;font-variant-numeric:tabular-nums;padding:7px 6px;color:var(--ink);white-space:nowrap}
table.st th:first-child,table.st td:first-child{text-align:left;position:sticky;left:0;background:var(--surface)}
table.st td:first-child{font-weight:600}table.st td:first-child small{display:block;font-weight:400;color:var(--muted);font-size:.8rem}
table.st td.hi{color:var(--good);font-weight:600}table.st td.lo{color:var(--bad)}
table.st tr.ir td{color:var(--muted)}
.logs{display:grid;gap:8px;margin-top:6px}
.logs details{border:1px solid var(--rule);border-radius:10px;padding:8px 12px;min-width:0}
.logs summary{cursor:pointer;display:flex;justify-content:space-between;gap:10px;font-weight:600}
.logs summary span{font-weight:400;color:var(--muted);font-size:.9rem}
.logs details[open] summary{margin-bottom:6px}
.inj{display:grid;gap:12px}
.ic{border:1px solid var(--rule);border-radius:12px;padding:12px 14px}
.ic.t-pos{border-left:4px solid var(--good)}.ic.t-warn{border-left:4px solid var(--warn)}.ic.t-you{border-left:4px solid var(--you)}
.ih{display:flex;justify-content:space-between;gap:10px;align-items:baseline;flex-wrap:wrap}
.ih strong{font:700 1.3rem/1.1 "Barlow Condensed","Arial Narrow",sans-serif}
.vd{font:700 1.05rem/1 "Barlow Condensed","Arial Narrow",sans-serif;padding:5px 9px;border-radius:6px;background:var(--field);color:var(--muted)}
.vd.t-pos{background:color-mix(in srgb,var(--good) 14%,transparent);color:var(--good)}
.vd.t-warn{background:color-mix(in srgb,var(--warn) 14%,transparent);color:var(--warn)}
.vd.t-you{background:var(--you-soft);color:var(--you)}
.facts{display:flex;flex-wrap:wrap;gap:4px 16px;margin:6px 0 8px;font-size:.9rem;color:var(--muted)}
.facts b{color:var(--ink);font-weight:600}
.ic ul{margin:0 0 6px;padding-left:1.1rem;display:grid;gap:4px;font-size:.95rem}
.line{display:flex;flex-wrap:wrap;gap:5px;margin:4px 0 8px}
.line span{font:600 .88rem/1 "Barlow Condensed","Arial Narrow",sans-serif;padding:4px 7px;border-radius:5px;background:var(--field);font-variant-numeric:tabular-nums}
.news{border-top:1px solid var(--rule);margin-top:6px;padding-top:6px;font-size:.9rem}
.news p{margin:2px 0 6px}.news .dc{display:block}
.order{margin:0 0 14px;padding-left:1.4rem;display:grid;gap:6px}
.order li::marker{font:700 1.05rem "Barlow Condensed","Arial Narrow",sans-serif;color:var(--you)}
.pf{display:flex;flex-wrap:wrap;gap:8px 10px;align-items:center;margin:0 0 12px}.pf .seg{margin:0}
.pf-q input{font:500 .95rem/1.2 Barlow,"Segoe UI",system-ui,sans-serif;color:var(--ink);background:var(--field);border:1px solid var(--rule);
border-radius:8px;padding:8px 10px;width:12rem;max-width:100%}
.pf-q input:focus-visible{outline:2px solid var(--you);outline-offset:1px}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.pf-chips{flex-wrap:wrap}
table.st th button{font:inherit;color:inherit;background:none;border:0;padding:0;cursor:pointer;white-space:nowrap}
table.st th button:focus-visible{outline:2px solid var(--you);outline-offset:2px;border-radius:3px}
table.st th[aria-sort="descending"] button::after{content:" ▾";color:var(--you)}
table.st th[aria-sort="ascending"] button::after{content:" ▴";color:var(--you)}
table.st th[aria-sort="descending"],table.st th[aria-sort="ascending"]{color:var(--ink)}
@media (max-width:560px){.pf-q,.pf-q input{width:100%}.pf-chips{display:flex;width:100%}.pf-chips button{flex:1 1 auto;padding:8px 8px}}
table.lg th[scope=row]{text-align:left;font:600 .95rem/1.2 Barlow,sans-serif;color:var(--ink);position:sticky;left:0;background:var(--surface);padding:7px 10px 7px 6px;white-space:nowrap;border-top:1px solid var(--rule)}
table.lg th[scope=row] small{display:block;font-weight:400;color:var(--muted);font-size:.78rem}
table.lg td.lg-c small{display:block;font-size:.72rem;color:var(--muted);font-weight:400}
table.lg td.lg-c.hi{color:var(--good)}table.lg td.lg-c.hi small{color:var(--good)}
table.lg td.lg-c.lo{color:var(--bad)}table.lg td.lg-c.lo small{color:var(--bad)}
table.lg tr.lg-me th[scope=row],table.lg tr.lg-me td,table.lg tr.lg-plan th[scope=row],table.lg tr.lg-plan td{background:var(--you-soft)}
table.lg tr.lg-me td.lg-c,table.lg tr.lg-plan td.lg-c{font-weight:600}
table.lg tr.lg-opp th[scope=row]{box-shadow:inset 3px 0 0 var(--opp)}
table.lg td.lg-w b{font:700 1.05rem/1 "Barlow Condensed","Arial Narrow",sans-serif}
table.lg td.lg-w small{display:block;font-size:.72rem;color:var(--muted)}
.lk-cal{margin-left:auto;display:inline-flex;gap:12px;align-items:center;flex-wrap:wrap}
.lk-cal button{font:600 .88rem/1 Barlow,sans-serif;color:var(--you);background:none;border:1px solid var(--rule);border-radius:6px;padding:5px 8px;cursor:pointer}
.lk-cal button:focus-visible{outline:2px solid var(--you);outline-offset:1px}
.lk-and{grid-column:1/-1;margin:0;font-size:.85rem}
table.sc td.sc-c,table.sc th.sc-d{text-align:center;padding:6px 3px;min-width:2rem}
table.sc th.sc-d span{display:block}table.sc th.sc-d small{display:block;font-weight:500;font-size:.75rem}
table.sc .sc-nx{border-left:2px solid var(--rule)}
table.sc th.sc-wk{text-align:center;font-size:.85rem;padding-bottom:2px}
table.sc .dot{display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--you)}
table.sc .dot.b2b{background:transparent;border:2.5px solid var(--opp);width:11px;height:11px}
table.sc td.sc-out{color:var(--bad);font-weight:700}
table.sc td.sc-none{background:repeating-linear-gradient(135deg,var(--field),var(--field) 4px,transparent 4px,transparent 8px)}
table.sc th.sc-none{color:var(--muted);font-weight:500}
table.sc td b{font-weight:700}
.sub3{font:700 1.1rem/1.1 "Barlow Condensed","Arial Narrow",sans-serif;margin:14px 0 4px}
.xlist{margin:0;padding-left:1.1rem;display:grid;gap:3px;font-size:.93rem}
.more{margin-top:14px;border-top:1px solid var(--rule);padding-top:10px}
.more>summary{cursor:pointer;font:700 1.1rem/1.2 "Barlow Condensed","Arial Narrow",sans-serif;color:var(--ink)}
.more[open]>summary{margin-bottom:10px}
table.trend td:first-child{white-space:nowrap}
#tab-plan>.panel,#tab-plan>section{margin-bottom:18px}
[hidden]{display:none!important}
@media (max-width:620px){.wi{grid-template-columns:1fr}.cg{grid-template-columns:repeat(5,1fr)}}
@media (max-width:820px){.plan{grid-template-columns:1fr}}
@media (max-width:520px){.row{grid-template-columns:3.1rem 1fr 2.6rem 1fr 3.1rem;gap:5px}}
"""

SHORT = {"Probable": "Prob", "Day-to-day": "DTD", "Questionable": "GTD", "Doubtful": "Doubt"}


def _pct(x):
    return f"{round(x * 100)}%"


def _now_val(c, tot):
    _, idx, _ = CATS[c]
    if isinstance(idx, tuple) and not tot[idx[1]]:
        return "–"
    return fmt_cat(c, tot)


def _board_now(data):
    """Today's actual totals for both sides, for the scoreboard, or None before any games count."""
    if not _now_line(data):
        return None
    return data["me"]["sofar"], data["opp"]["sofar"]


def _now_html(data):
    x = _now_line(data)
    if not x:
        return ""
    lead, trail, tie = x
    tied = f", {tie} tied" if tie else ""
    return (f'<p class="dc" style="margin:0 0 10px">Right now you lead {lead} categor{"y" if lead == 1 else "ies"} '
            f'and trail {trail}{tied}. Big numbers are projected finals; small ones are the actual totals so far.</p>')


def _nextmatch(plan, data):
    nm = plan.get("nextmatch")
    if not nm:
        why = ("ESPN’s schedule didn’t name your next opponent (a bye, the playoffs, or the season’s end)."
               if data.get("next_days") else "Next week’s NBA schedule isn’t available yet.")
        return f'<section class="panel" style="margin-bottom:18px"><h2>Next matchup</h2><p class="empty">{why}</p></section>'
    me, opp = data["me"]["name"], nm["name"]
    win = round(nm["win"] * 100)
    again = " again" if nm.get("same") else ""
    verdict = (f"{win}% chance you win next week against {escape(opp)}{again}."
               + ("" if win >= 50 else f" {escape(opp)} would be the favorite."))
    g_me, g_opp = nm.get("games") or (0, 0)
    swing = [CATS[i][0] for i in range(9) if 0.3 <= nm["catP"][i] <= 0.7]
    sw = (f'<p class="dc" style="margin:8px 0 0">Closest categories: {escape(", ".join(swing))}. '
          f'Pickups that help there are worth the most next week.</p>' if swing else "")
    return (f'<section class="board"><h2 style="margin-top:0">Next matchup</h2><div class="score">'
            f'<div class="side you"><span class="team">{escape(me)}</span><span class="big">{nm["cats"]:.1f}</span></div>'
            f'<div class="mid">categories<br>won</div>'
            f'<div class="side opp"><span class="team">{escape(opp)}</span><span class="big">{9 - nm["cats"]:.1f}</span></div></div>'
            f'<p class="verdict">{verdict}</p>'
            f'<p class="dc" style="margin:-6px 0 12px">Both rosters as they stand today, before any moves. Roster games scheduled: '
            f'you {g_me}, them {g_opp}. Uses season-long numbers, so this week’s form and boosts don’t carry over.</p>'
            f'<div class="tug">{_tug(nm)}</div>{sw}</section>')


def _now_line(data):
    """Who leads each category on the actual totals so far, or None before any games count."""
    me, op = data["me"].get("sofar") or [], data["opp"].get("sofar") or []
    if len(me) < 11 or len(op) < 11 or not (any(me) or any(op)):
        return None
    lead = trail = tie = 0
    for c, (_, idx, low) in enumerate(CATS):
        if isinstance(idx, tuple):
            a = me[idx[0]] / me[idx[1]] if me[idx[1]] else None
            b = op[idx[0]] / op[idx[1]] if op[idx[1]] else None
            if a is None or b is None:
                tie += 1
                continue
        else:
            a, b = me[idx], op[idx]
        if abs(a - b) < 1e-9:
            tie += 1
        elif (a < b) == low:
            lead += 1
        else:
            trail += 1
    return lead, trail, tie


def _tug(res, now=None):
    """One row per category: projected final totals and your chance; with now, today's actual totals too."""
    rows = []
    for c, (label, _, _) in enumerate(CATS):
        p = res["catP"][c]
        y, o = p * 100, (1 - p) * 100
        yl = (f'<b style="right:6px;color:var(--on-you)">{_pct(p)}</b>' if y >= 22
              else f'<b style="right:calc({y:.1f}% + 6px);color:var(--you)">{_pct(p)}</b>')
        ol = (f'<b style="left:6px;color:var(--on-opp)">{_pct(1 - p)}</b>' if o >= 22
              else f'<b style="left:calc({o:.1f}% + 6px);color:var(--opp)">{_pct(1 - p)}</b>')
        nl = nr = ""
        if now:
            nl = f'<small title="Actual total so far">now {_now_val(c, now[0])}</small>'
            nr = f'<small title="Actual total so far">now {_now_val(c, now[1])}</small>'
        rows.append(f'<div class="row"><span class="v l">{fmt_cat(c, res["mean"])}{nl}</span>'
                    f'<div class="bar y"><i style="width:{y:.1f}%"></i>{yl}</div><span class="cat">{label}</span>'
                    f'<div class="bar o"><i style="width:{o:.1f}%"></i>{ol}</div>'
                    f'<span class="v r">{fmt_cat(c, res["opp_mean"])}{nr}</span></div>')
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
            '<p class="hint" style="margin-top:10px">Big number: change in your chance to win the week.</p>')


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
    h += ('</ol><p class="hint" style="margin-top:10px">Make today’s moves; later steps can change as news comes in.</p>')
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
        slots = d.get("slot") or [None] * len(d["start"])
        chips = "".join(f'<span class="chip">{f"<i>{escape(sl)}</i>" if sl else ""}{escape(n)}'
                        f'{f"<small>{SHORT.get(s, s)}</small>" if pr < 1 else ""}</span>'
                        for (n, pr, s), sl in zip(d["start"], slots))
        chips += "".join(f'<span class="chip bench">{escape(n)}</span>' for n in d["bench"])
        if d.get("squeezed"):
            chips += (f'<p class="dc" style="margin:4px 0 0">{escape(", ".join(d["squeezed"]))} can’t start: '
                      f'the open spot{"s don’t" if d["open"] > 1 else " doesn’t"} fit his position.</p>')
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
var T=document.getElementById('wi-day'),A=document.getElementById('wi-add'),R=document.getElementById('wi-drop'),O=document.getElementById('wi-out'),B=document.getElementById('wi-best');
function opt(sel,t,v){var o=document.createElement('option');o.value=v;o.textContent=t;sel.appendChild(o);}
function gm(k){return k+' game'+(k==1?'':'s');}
D.days.forEach(function(d,i){opt(T,(d.today?'Today, ':'')+d.label,i);});
function sg(v,s){return (v>0?'+':v<0?'\u2212':'\u00b1')+Math.abs(v)+(s||'');}
function tone(v){return v>0?'pos':v<0?'neg':'flat';}
function ms(dt){var p=dt.split('-');return Date.UTC(+p[0],+p[1]-1,+p[2]);}
// Game days from day t (or before t), with back-to-back pairs flagged.
function sched(g,from,until){
  var ds=g.filter(function(d){return d>=from&&d<until;}),out=[],b2b=false;
  ds.forEach(function(d,i){var lab=D.dl[d].l;
    if(i>0&&ms(D.dl[d].dt)-ms(D.dl[ds[i-1]].dt)===864e5){b2b=true;}
    out.push(lab);});
  return {n:ds.length,txt:out.join(', '),b2b:b2b};
}
function b2bPairs(g,from){
  var ds=g.filter(function(d){return d>=from;}),pairs=[];
  for(var i=1;i<ds.length;i++){if(ms(D.dl[ds[i]].dt)-ms(D.dl[ds[i-1]].dt)===864e5)pairs.push(D.dl[ds[i-1]].l+'\u2013'+D.dl[ds[i]].l);}
  return pairs;
}
// A drop is "safe" if it's an open spot, or a non-keeper who isn't better than the add over the season.
function safe(a,r){var dp=D.drops[r];return dp.open||(!dp.keep&&dp.sv<=D.adds[a].sv);}
function bestDrop(row,a){var bi=-1;row.forEach(function(x,i){if(!safe(a,i))return;if(bi<0||x[0]>row[bi][0]||(x[0]===row[bi][0]&&x[1]>row[bi][1]))bi=i;});return bi;}
function addRank(a,r){var n=1;D.drops.forEach(function(dp,i){if(i!==r&&!dp.open&&dp.sv>D.adds[a].sv)n++;});return n;}
function fill(){
 var d=D.days[+T.value],ka=A.value,kr=R.value;A.innerHTML='';R.innerHTML='';
 var order=D.adds.map(function(p,i){var row=d.rows[i],bd=row?bestDrop(row,i):-1;return {i:i,bd:bd,best:bd>=0?row[bd][0]:-1e9};});
 order.sort(function(x,y){return y.best-x.best;});
 order.forEach(function(o){var p=D.adds[o.i],s=sched(p.g,d.t,1e9);
   var lab=p.name+' ('+p.team+(s.n?': '+s.txt+(s.b2b?', back-to-back':''):', no games left')+(p.status!=='Healthy'?', '+p.status:'')+')';
   if(s.n)lab+=o.bd>=0?'  best '+sg(Math.round(o.best/10),'%'):'  (only by cutting a keeper)';
   opt(A,lab,o.i);});
 D.drops.forEach(function(p,i){var s=sched(p.g,d.t,1e9);opt(R,p.open?p.name:p.name+' (#'+p.rank+' season'+(p.keep?', keeper':'')+'; gives up '+(s.n?s.txt:'nothing')+')',i);});
 if(ka!=='')A.value=ka; if(kr!=='')R.value=kr;
 var top=order[0];
 if(top&&top.bd>=0&&top.best>=10){var row=d.rows[top.i],bd=top.bd;
   B.innerHTML='<p>Best move starting '+d.label+': <strong>add '+D.adds[top.i].name+'</strong>, '+(D.drops[bd].open?'using your open spot':'drop '+D.drops[bd].name)+' <span class="delta pos">'+sg(Math.round(row[bd][0]/10),'%')+'</span> <button type="button" class="wib" id="wi-show">Show it</button></p>';
   document.getElementById('wi-show').onclick=function(){A.value=top.i;R.value=bd;show();};
 } else B.innerHTML='<p class="dc">No pickup starting '+d.label+' raises your chance to win by a point or more. Saving the add may be the better play.</p>';
}
function show(){
 var d=D.days[+T.value],a=+A.value,r=+R.value,p=D.adds[a],dp=D.drops[r],row=d.rows[a];
 if(!row){O.innerHTML='<p class="empty">'+p.name+' has no games left from '+d.label+', so adding him then wouldn\u2019t change anything. Pick an earlier day.</p>';return;}
 var x=row[r],b=Math.round(D.base.win*100),aw=Math.max(0,Math.min(100,b+Math.round(x[0]/10))),dw=aw-b;
 var cats=(D.base.cats+x[1]/100).toFixed(1),st=x[3]/10,cells='';
 D.cats.forEach(function(c,i){var bb=Math.round(D.base.catP[i]*100),aa=Math.max(0,Math.min(100,bb+x[2][i])),dd=aa-bb;
  cells+='<div class="cc'+(dd>=3?' pos':dd<=-3?' neg':'')+'"><b>'+c+'</b><span>'+aa+'%</span><small class="'+tone(dd)+'">'+sg(dd)+'</small></div>';});
 var sa=sched(p.g,d.t,1e9),sd=sched(dp.g,d.t,1e9),pairs=b2bPairs(p.g,d.t);
 var who=dp.open?'using your open roster spot':'dropping '+dp.name+(sd.n?' (he gives up '+sd.txt+')':' (no games left to give up)');
 var best=bestDrop(row,a),bnote=best>=0&&best!==r?' Best drop that doesn\u2019t cost you long-term: '+(D.drops[best].open?'your open spot':D.drops[best].name)+' ('+sg(Math.round(row[best][0]/10),'%')+').':'';
 var warn='';
 if(!safe(a,r)){var worse=dp.sv>p.sv;
   warn='<p class="warn"><strong>Long-term check:</strong> this number only covers this matchup. '+dp.name+' is your #'+dp.rank+' player over the season'
     +(worse?', and '+p.name+' would only be your #'+addRank(a,r)+'.':(dp.keep&&dp.rank>6?' and on your keep list.':'.'))
     +' Dropping him is permanent, so a one-week gain probably isn\u2019t worth it'+(best<0?'. None of your other drops are safe for this add either.':'.')+'</p>';}
 O.innerHTML='<p class="lift"><span class="cd">'+b+'%</span> <span class="arrow">\u2192</span> <span class="cd '+tone(dw)+'">'+aw+'%</span> chance to win the week <span class="delta '+tone(dw)+'">'+sg(dw,'%')+'</span></p>'
  +'<p>Adding '+p.name+' ('+p.team+'), who plays '+sa.txt+' for you, and '+who+'. '
  +(d.act?'Make the move in ESPN on '+d.act+'. ':'')+'Expected categories '+D.base.cats.toFixed(1)+' \u2192 '+cats+'; '
  +(Math.abs(st)<0.5?'about the same number of':(st>0?'+':'')+st.toFixed(1))+' starter games.'+bnote+'</p>'+warn
  +(pairs.length?'<p class="dc">Back-to-back: '+pairs.join(', ')+'. Teams sometimes rest players on the second night; the simulation doesn\u2019t assume that, so check the news before relying on both games.</p>':'')
  +(p.trend?'<p class="dc">'+p.trend+'</p>':'')+'<div class="cg">'+cells+'</div>';
}
T.addEventListener('change',function(){fill();show();});
A.addEventListener('change',function(){var a=+A.value,row=D.days[+T.value].rows[a],bd=row?bestDrop(row,a):-1;if(bd>=0)R.value=bd;show();});
R.addEventListener('change',show);
fill();var d0=D.days[0],o0=+A.value,b0=d0.rows[o0]?bestDrop(d0.rows[o0],o0):-1;if(b0>=0)R.value=b0;show();
})();"""


def _whatif(plan):
    g = plan.get("whatif") or {}
    sc = _scenario(plan.get("scenario"))
    help_ = ('<p class="hint" style="margin-top:12px">For someone not listed, like a trade target, go to <strong>Actions → '
             'Daily matchup plan → Run workflow</strong> and type e.g. <code>add: Jalen Brunson; drop: Grant Sato</code>.</p>')
    if not g.get("adds"):
        return sc + f'<p class="empty">{escape(g.get("note") or "No free agents to test.")}</p>' + help_
    data = dict(g)
    res = plan["result"]
    data["base"] = {"win": res["win"], "cats": res["cats"], "catP": res["catP"]}
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    return (sc + '<p class="hint">Pick a day, a pickup and a drop to see how your chances change.</p>'
            '<div class="wi"><label>Starting<select id="wi-day"></select></label><label>Add<select id="wi-add"></select></label>'
            '<label>Drop<select id="wi-drop"></select></label></div><div class="wibest" id="wi-best"></div><div class="wiout" id="wi-out" aria-live="polite"></div>'
            f'<script type="application/json" id="wi-data">{blob}</script><script>{WI_JS}</script>' + help_)


def _fa_cross(data, limit=5):
    """The best free agents who play both the last day of this matchup and the first day of next week."""
    from .whatif import season_value
    mine = {p["name"] for p in data["me"]["players"]}
    out = []
    for p in sorted(data["fa"], key=season_value, reverse=True):
        if p["name"] in mine or p["status"] == "Out":
            continue
        x = _sched(p, data)
        if x["cross"]:
            out.append((p, x))
        if len(out) == limit:
            break
    return out


def _fa_cross_html(data):
    names = _cross_names(data)
    rows = _fa_cross(data)
    if not names or not rows:
        return ""
    a, b = names
    items = "".join(f'<li><strong>{escape(p["name"])}</strong> <span class="dc">{escape(p["team"])}</span>: '
                    f'{x["next"]} game{"s" if x["next"] != 1 else ""} next week'
                    + (f', {x["b2b_next"]} back-to-back{"s" if x["b2b_next"] != 1 else ""}' if x["b2b_next"] else "")
                    + "</li>" for p, x in rows)
    return (f'<h3 class="sub3">Free agents who play {escape(a)} and {escape(b)}</h3>'
            f'<p class="dc" style="margin:0 0 4px">Added on {escape(a)}, they can play that day if you have a spot and start next week straight away.</p>'
            f'<ul class="xlist">{items}</ul>')


def _nextweek(plan, data):
    nw = plan.get("nextweek") or {}
    if not nw.get("range"):
        return f'<p class="empty">{escape(nw.get("note") or "Next week’s schedule isn’t available yet.")}</p>'
    day = escape(nw["day"])
    intro = (f'<p class="hint">Adds reset for next week, so any left on {day} are free. Moves for '
             f'{escape(nw["range"])}.</p>')
    games = nw.get("roster_games") or []
    few = [f"{escape(n)} ({g})" for n, g in games if g <= 2]
    roster_line = (f'<p class="dc" style="margin:0 0 10px">Fewest games next week on your roster: {", ".join(few)}.</p>'
                   if few else "")
    if not nw.get("moves"):
        stash = (f'<p class="dc">A spare add could also stash {escape(_join_words(nw["stash"]))} from the Injury watch tab.</p>'
                 if nw.get("stash") else "")
        return intro + f'<p class="empty">{escape(nw.get("note") or "")}</p>' + stash + _fa_cross_html(data)
    gain = nw["after_starts"] - nw["base_starts"]
    roster_line = ""  # the Schedule section on the same tab shows this in full
    h = (intro + f'<p class="lift"><span class="cd">{nw["base_starts"]:.0f}</span> <span class="arrow">→</span> '
         f'<span class="cd strong">{nw["after_starts"]:.0f}</span> expected starter games next week'
         f'{f" (+{gain:.1f})" if gain >= 0.5 else ""}, using {len(nw["moves"])} of your {nw["adds_left"]} spare '
         f'add{"s" if nw["adds_left"] != 1 else ""}.</p>' + roster_line + '<ol class="steps">')
    tag = '<span class="tag now">Do today</span>' if nw.get("today") else '<span class="tag">Planned</span>'
    for m in nw["moves"]:
        status = f' ({escape(m["add_status"])})' if m["add_status"] != "Healthy" else ""
        if m["drop"]:
            after = ""
            if m["drop_after_game"]:
                after = f" after his {day.split()[0]} game" + (f" ends (about {escape(clock(m['free_from']))} UK)" if m.get("free_from") else "")
            drop = (f'Drop {escape(m["drop"])}{after}'
                    + f' ({len(m["drop_days"])} game{"s" if len(m["drop_days"]) != 1 else ""} next week).'
                    + ("" if m["drop_is_streamer"] else " This one is a permanent cut."))
        else:
            drop = "Use your open roster spot."
        trend = f'<p>{escape(m["trend"])}</p>' if m.get("trend") else ""
        fa = next((p for p in data["fa"] if p["name"] == m["add"]), None)
        if fa is not None:
            x = _sched(fa, data)
            extra = []
            if x["cross"]:
                last_day = (_cross_names(data) or ("Sun", "Mon"))[0]
                extra.append(f"He also plays {last_day}, so he can fill an open spot that day too")
            if x["b2b_next"]:
                extra.append(f"{x['b2b_next']} back-to-back{'s' if x['b2b_next'] != 1 else ''} next week")
            if extra:
                trend = f'<p>{escape(". ".join(extra))}.</p>' + trend
        h += (f'<li class="step"><div class="sh"><span class="dn">{day}</span>{tag}</div>'
              f'<p class="act"><strong>Add {escape(m["add"])}</strong> <span class="dc">{escape(m["add_team"])}{status}</span></p>'
              f'<p>{drop} He plays {len(m["add_days"])} game{"s" if len(m["add_days"]) != 1 else ""} next week: '
              f'{escape(", ".join(m["add_days"]))}.</p>{trend}</li>')
    h += "</ol>" + _fa_cross_html(data)
    if nw.get("stash"):
        h += f'<p class="dc">Spare add left over? It could also stash {escape(_join_words(nw["stash"]))} from the Injury watch tab.</p>'
    late = any(m["drop_after_game"] for m in nw["moves"])
    h += ('<p class="hint" style="margin-top:10px">Counts only games on days you have a free lineup spot.'
          + (" A move made after ESPN starts the new week uses one of next week’s adds." if late else "") + "</p>")
    return h


def _ord(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _league(plan):
    L = plan.get("league")
    if not L:
        return ""
    n = L["n_teams"]
    third = max(1, round(n / 3))

    def cell(t, c, mine):
        r = t["ranks"][c]
        cls = (" hi" if r <= third else " lo" if r > n - third else "") if mine else ""
        return f'<td class="lg-c{cls}">{escape(t["shown"][c])}<small>{_ord(r)}</small></td>'

    def chance(t):
        if t.get("me"):
            return "<td></td>"
        w = round(t["win"] * 100)
        cls = "pos" if w > 55 else "neg" if w < 45 else "flat"
        plan_txt = f'<small>{round(t["win_plan"] * 100)}% with plan</small>' if "win_plan" in t else ""
        return f'<td class="lg-w"><b class="{cls}">{w}%</b>{plan_txt}</td>'

    teams = L["teams"]
    me = next(t for t in teams if t.get("me"))
    rivals = sorted((t for t in teams if not t.get("me")), key=lambda t: (not t.get("opp"), t["win"]))
    rows = (f'<tr class="lg-me"><th scope="row">{escape(me["name"])}<small>You, no more moves</small></th>'
            + "".join(cell(me, c, True) for c in range(9)) + "<td></td></tr>")
    if L.get("plan_row"):
        pr = L["plan_row"]
        rows += (f'<tr class="lg-plan"><th scope="row">{escape(me["name"])}<small>With your streaming plan</small></th>'
                 + "".join(cell(pr, c, True) for c in range(9)) + "<td></td></tr>")
    for t in rivals:
        tag = "<small>This week’s opponent</small>" if t.get("opp") else ""
        rows += (f'<tr{" class=lg-opp" if t.get("opp") else ""}><th scope="row">{escape(t["name"])}{tag}</th>'
                 + "".join(cell(t, c, False) for c in range(9)) + chance(t) + "</tr>")
    head = "".join(f"<th>{escape(label)}</th>" for label, _, _ in CATS)
    rivals_n = n - 1
    line = f'As things stand you’d beat <strong>{L["beats"]} of {rivals_n}</strong> teams head-to-head this week'
    if L.get("beats_plan") is not None:
        line += f', or <strong>{L["beats_plan"]} of {rivals_n}</strong> with your streaming plan'
    line += f'. Your average category rank is {L["avg_rank"]:.1f} out of {n}.'
    best = [CATS[c][0] for c in range(9) if me["ranks"][c] == 1]
    if best:
        line += f' You’d lead the league in {_join_words(best)}.'
    note = ("" if not L.get("partial") else
            "<p class=dc>Only your matchup could be read this week, so the table shows just you and your opponent.</p>")
    return (f'<section class="panel" style="margin-bottom:18px"><h2>Your week across the league</h2>'
            f'<p class="lift" style="font-size:1rem">{line}</p>'
            f'<p class="hint">Projected final totals, with rank out of {n}. Other teams are shown without pickups. '
            f'Last column: your chance if you played them.</p>'
            f'{note}<div class="scroll"><table class="st lg"><thead><tr><th>Team</th>{head}<th>Your chance</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div></section>')


def _join_words(xs):
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


# ---------- Deadline banner ----------

def _lock(plan):
    dl = plan.get("deadlines") or []
    if not dl:
        return ('<section class="lock past"><div class="lk-time">No games</div><div class="lk-body"><p>No games left for your '
                "players in this matchup. The next run picks up the new week once ESPN rolls it over.</p></div></section>")
    first = dl[0]
    todo = "".join(f"<span>{escape(m)}</span>" for m in first["moves"])
    def _next(d):
        n = len(d["moves"])
        moves = f", {n} move{'s' if n != 1 else ''}" if n else ""
        return (f'<span>{escape(d["label"].split()[0])}’s games lock <b>{escape(d["lock_txt"].split(" UK")[0])}</b>'
                f'{moves}</span>')

    nxt = "".join(_next(d) for d in dl[1:5]).replace("<span>", "<span>Next: ", 1)
    blob = json.dumps([{"at": d["lock"], "label": d["label"], "txt": d["lock_txt"], "why": d["why"], "moves": d["moves"]}
                       for d in dl], separators=(",", ":")).replace("</", "<\\/")
    return (f'<section class="lock" id="lock" aria-live="polite"><div><div class="lk-time" id="lk-time">'
            f'{escape(first["lock_txt"].split(" UK")[0])}</div><div class="lk-left" id="lk-left"></div></div>'
            f'<div class="lk-body"><p id="lk-head"><strong>{"Today’s" if first["today"] else escape(first["label"]) + "’s"} roster window '
            f'closes at {escape(first["lock_txt"])}.</strong></p><p class="dc" id="lk-why">{escape(first["why"])} then. '
            f'Make pickups and set your lineup before.</p>'
            f'<div class="lk-todo" id="lk-todo">{todo}</div>'
            f'{"" if todo else "<p class=dc id=lk-none>No pickups planned for this day. Just check your lineup and late scratches.</p>"}</div>'
            f'<div class="lk-next">{nxt}<span class="lk-cal"><a id="lk-cal" href="reminders.ics">Add deadlines to your calendar</a>'
            f'<button type="button" id="lk-copy" hidden>Copy calendar link</button></span></div>'
            f'<p class="dc lk-and" id="lk-and" hidden>On Android this opens Google Calendar; tap <strong>Add</strong>. '
            f'Google refreshes subscribed calendars only every several hours, so late plan changes can be missed. '
            f'The Discord reminder is more dependable.</p>'
            f'<script type="application/json" id="lk-data">{blob}</script></section>')


# ---------- Schedule: games, back-to-backs, Sunday-Monday ----------

def _columns(data):
    """Day columns for the rest of this week and all of next week, oldest first.

    ESPN only lists days with NBA games, so a day without any (Election Day, say) would vanish.
    Missing days between two listed ones come back as columns marked none=True, so the
    calendar reads straight through. Each column keeps its index into days or next_days.
    """
    from datetime import date as _d
    days, nd, ti = data["days"], data.get("next_days") or [], data["today_index"]
    cols = [{"date": _d.fromisoformat(days[i]["date"]), "label": days[i]["label"], "week": 0, "i": i, "none": False}
            for i in range(ti, len(days))]
    cols += [{"date": _d.fromisoformat(d["date"]), "label": d["label"], "week": 1, "i": i, "none": False}
             for i, d in enumerate(nd)]
    out = []
    for c in cols:
        if out:
            gap = out[-1]["date"] + timedelta(days=1)
            while gap < c["date"]:
                out.append({"date": gap, "label": gap.strftime("%a %b %-d"), "i": None, "none": True,
                            "week": out[-1]["week"] if out[-1]["week"] == c["week"] else 1})
                gap += timedelta(days=1)
        out.append(c)
    return out


def _sched(p, data):
    """A player's remaining games this week and next week, with back-to-backs found from the dates.

    Games he's ruled out of (chance 0) are kept for display but not counted.
    """
    ng, npb = p.get("next_games") or [], p.get("next_prob") or []
    cells = []
    for col in _columns(data):
        c = dict(col)
        i = col["i"]
        if col["none"]:
            g = ok = False
        elif col["week"] == 0:
            g = bool(p["games"][i])
            ok = g and p["prob"][i] > 0
        else:
            g = bool(ng[i]) if i < len(ng) else False
            ok = g and (npb[i] if i < len(npb) else 1) > 0
        c.update(game=g, ok=ok)
        cells.append(c)
    by_date = {c["date"]: c for c in cells}
    b2b = 0
    for c in cells:
        prev = by_date.get(c["date"] - timedelta(days=1))
        c["b2b"] = bool(c["ok"] and prev and prev["ok"])
        b2b += c["b2b"]
    last = [c for c in cells if c["week"] == 0 and not c["none"]]
    first = [c for c in cells if c["week"] == 1 and not c["none"]]
    cross = bool(last and first and last[-1]["ok"] and first[0]["ok"]
                 and (first[0]["date"] - last[-1]["date"]).days == 1)
    return {"cells": cells, "this": sum(c["ok"] for c in cells if c["week"] == 0),
            "next": sum(c["ok"] for c in cells if c["week"] == 1), "b2b": b2b, "cross": cross,
            "b2b_next": sum(c["b2b"] for c in cells if c["week"] == 1)}


def _day_heads(cols):
    """Header cells for day columns, with a heavier line where next week starts."""
    out = ""
    for k, c in enumerate(cols):
        cls = " sc-nx" if c["week"] == 1 and (k == 0 or cols[k - 1]["week"] == 0) else ""
        if c["none"]:
            out += (f'<th class="sc-d sc-none{cls}" title="No NBA games on {escape(c["label"])}">'
                    f'<span>{escape(c["label"].split()[0])}</span><small>{c["date"].day}</small></th>')
        else:
            out += f'<th class="sc-d{cls}"><span>{escape(c["label"].split()[0])}</span><small>{c["date"].day}</small></th>'
    return out


def _week_head(cols, lead, tail):
    """The 'Rest of this week | Next week' row over the day columns."""
    n_this = sum(1 for c in cols if c["week"] == 0)
    n_next = len(cols) - n_this
    row = f"<tr>{lead}"
    if n_this:
        row += f'<th colspan="{n_this}" class="sc-wk">Rest of this week</th>'
    if n_next:
        row += f'<th colspan="{n_next}" class="sc-wk sc-nx">Next week</th>'
    return row + f"{tail}</tr>"


def _cross_names(data):
    """Day names for the last day of this matchup and the first of next week, e.g. ('Sun', 'Mon')."""
    days, nd = data["days"], data.get("next_days") or []
    if not days or not nd:
        return None
    return days[-1]["label"].split()[0], nd[0]["label"].split()[0]


def _schedule_section(data):
    nd = data.get("next_days") or []
    players = [p for p in data["me"]["players"]]
    if not nd:
        return ('<section class="panel" style="margin-bottom:18px"><h2>Schedule</h2><p class="empty">Next week’s '
                "NBA schedule isn’t available yet.</p></section>")
    info = [(p, _sched(p, data)) for p in players]
    info.sort(key=lambda x: (x[0]["ir"], -x[1]["next"], -x[1]["this"], x[0]["name"]))
    cells0 = info[0][1]["cells"] if info else _columns(data)
    a, b = _cross_names(data) or ("Sun", "Mon")
    head1 = _week_head(cells0, "<th></th>", '<th colspan="4"></th>')
    head2 = "<tr><th>Player</th>" + _day_heads(cells0)
    head2 += (f'<th>This wk</th><th>Next wk</th><th title="Back-to-back pairs, rest of this week and next week">B2B</th>'
              f'<th title="Plays the last day of this matchup and the first day of next week">{escape(a)}+{escape(b)}</th></tr>')
    rows = ""
    for p, x in info:
        tds = ""
        for i, c in enumerate(x["cells"]):
            cls = "sc-c" + (" sc-nx" if c["week"] == 1 and (i == 0 or x["cells"][i - 1]["week"] == 0) else "")
            if c["none"]:
                tds += f'<td class="{cls} sc-none" title="No NBA games"></td>'
            elif c["game"] and not c["ok"]:
                tds += f'<td class="{cls} sc-out" title="Game, but ruled out">×</td>'
            elif c["b2b"]:
                tds += f'<td class="{cls}" title="Second night of a back-to-back"><i class="dot b2b"></i></td>'
            elif c["ok"]:
                tds += f'<td class="{cls}" title="Game"><i class="dot"></i></td>'
            else:
                tds += f'<td class="{cls}"></td>'
        tag = escape(p["team"]) + (f", {escape(p['status'])}" if p["status"] != "Healthy" else "") + (", IR" if p["ir"] else "")
        rows += (f'<tr{" class=ir" if p["ir"] else ""}><td>{escape(p["name"])}<small>{tag}</small></td>{tds}'
                 f'<td>{x["this"]}</td><td><b>{x["next"]}</b></td><td>{x["b2b"] or ""}</td>'
                 f'<td>{"✓" if x["cross"] else ""}</td></tr>')
    both = [p["name"] for p, x in info if x["cross"] and not p["ir"]]
    line = (f'<p class="lift" style="font-size:1rem">Play both {escape(a)} and {escape(b)}: '
            f'<strong>{escape(_join_words(both))}</strong>.</p>' if both else
            f'<p class="lift" style="font-size:1rem">None of your players has games on both {escape(a)} and {escape(b)}.</p>')
    return (f'<section class="panel" style="margin-bottom:18px"><h2>Schedule</h2>{line}'
            f'<p class="hint">Ringed dot: second night of a back-to-back. ×: ruled out. Grey column: no NBA games that day.</p>'
            f'<div class="scroll"><table class="st sc"><thead>{head1}{head2}</thead><tbody>{rows}</tbody></table></div></section>')


def _teams_section(data):
    ts, nd = data.get("team_sched") or {}, data.get("next_days") or []
    if not ts or not nd:
        return ""
    cols = _columns(data)
    names = _cross_names(data) or ("Sun", "Mon")
    mine = {p["team"] for p in data["me"]["players"] if not p["ir"]}
    ti = data["today_index"]
    last_date = cols and next((c["date"] for c in reversed(cols) if c["week"] == 0 and not c["none"]), None)
    rows = []
    for team, x in ts.items():
        this, nxt = x.get("this") or [], x["next"]
        g = []
        for c in cols:
            if c["none"]:
                g.append(False)
            elif c["week"] == 0:
                k = c["i"] - ti
                g.append(bool(this[k]) if 0 <= k < len(this) else False)
            else:
                g.append(bool(nxt[c["i"]]) if c["i"] < len(nxt) else False)
        second = [k > 0 and g[k] and g[k - 1] for k in range(len(g))]  # columns are consecutive days
        pairs = [f'{cols[k - 1]["label"].split()[0]}–{cols[k]["label"].split()[0]}'
                 for k in range(len(g)) if second[k] and cols[k]["week"] == 1 and cols[k - 1]["week"] == 1]
        first_next = next((k for k, c in enumerate(cols) if c["week"] == 1 and not c["none"]), None)
        cross = bool(x.get("last") and first_next is not None and g[first_next] and last_date
                     and (cols[first_next]["date"] - last_date).days == 1)
        rows.append({"team": team, "g": g, "second": second, "pairs": pairs, "cross": cross,
                     "this": sum(v for v, c in zip(g, cols) if c["week"] == 0),
                     "n": sum(v for v, c in zip(g, cols) if c["week"] == 1)})
    rows.sort(key=lambda r: (-len(r["pairs"]), -r["n"], -r["this"], r["team"]))
    with_b2b = [r for r in rows if r["pairs"]]
    body = ""
    for r in rows:
        cells = ""
        for k, c in enumerate(cols):
            cls = "sc-c" + (" sc-nx" if c["week"] == 1 and (k == 0 or cols[k - 1]["week"] == 0) else "")
            if c["none"]:
                cells += f'<td class="{cls} sc-none" title="No NBA games"></td>'
            elif r["second"][k]:
                cells += f'<td class="{cls}"><i class="dot b2b"></i></td>'
            elif r["g"][k]:
                cells += f'<td class="{cls}"><i class="dot"></i></td>'
            else:
                cells += f'<td class="{cls}"></td>'
        you = ' <span class="dc">(yours)</span>' if r["team"] in mine else ""
        body += (f'<tr><td>{escape(r["team"])}{you}</td>{cells}<td>{r["this"]}</td><td><b>{r["n"]}</b></td>'
                 f'<td style="text-align:left">{escape(", ".join(r["pairs"]))}</td><td>{"✓" if r["cross"] else ""}</td></tr>')
    if with_b2b:
        line = (f'<p class="lift" style="font-size:1rem">{len(with_b2b)} of {len(rows)} teams play a back-to-back next week. '
                f'They’re listed first.</p>')
    else:
        line = '<p class="lift" style="font-size:1rem">No team plays back-to-back next week.</p>'
    head1 = _week_head(cols, "<th></th>", '<th colspan="4"></th>')
    head2 = (f'<tr><th>Team</th>{_day_heads(cols)}<th>This wk</th><th>Next wk</th>'
             f'<th style="text-align:left">Back-to-backs next week</th><th>{escape(names[0])}+{escape(names[1])}</th></tr>')
    return (f'<section class="panel" style="margin-bottom:18px"><h2>NBA teams, this week and next</h2>{line}'
            f'<p class="hint">Ringed dot: second night of a back-to-back. Grey column: no NBA games that day. '
            f'Scroll sideways for more days.</p>'
            f'<div class="scroll"><table class="st sc"><thead>{head1}{head2}</thead><tbody>{body}</tbody></table></div></section>')


# ---------- My players ----------

AVG_COLS = [("GP", "GP"), ("MIN", "MIN"), ("PTS", "PTS"), ("REB", "REB"), ("AST", "AST"), ("STL", "STL"),
            ("BLK", "BLK"), ("3PM", "3PM"), ("TO", "TO")]
SPLIT_ORDER = ["Season", "Last 15", "Last 7", "Last season"]


def _num(v, d=1):
    return "–" if v is None else f"{v:.{d}f}"


def _pctx(m, a):
    return "–" if not a else f"{m / a:.3f}".lstrip("0")


def _cmp_cls(v, base, key):
    if v is None or not base or base.get(key) is None:
        return ""
    b = base[key]
    if key == "TO":
        return " class=lo" if v >= b + 1.5 else " class=hi" if b >= 1.5 and v <= b - 1.5 else ""
    if key in ("GP", "MIN"):
        return ""
    gap = max(b * 0.3, 1.5 if key in ("PTS", "REB", "AST") else 1)
    return " class=hi" if v >= b + gap else " class=lo" if v <= b - gap else ""


def _players_tab(data):
    players = data["me"]["players"]
    if not any(p.get("card") for p in players):
        return ('<p class="empty">ESPN didn’t send per-game stats on this run. They’re pulled from player cards, '
                "which ESPN sometimes leaves out; the next run will try again.</p>")
    days = data["days"]
    ti = data["today_index"]
    tables = []
    sort_cols = [c for c, _ in AVG_COLS] + ["FG%", "FT%", "Left", "Next"]
    for k, split in enumerate(SPLIT_ORDER):
        rows = ""
        for p in sorted(players, key=lambda p: (p["ir"], -((p.get("card") or {}).get("avgs", {}).get("Season", {}).get("PTS", 0)))):
            a = (p.get("card") or {}).get("avgs", {}).get(split)
            left = [days[d]["label"].split()[0] for d in range(ti, len(days)) if p["games"][d]]
            nx = _sched(p, data)
            nxt_td = f'<td data-v="{nx["next"]}" title="Games next week">{nx["next"]}</td>'
            tag = f'{escape(p["team"])}, {escape(p["status"])}' if p["status"] != "Healthy" else escape(p["team"])
            if p["ir"]:
                tag += ", IR"
            flags = ["all"]
            if left and not p["ir"]:
                flags.append("week")
            if ti < len(days) and p["games"][ti] and not p["ir"]:
                flags.append("today")
            attrs = (f' data-name="{escape(p["name"].lower())}" data-f="{" ".join(flags)}"'
                     + (' class="ir"' if p["ir"] else ""))
            base = (p.get("card") or {}).get("avgs", {}).get("Season") if split in ("Last 15", "Last 7") else None
            if not a:
                rows += (f'<tr{attrs}><td>{escape(p["name"])}<small>{tag}</small></td>'
                         f'<td colspan="11" style="text-align:left;color:var(--muted)">No games in this span</td>'
                         f'<td data-v="{len(left)}">{len(left)}</td>{nxt_td}</tr>')
                continue
            cells = "".join(f'<td data-v="{a.get(c) or 0:.3f}"{_cmp_cls(a.get(c), base, c)}>{_num(a.get(c), 0 if c == "GP" else 1)}</td>'
                            for c, _ in AVG_COLS)
            fg = a.get("FGM", 0) / a["FGA"] if a.get("FGA") else 0
            ft = a.get("FTM", 0) / a["FTA"] if a.get("FTA") else 0
            rows += (f'<tr{attrs}><td>{escape(p["name"])}<small>{tag}</small></td>{cells}'
                     f'<td data-v="{fg:.4f}">{_pctx(a.get("FGM", 0), a.get("FGA", 0))}</td>'
                     f'<td data-v="{ft:.4f}">{_pctx(a.get("FTM", 0), a.get("FTA", 0))}</td>'
                     f'<td data-v="{len(left)}" title="{escape(", ".join(left))}">{len(left)}</td>{nxt_td}</tr>')
        head = "".join(f'<th aria-sort="none"><button type="button" data-col="{i + 1}" data-low="{1 if c == "TO" else 0}">{c}</button></th>'
                       for i, c in enumerate(sort_cols))
        tables.append(f'<div class="scroll" data-split="{k}"{"" if k == 0 else " hidden"}><table class="st"><thead><tr>'
                      f'<th>Player</th>{head}</tr></thead>'
                      f'<tbody>{rows}</tbody></table><p class="empty pf-none" hidden>No players match this filter.</p></div>')
    seg = "".join(f'<button type="button" data-k="{k}" aria-pressed="{"true" if k == 0 else "false"}">{s_}</button>'
                  for k, s_ in enumerate(SPLIT_ORDER))
    chips = "".join(f'<button type="button" data-f="{f}" aria-pressed="{"true" if f == "all" else "false"}">{l}</button>'
                    for f, l in (("all", "All"), ("today", "Playing today"), ("week", "Playing this week")))
    filters = (f'<div class="pf"><label class="pf-q"><span class="sr">Find a player</span>'
               f'<input type="search" id="pf-q" placeholder="Find a player" autocomplete="off"></label>'
               f'<div class="seg" id="split-seg">{seg}</div><div class="seg pf-chips" id="pf-chips">{chips}</div></div>')

    logs = ""
    for p in players:
        log = (p.get("card") or {}).get("log") or []
        if not log:
            continue
        base = (p.get("card") or {}).get("avgs", {}).get("Season")
        rows = ""
        for g in log:
            cells = "".join(f'<td{_cmp_cls(g.get(c), base, c)}>{_num(g.get(c), 0)}</td>'
                            for c in ("MIN", "PTS", "REB", "AST", "STL", "BLK", "3PM", "TO"))
            rows += (f'<tr><td>{escape(g["date"])} <small style="display:inline;color:var(--muted)">{escape(g["opp"])}</small></td>{cells}'
                     f'<td>{int(g.get("FGM", 0))}-{int(g.get("FGA", 0))}</td><td>{int(g.get("FTM", 0))}-{int(g.get("FTA", 0))}</td></tr>')
        last = log[0]
        logs += (f'<details><summary>{escape(p["name"])}<span>Last game {escape(last["date"])}: {_num(last.get("PTS"), 0)} pts, '
                 f'{_num(last.get("REB"), 0)} reb, {_num(last.get("AST"), 0)} ast</span></summary><div class="scroll"><table class="st">'
                 f'<thead><tr><th>Game</th><th>MIN</th><th>PTS</th><th>REB</th><th>AST</th><th>STL</th><th>BLK</th><th>3PM</th>'
                 f'<th>TO</th><th>FG</th><th>FT</th></tr></thead><tbody>{rows}</tbody></table></div></details>')
    return (f'<section class="panel" style="margin-bottom:18px"><h2>Per-game averages</h2>'
            f'<p class="hint">Green and red: well above or below his season average. Tap a heading to sort.</p>{filters}{"".join(tables)}</section>'
''
            f'<section class="panel"><h2>Game logs</h2><p class="hint">Last 10 games, compared with his season average.</p><div class="logs">{logs or "<p class=empty>No games played yet this season.</p>"}</div></section>')


# ---------- Injury watch ----------

def _line_chips(x):
    a = x.get("line")
    if not a:
        return ""
    chips = [f'{_num(a.get(k))} {k.lower() if k not in ("3PM", "TO") else k}' for k in ("PTS", "REB", "AST", "STL", "BLK", "3PM", "TO")]
    chips += [f'{_pctx(a.get("FGM", 0), a.get("FGA", 0))} FG', f'{_pctx(a.get("FTM", 0), a.get("FTA", 0))} FT']
    return (f'<p class="dc" style="margin:0">Per game, {escape(x["source"] or "")}:</p>'
            f'<div class="line">{"".join(f"<span>{escape(c)}</span>" for c in chips)}</div>')


def _nice_date(iso):
    try:
        return date.fromisoformat(iso[:10]).strftime("%a %b %-d")
    except (TypeError, ValueError):
        return iso or ""


def _injury_tab(data):
    watch = data.get("injury_watch") or []
    help_ = ('<p class="hint" style="margin-top:14px">Track more players by adding names to the <code>WATCH_PLAYERS</code> '
             'variable in GitHub (Settings → Secrets and variables → Actions → Variables).</p>')
    miss = "".join(f'<p class="warn">Couldn’t find “{escape(m)}” in ESPN’s player list. Check the spelling in WATCH_PLAYERS.</p>'
                   for m in data.get("watch_missing") or [])
    if not watch:
        return miss + '<p class="empty">No injured players to track right now: none of your players are hurt and no injured free agent would crack your lineup.</p>' + help_
    grab = [x for x in watch if x["bucket"] <= 2 and x["owner"] in ("Free agent", "On waivers")]
    order = ""
    if grab:
        order = ('<h2>Who to grab first</h2><p class="hint">Most urgent first.</p>'
                 '<ol class="order">'
                 + "".join(f'<li><strong>{escape(x["name"])}</strong>: {escape(x["verdict"])}'
                           + (f" (your #{x['rank']} player when healthy)" if x.get("rank") else "") + "</li>"
                           for x in grab) + "</ol>")
    cards_ = ""
    for x in watch:
        facts = [f'<span>Status <b>{escape(x["status"])}</b></span>', f'<span><b>{escape(x["owner"])}</b></span>']
        if x.get("ret"):
            d = x["days_out"]
            when = "today" if d == 0 else f"in {d} days" if d and d > 0 else "date passed, check news"
            ret_txt = date.fromisoformat(x["ret"]).strftime("%a %b %-d")
            facts.append(f'<span>ESPN return estimate <b>{ret_txt}</b> ({when})</span>')
        else:
            facts.append("<span>Return date <b>none from ESPN</b></span>")
        if x.get("games_left") is not None:
            facts.append(f'<span>NBA games left{" after return" if x.get("ret") else ""} <b>{x["games_left"]}</b></span>')
        if x.get("own") is not None:
            ch = x.get("own_change")
            facts.append(f'<span>Rostered <b>{x["own"]:.0f}%</b>'
                         + (f' ({"+" if ch > 0 else ""}{ch:.1f})' if ch else "") + "</span>")
        news = "".join(f'<p><span class="dc">{escape(_nice_date(n["published"]))}</span><strong>{escape(n["headline"])}</strong>'
                       f'{(" " + escape(n["story"])) if n["story"] and n["story"] != n["headline"] else ""}</p>'
                       for n in (x.get("news") or [])[:2])
        cls = {"pos": " t-pos", "warn": " t-warn", "you": " t-you"}.get(x["tone"], "")
        cards_ += (f'<article class="ic{cls}"><div class="ih"><strong>{escape(x["name"])} <span class="dc">{escape(x["team"])}'
                   f'{", watch list" if x["watch"] else ""}</span></strong><span class="vd{cls}">{escape(x["verdict"])}</span></div>'
                   f'<div class="facts">{"".join(facts)}</div>{_line_chips(x)}'
                   f'<ul>{"".join(f"<li>{escape(w)}</li>" for w in x["why"])}</ul>'
                   f'{f"<div class=news>{news}</div>" if news else ""}</article>')
    return (miss + f'<section class="panel" style="margin-bottom:18px">{order}<h2>Injured players</h2>'
            f'<p class="hint">Return dates are ESPN’s estimates and often move.</p><div class="inj">{cards_}</div>{help_}</section>')


PAGE_JS = r"""(function(){
var tabs=[].slice.call(document.querySelectorAll('.tabs button')),ids=tabs.map(function(b){return b.dataset.tab;});
function go(id,push){if(ids.indexOf(id)<0)id=ids[0];tabs.forEach(function(b){var on=b.dataset.tab===id;b.setAttribute('aria-selected',on);b.tabIndex=on?0:-1;
 document.getElementById('tab-'+b.dataset.tab).hidden=!on;});if(push){try{history.replaceState(null,'','#'+id);}catch(e){}}}
tabs.forEach(function(b,i){b.onclick=function(){go(b.dataset.tab,true);};b.onkeydown=function(e){var k=e.key==='ArrowRight'?1:e.key==='ArrowLeft'?-1:0;
 if(k){var n=tabs[(i+k+tabs.length)%tabs.length];n.focus();go(n.dataset.tab,true);}};});
go((location.hash||'').slice(1),false);window.addEventListener('hashchange',function(){go(location.hash.slice(1),false);});
var seg=document.getElementById('split-seg');if(seg){seg.onclick=function(e){var b=e.target.closest('button');if(!b)return;
 [].forEach.call(seg.children,function(x){x.setAttribute('aria-pressed',x===b);});
 [].forEach.call(document.querySelectorAll('[data-split]'),function(t){t.hidden=t.dataset.split!==b.dataset.k;});};}
// Filters and sorting apply to all four split tables, so switching split keeps your view.
var q=document.getElementById('pf-q'),chips=document.getElementById('pf-chips'),flt='all',sortCol=0,sortDir=0;
function apply(){var term=(q&&q.value||'').trim().toLowerCase();
 [].forEach.call(document.querySelectorAll('[data-split]'),function(box){var shown=0;
  [].forEach.call(box.querySelectorAll('tbody tr'),function(r){var ok=(' '+r.dataset.f+' ').indexOf(' '+flt+' ')>=0&&r.dataset.name.indexOf(term)>=0;r.hidden=!ok;if(ok)shown++;});
  box.querySelector('.pf-none').hidden=shown>0;});}
function val(r){var c=r.children[sortCol];if(!c||c.colSpan>1)return null;var v=parseFloat(c.dataset.v);return isNaN(v)?null:v;}
function sortAll(){[].forEach.call(document.querySelectorAll('[data-split] tbody'),function(tb){
 var rows=[].slice.call(tb.children),orig=rows.map(function(r,i){return i;});
 rows.forEach(function(r,i){if(r.dataset.i===undefined)r.dataset.i=i;});
 rows.sort(function(a,b){if(!sortCol)return a.dataset.i-b.dataset.i;var x=val(a),y=val(b);
  if(x===null&&y===null)return a.dataset.i-b.dataset.i;if(x===null)return 1;if(y===null)return -1;return sortDir*(y-x)||a.dataset.i-b.dataset.i;});
 rows.forEach(function(r){tb.appendChild(r);});});
 [].forEach.call(document.querySelectorAll('[data-split] th[aria-sort]'),function(th){var b=th.querySelector('button');
  th.setAttribute('aria-sort',sortCol&&+b.dataset.col===sortCol?(sortDir>0?'descending':'ascending'):'none');});}
document.addEventListener('click',function(e){var b=e.target.closest('[data-split] th button');if(!b)return;var c=+b.dataset.col;
 // First tap sorts best-first (lowest first for TO), second tap reverses, third clears.
 var best=b.dataset.low==='1'?-1:1;if(sortCol!==c){sortCol=c;sortDir=best;}else if(sortDir===best){sortDir=-best;}else{sortCol=0;sortDir=0;}sortAll();});
if(q)q.addEventListener('input',apply);
if(chips)chips.onclick=function(e){var b=e.target.closest('button');if(!b)return;flt=b.dataset.f;
 [].forEach.call(chips.children,function(x){x.setAttribute('aria-pressed',x===b);});apply();};
var cal=document.getElementById('lk-cal');if(cal&&/^https?:$/.test(location.protocol)){
 var base=location.host+location.pathname.replace(/[^\/]*$/,''),feed='webcal://'+base+'reminders.ics';
 if(/Android/i.test(navigator.userAgent)){
  // Android has no app for webcal links, so subscribe through Google Calendar instead.
  cal.href='https://calendar.google.com/calendar/r?cid='+encodeURIComponent(feed);cal.target='_blank';cal.rel='noopener';
  cal.textContent='Add deadlines to Google Calendar';document.getElementById('lk-and').hidden=false;
 } else cal.href=feed;
 var cp=document.getElementById('lk-copy');
 if(navigator.clipboard){cp.hidden=false;cp.onclick=function(){navigator.clipboard.writeText('https://'+base+'reminders.ics').then(function(){
  cp.textContent='Link copied';setTimeout(function(){cp.textContent='Copy calendar link';},2500);});};}
}
var L=document.getElementById('lk-data');if(!L)return;var dl=JSON.parse(L.textContent),box=document.getElementById('lock');
function tick(){var now=Date.now(),i=0;while(i<dl.length&&Date.parse(dl[i].at)<=now)i++;
 var left=document.getElementById('lk-left');
 if(i>=dl.length){box.className='lock past';left.textContent='Last deadline of this matchup has passed';return;}
 var d=dl[i],ms=Date.parse(d.at)-now,h=Math.floor(ms/36e5),m=Math.floor(ms%36e5/6e4);
 left.textContent='closes in '+(h?h+' h ':'')+m+' min';box.className='lock'+(ms<36e5*2?' soon':'');
 if(i>0&&!box.dataset.moved){box.dataset.moved=1;document.getElementById('lk-time').textContent=d.txt.split(' UK')[0];
  document.getElementById('lk-head').innerHTML='<strong>'+d.label+'\u2019s roster window closes at '+d.txt+'.</strong>';
  document.getElementById('lk-why').textContent=d.why+' then. Make pickups and set your lineup before.';
  var t=document.getElementById('lk-todo');t.innerHTML='';d.moves.forEach(function(x){var s=document.createElement('span');s.textContent=x;t.appendChild(s);});
  var n=document.getElementById('lk-none');if(n)n.hidden=d.moves.length>0;}}
tick();setInterval(tick,30000);
})();"""


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
    n_act = sum(1 for x in data.get("injury_watch") or [] if x.get("bucket") == 0)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Matchup plan: {escape(me)} vs {escape(opp)}</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🏀</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Barlow+Condensed:wght@500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">
<h1>Matchup plan</h1>
<p class="sub">{escape(data["league"]["name"])}, week {data["league"]["week"]}. Updated {now}.</p>
{_lock(plan)}
<nav class="tabs" role="tablist" aria-label="Sections">
<button type="button" role="tab" data-tab="plan" aria-controls="tab-plan">This week</button>
<button type="button" role="tab" data-tab="next" aria-controls="tab-next">Next week</button>
<button type="button" role="tab" data-tab="players" aria-controls="tab-players">Players</button>
<button type="button" role="tab" data-tab="injuries" aria-controls="tab-injuries">Injuries{f'<span class="n">{n_act}</span>' if n_act else ""}</button>
</nav>
<div id="tab-plan" role="tabpanel" aria-label="This week">
<section class="board"><div class="score">
<div class="side you"><span class="team">{escape(me)}</span><span class="big">{res["cats"]:.1f}</span></div>
<div class="mid">categories<br>won</div>
<div class="side opp"><span class="team">{escape(opp)}</span><span class="big">{9 - res["cats"]:.1f}</span></div></div>
<p class="verdict">{verdict}</p>{_now_html(data)}<div class="tug">{_tug(res, _board_now(data))}</div></section>
<div class="plan">
<section class="panel"><h2>Streaming plan</h2>{_stream(plan)}
<details class="more"><summary>Other pickups right now</summary>{_picks(plan)}</details></section>
<div class="stack">
<section class="panel"><h2>Daily lineup</h2>{_days(plan)}</section>
<section class="panel"><h2>Game plan</h2><ul class="notes">{notes}</ul></section></div></div>
{_league(plan)}
<section class="panel"><h2>What if…</h2>{_whatif(plan)}</section>
</div>
<div id="tab-next" role="tabpanel" aria-label="Next week" hidden>
{_nextmatch(plan, data)}
<section class="panel" style="margin-bottom:18px"><h2>Set up next week</h2>{_nextweek(plan, data)}</section>
{_schedule_section(data)}{_teams_section(data)}
</div>
<div id="tab-players" role="tabpanel" aria-label="Players" hidden>{_players_tab(data)}</div>
<div id="tab-injuries" role="tabpanel" aria-label="Injuries" hidden>{_injury_tab(data)}
{f'<section class="panel"><h2>Status and minutes changes</h2><p class="hint">Injury status and minutes trends for both rosters, and free agents whose minutes are rising.</p><div class="scroll"><table class="trend">{trends}</table></div></section>' if trends else ""}
</div>
<p class="foot">Every remaining game is simulated thousands of times from recent averages, with injury status setting each
player’s chance to play and lineups following your league’s position slots. Updated each morning after the night’s games,
and within an hour of any roster move. Always check ESPN for late scratches before games lock.</p>
<script>{PAGE_JS}</script>
</div></body></html>"""


def summary(data, plan):
    res = plan["result"]
    lines = [f"{data['me']['name']} vs {data['opp']['name']}: projected {res['cats']:.1f} to {9 - res['cats']:.1f} "
             f"categories, {round(res['win'] * 100)}% to win."]
    swing = [CATS[i][0] for i in range(9) if 0.2 <= res["catP"][i] < 0.8]
    if swing:
        lines.append("Swing: " + ", ".join(swing))
    dl = plan.get("deadlines") or []
    if dl:
        lines.append(f"{'Today' if dl[0]['today'] else dl[0]['label']}: make moves before {dl[0]['lock_txt']}, "
                     f"when {dl[0]['why'].replace(' tips off', '')} tips off.")
    for x in data.get("injury_watch") or []:
        if x.get("bucket") == 0 and not x.get("mine"):
            lines.append(f"Injury watch: {x['verdict']}: {x['name']}.")
    sc = plan.get("scenario")
    if sc and sc.get("ok"):
        lines.append(f"What-if ({sc['text']}): {round(sc['before']['win'] * 100)}% -> {round(sc['after']['win'] * 100)}% to win")
    elif sc:
        lines.append("What-if couldn't run: " + " ".join(sc["errors"]))
    nm = plan.get("nextmatch")
    if nm:
        lines.append(f"Next week vs {nm['name']}: projected {nm['cats']:.1f} to {9 - nm['cats']:.1f}, "
                     f"{round(nm['win'] * 100)}% to win.")
    nw = plan.get("nextweek") or {}
    nw_lines = [f"{'TODAY ' if nw.get('today') else ''}{nw['day']}, for next week: add {m['add']}"
                + (f", drop {m['drop']}" if m["drop"] else "")
                + (f" after his game (from about {clock(m['free_from'])} UK)" if m.get("free_from") else "")
                for m in nw.get("moves") or []]
    st = plan.get("stream") or {}
    if st.get("moves"):
        lines.append(f"Streaming plan: {round(st['before'] * 100)}% -> {round(st['after'] * 100)}% to win")
        for m in st["moves"]:
            drop = f", drop {m['drop']}" if m["drop"] else ""
            lines.append(f"{'TODAY ' if m['today'] else ''}{m['day']}: add {m['add']}{drop}")
        return "\n".join(lines + nw_lines)
    lines += nw_lines
    if plan["picks"] and plan["picks"][0]["win_delta"] > 0:
        x = plan["picks"][0]
        drop = f", drop {x['drop']}" if x["drop"] else ""
        lines.append(f"Top add: {x['add']}{drop} ({x['win_delta']:+d}% win chance)")
    elif plan["pick_note"]:
        lines.append(plan["pick_note"])
    return "\n".join(lines)
