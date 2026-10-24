"""Roster deadlines, injury-stash advice, and the calendar reminder feed."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .sim import EQUAL, value
from .whatif import _protected, _season_ranks, season_value

ET, UK, UTC = ZoneInfo("America/New_York"), ZoneInfo("Europe/London"), ZoneInfo("UTC")
LONG_TERM = ("season-ending", "out for the season", "rest of the season", "remainder of the season",
             "torn acl", "acl tear", "achilles", "indefinitely")


def _dt(iso):
    if not iso:
        return None
    d = datetime.fromisoformat(iso)
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def clock(iso, tz=UK, with_day=True):
    d = _dt(iso)
    if d is None:
        return ""
    d = d.astimezone(tz)
    t = d.strftime("%-I:%M %p").lower().replace(":00 ", " ")
    return (d.strftime("%a ") + t) if with_day else t


def both(iso):
    """'Sun 12 am UK (7 pm ET Sat)': UK first, because that's where you are."""
    if not iso:
        return ""
    uk, et = _dt(iso).astimezone(UK), _dt(iso).astimezone(ET)
    et_txt = clock(iso, ET, with_day=uk.date() != et.date())
    return f"{clock(iso, UK)} UK ({et_txt} ET)"


def deadlines(data, plan, cfg):
    """For each remaining day: when your first player tips off (the moment that day's lineup and
    any same-day pickup must be set), and the moves planned for that day."""
    days = data["days"]
    me = [p for p in data["me"]["players"] if not p["ir"]]
    moves = (plan.get("stream") or {}).get("moves") or []
    out = []
    for d in range(data["today_index"], len(days)):
        playing = [(p["tips"][d], p["name"]) for p in me
                   if p["games"][d] and p.get("tips") and p["tips"][d] and p["prob"][d] > 0]
        first = min(playing) if playing else (days[d].get("first_tip"), None)
        todo = [m for m in moves if m["day"] == days[d]["label"]]
        lock, why = first[0], (f"{first[1]} tips off" if first[1] else "First NBA game tips off")
        for m in todo:
            if m.get("add_tip") and (lock is None or m["add_tip"] < lock):
                lock, why = m["add_tip"], f"{m['add']} tips off"
        if not lock:
            continue
        texts = [f"Add {m['add']}" + (f", drop {m['drop']}" if m["drop"] else "") for m in todo]
        if d == len(days) - 1:  # last day: the moves that set up next week
            # Moves that wait for a dropped player's game to finish happen after the lock, so they
            # aren't listed against it; the Set up next week panel gives their timing.
            for m in (plan.get("nextweek") or {}).get("moves") or []:
                if not m["drop_after_game"]:
                    texts.append(f"For next week: add {m['add']}" + (f", drop {m['drop']}" if m["drop"] else ""))
        out.append({"date": days[d]["date"], "label": days[d]["label"], "today": d == data["today_index"],
                    "lock": lock, "lock_txt": both(lock), "why": why, "players": len(playing), "moves": texts})
    return out


def _today():
    return datetime.now(ET).date()


def advise(data, cfg, plan):
    """Decide, for each injured player being tracked, whether to add him now, stash later, or wait."""
    watch = data.get("injury_watch") or []
    me = [p for p in data["me"]["players"] if not p["ir"]]
    ranks = _season_ranks(me)
    mine_vals = sorted((season_value(p) for p in me), reverse=True)
    st = plan.get("stream") or {}
    adds_left = st["adds_left_after"] if st.get("moves") else cfg.max_adds - (data.get("adds_used") or 0)
    ir_free = max(0, (data.get("ir_slots") or 0) - (data.get("ir_used") or 0))
    droppable = sorted((p for p in me if not _protected(p, ranks, cfg)), key=season_value)
    drop = droppable[0]["name"] if droppable else None
    today = _today()
    matchup_end = data["days"][-1]["label"] if data["days"] else "the end of this matchup"

    for x in watch:
        v = value(x["s"], EQUAL) if x.get("s") else None
        x["rank"] = (1 + sum(1 for m in mine_vals if m > v)) if v is not None else None
        ret = date.fromisoformat(x["ret"]) if x.get("ret") else None
        x["days_out"] = (ret - today).days if ret else None
        text = " ".join((n["headline"] + " " + n["story"]).lower() for n in x.get("news") or [])
        long_term = any(k in text for k in LONG_TERM)
        rising = (x.get("own_change") or 0) >= 3
        soon_status = x["status"] in ("Day-to-day", "Questionable", "Probable")
        due_soon = x["days_out"] is not None and x["days_out"] <= 14
        claim = x["owner"] == "On waivers"
        why, verdict, tone, bucket, add_by = [], "", "flat", 3, None
        if x["mine"]:
            verdict, tone, bucket = "On your team", "you", 4
            if x["status"] == "Out" and ir_free:
                why.append("He’s listed Out, so he can go in your IR slot. That frees a bench spot for a streamer.")
            if ret:
                why.append(f"ESPN expects him back around {ret.strftime('%a %b %-d')}. Plan to activate him then.")
            elif long_term:
                why.append("Recent news points to a long absence and there’s no return date yet.")
        elif x["owner"] not in ("Free agent", "On waivers"):
            verdict, tone, bucket = f"Owned by {x['owner']}", "flat", 5
            why.append("Not available. If they drop him, he’ll show up here as a free agent with advice on timing.")
        elif x["rank"] is None:
            verdict, bucket = "Watch", 2
            why.append("ESPN has no stats for him yet, so there’s nothing to judge his level by.")
        elif x["rank"] > cfg.roster_size:
            verdict, bucket = "Pass", 3
            why.append(f"Even healthy he’d only be your #{x['rank']} player, so he wouldn’t make your lineup.")
        elif x["games_left"] is not None and x["games_left"] < 8 and ret:
            verdict, bucket = "Pass", 3
            why.append(f"Only {x['games_left']} NBA games left after he’s due back. Not worth a roster spot.")
        else:
            worth = f"Healthy, he’d be your #{x['rank']} player ({x['source']})."
            if soon_status or due_soon or rising:
                verdict, tone, bucket = ("Claim now" if claim else "Add now"), "pos", 0
                if soon_status:
                    why.append(f"He’s {x['status'].lower()}, so he’s close to playing and others will notice.")
                elif due_soon:
                    why.append(f"He’s due back in {x['days_out']} day{'s' if x['days_out'] != 1 else ''}.")
                if rising:
                    why.append(f"Ownership is up {x['own_change']:.0f} points: managers are starting to grab him.")
                why.append(worth)
            elif x["status"] == "Out" and ir_free:
                verdict, tone, bucket = ("Claim now, put on IR" if claim else "Add now, put on IR"), "pos", 0
                why.append("Your IR slot is free, so stashing him costs one add and no roster spot.")
                why.append(worth)
                if adds_left <= 0:
                    why.append("You’re out of adds this matchup, so do it first thing when adds reset.")
            elif ret:
                add_by = ret - timedelta(days=14)
                if add_by <= today:
                    verdict, tone, bucket = ("Claim now" if claim else "Add now"), "pos", 0
                    why.append(f"He’s due back {ret.strftime('%b %-d')}, close enough that waiting risks losing him.")
                else:
                    verdict, tone, bucket = f"Stash by {add_by.strftime('%a %b %-d')}", "warn", 1
                    why.append(f"Due back around {ret.strftime('%a %b %-d')}. Adding him about two weeks early gets "
                               f"ahead of the rush without tying up a bench spot for {x['days_out'] // 7} weeks.")
                why.append(worth)
            else:
                verdict, bucket = "Watch", 2
                why.append(("News points to a long absence" if long_term else "ESPN has no return date yet")
                           + ", so adding him now ties up a roster spot for an unknown stretch. Add him the moment "
                           "he gets a return date, is upgraded, or his ownership starts climbing.")
                why.append(worth)
            if bucket <= 1 and drop and not (verdict.endswith("IR")):
                why.append(f"If you need the spot, {drop} is your weakest player to cut.")
            if claim and bucket <= 1:
                why.append("He’s on waivers, so it’s a claim: the team with the best waiver priority gets him.")
            if bucket == 0 and adds_left > 0 and not verdict.endswith("IR"):
                why.append(f"You have {adds_left} add{'s' if adds_left != 1 else ''} spare after this week’s streaming plan.")
            if bucket == 1 and adds_left > 0:
                why.append(f"A spare add on {matchup_end} (the last day of this matchup) costs you nothing this week.")
        x["verdict"], x["why"], x["tone"], x["bucket"] = verdict, why, tone, bucket
        x["add_by"] = add_by.isoformat() if add_by else None
        x["long_term"] = long_term
    watch.sort(key=lambda x: (x["bucket"], x["rank"] or 99))
    return watch


def ics(deadlines_, page_url=""):
    """A calendar feed with an event at each day's lock time and alerts 60 and 15 minutes before."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Fantasy Planner//Roster deadlines//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:Fantasy roster deadlines",
             "REFRESH-INTERVAL;VALUE=DURATION:PT1H", "X-PUBLISHED-TTL:PT1H"]

    def esc(t):
        return t.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    for d in deadlines_:
        at = _dt(d["lock"]).astimezone(UTC)
        summary = "Fantasy: set lineup" + (f" + {len(d['moves'])} move{'s' if len(d['moves']) != 1 else ''}" if d["moves"] else "")
        desc = (f"{d['why']} at {d['lock_txt']}.\n" + "\n".join(d["moves"])
                + ("\nCheck ESPN for late scratches first." if d["players"] else "") + (f"\n{page_url}" if page_url else ""))
        lines += ["BEGIN:VEVENT", f"UID:lock-{d['date']}@fantasy-planner", f"DTSTAMP:{stamp}",
                  f"DTSTART:{(at - timedelta(minutes=30)).strftime('%Y%m%dT%H%M%SZ')}",
                  f"DTEND:{at.strftime('%Y%m%dT%H%M%SZ')}", f"SUMMARY:{esc(summary)}", f"DESCRIPTION:{esc(desc)}"]
        for mins in (60, 15):
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{esc(summary)}",
                      f"TRIGGER;RELATED=END:-PT{mins}M", "END:VALARM"]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
