"""Post to Discord the moment an injured player you're tracking changes on ESPN.

Runs on its own schedule (every 30 minutes by default) and compares each player with what it saw
on the previous run. It alerts when:
  - his injury status changes (Out -> Day-to-day -> Healthy, or worse)
  - ESPN gives or moves a return date
  - ESPN posts a new news blurb about him
  - someone in your league picks him up, drops him, or he goes on waivers
  - his ownership across ESPN leagues jumps (other managers are starting to stash him)

Who it tracks: your WATCH_PLAYERS, plus everyone on the Injury Watch tab of your published plan
(your own injured players and the injured free agents worth stashing). A player stays tracked
until he's healthy, so you still hear when someone drops off the tab because he came back.

Its memory of the last run lives in STATE_FILE, which the workflow keeps between runs.

    python -m planner.watchalert            # needs the ESPN secrets and DISCORD_WEBHOOK_URL
    python -m planner.watchalert --dry-run  # print instead of posting
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

from . import cards
from .config import Config

STATE_FILE = Path(os.environ.get("WATCH_STATE", ".watch-state/watch.json"))
OWN_JUMP = 5.0  # alert when ESPN-wide ownership rises this many points since the last alert
DISCORD_LIMIT = 1900

# Higher is healthier. Used to say whether a status change is good or bad news.
RANK = {"Out": 0, "Suspended": 0, "Injured": 0, "Doubtful": 1, "Questionable": 2,
        "Day-to-day": 3, "Probable": 4, "Healthy": 5}


# ---------- reading ESPN ----------

def _plan_names(page):
    """Names on the published Injury Watch tab, or [] if the page can't be read."""
    if not page:
        return []
    try:
        req = urllib.request.Request(page.rstrip("/") + "/plan.json", headers={"User-Agent": "fantasy-planner"})
        with urllib.request.urlopen(req, timeout=20) as r:
            plan = json.load(r)
    except Exception as exc:
        print(f"Couldn't read the published plan, so only WATCH_PLAYERS are tracked ({exc})")
        return []
    return [x["name"] for x in plan.get("injury_watch") or [] if x.get("name")]


def _resolve(lg, queries):
    """Player ids for names (partial is fine if unique), plus the names that matched nobody."""
    from .whatif import match
    names = [k for k in (getattr(lg, "player_map", {}) or {}) if isinstance(k, str)]
    ids, missing = [], []
    for q in queries:
        hits = match(q, names)
        if hits:
            ids.append(lg.player_map[names[hits[0]]])
        else:
            missing.append(q)
    return ids, missing


def snapshot(lg, cfg, ids):
    """Current ESPN view of each player id: status, return date, owner, ownership and latest news."""
    owners = {t.team_id: t.team_name for t in lg.teams}
    raw = cards.fetch(lg, ids)
    out = {}
    for pid in ids:
        e = raw.get(pid)
        if not e:
            continue
        pl = e.get("player") or {}
        p = cards.parse(e, lg.year)
        if p["injury"] in (None, "ACTIVE", "NORMAL"):
            status = "Healthy"
        else:
            status = cards.STATUS_LABEL.get(p["injury"], "Injured" if p["injured"] else "Healthy")
        on = p["on_team"]
        if on == cfg.team_id:
            owner = "Your team"
        elif on and on in owners:
            owner = owners[on]
        else:
            owner = "On waivers" if p["status"] == "WAIVERS" else "Free agent"
        latest = (cards.news(lg, pid, limit=1) or [None])[0]
        out[str(pid)] = {
            "name": pl.get("fullName") or lg.player_map.get(pid, str(pid)),
            "status": status, "ret": p["ret"], "owner": owner, "own": p["own"],
            "news": latest["headline"] if latest else None,
            "story": latest["story"] if latest else None,
        }
    return out


# ---------- deciding what to say ----------

def changes(old, new):
    """Alert lines for one player, comparing the last run (old) with now (new)."""
    lines = []
    name = new["name"]
    if old["status"] != new["status"]:
        a, b = RANK.get(old["status"], 0), RANK.get(new["status"], 0)
        icon = "🟢" if new["status"] == "Healthy" else ("🟡" if b > a else "🔴")
        lines.append(f"{icon} **{name}**: {old['status']} → {new['status']}")
    if new["ret"] and new["ret"] != old["ret"]:
        if old["ret"]:
            word = "moved up" if new["ret"] < old["ret"] else "pushed back"
            lines.append(f"📅 **{name}**: ESPN return date {word}, {old['ret']} → {new['ret']}")
        else:
            lines.append(f"📅 **{name}**: ESPN now expects him back {new['ret']}")
    if new["news"] and new["news"] != old.get("news"):
        story = f" {new['story']}" if new.get("story") else ""
        lines.append(f"📰 **{name}**: {new['news']}.{story}")
    if old["owner"] != new["owner"]:
        if new["owner"] == "Your team":
            pass  # you made the move; no need to tell you
        elif new["owner"] == "Free agent":
            lines.append(f"🔓 **{name}** was dropped by {old['owner']} and is a free agent again")
        elif new["owner"] == "On waivers":
            lines.append(f"⏳ **{name}** is on waivers (dropped by {old['owner']})")
        else:
            lines.append(f"🚨 **{new['owner']}** picked up **{name}**")
    base = old.get("own_base", old.get("own"))
    if new["own"] is not None and base is not None and new["own"] - base >= OWN_JUMP:
        lines.append(f"📈 **{name}**: now rostered in {new['own']:.0f}% of ESPN leagues, "
                     f"up {new['own'] - base:.0f} points. Other managers are moving.")
    return lines


def advice(old, new):
    """One line on what to do, when a change makes it worth acting."""
    better = (RANK.get(new["status"], 0) > RANK.get(old["status"], 0)
              or (new["ret"] and new["ret"] != old["ret"] and (not old["ret"] or new["ret"] < old["ret"])))
    base = old.get("own_base", old.get("own"))
    rising = new["own"] is not None and base is not None and new["own"] - base >= OWN_JUMP
    if new["owner"] in ("Free agent", "On waivers") and (better or rising or old["owner"] != new["owner"]):
        verb = "Claim" if new["owner"] == "On waivers" else "Add"
        where = " and put him on IR" if new["status"] in ("Out", "Injured") else ""
        return f"→ {verb} him now{where} before someone else does."
    if new["owner"] == "Your team" and new["status"] == "Healthy" and old["status"] != "Healthy":
        return "→ He's yours: move him off IR into your lineup (you'll need a free bench spot)."
    return None


def build_message(old_state, new_state, first_run, missing):
    if first_run:
        rows = [f"• {p['name']}: {p['status']}, {p['owner']}" for p in new_state.values()]
        text = "👀 Injury alerts are on. Watching:\n" + "\n".join(rows or ["• nobody yet"])
        if missing:
            text += f"\nCouldn't find: {', '.join(missing)}. Check the spelling in WATCH_PLAYERS."
        return text
    blocks = []
    for pid, new in new_state.items():
        old = old_state.get(pid)
        if not old:
            continue  # newly tracked: record him quietly, alert on his next change
        lines = changes(old, new)
        if lines:
            tip = advice(old, new)
            blocks.append("\n".join(lines + ([tip] if tip else [])))
    return "\n\n".join(blocks)


def carry_forward(old_state, new_state):
    """Keep the ownership baseline unless we just alerted on a jump."""
    for pid, new in new_state.items():
        old = old_state.get(pid) or {}
        base = old.get("own_base", old.get("own"))
        if new["own"] is None or base is None or new["own"] - base >= OWN_JUMP:
            new["own_base"] = new["own"]
        else:
            new["own_base"] = base
    return new_state


# ---------- sending ----------

def post(hook, text):
    """Send to Discord in chunks under its 2,000-character limit, splitting between players."""
    chunks, cur = [], ""
    for block in text.split("\n\n"):
        block = block[:DISCORD_LIMIT]
        if cur and len(cur) + len(block) + 2 > DISCORD_LIMIT:
            chunks.append(cur)
            cur = block
        else:
            cur = f"{cur}\n\n{block}" if cur else block
    if cur:
        chunks.append(cur)
    for c in chunks:
        req = urllib.request.Request(hook, data=json.dumps({"content": c}).encode(),
                                     headers={"Content-Type": "application/json", "User-Agent": "fantasy-planner"})
        urllib.request.urlopen(req, timeout=15)


def main():
    dry = "--dry-run" in sys.argv
    cfg = Config.from_env()
    hook = cfg.discord_webhook
    if not hook and not dry:
        print("DISCORD_WEBHOOK_URL isn't set, so there's nowhere to send alerts.")
        return
    old_state = {}
    if STATE_FILE.exists():
        try:
            old_state = json.loads(STATE_FILE.read_text())
        except ValueError:
            print("Saved state was unreadable; starting fresh.")
    first_run = not old_state

    from .espn_source import _connect
    try:
        lg = _connect(cfg)
    except SystemExit as exc:
        print(exc)
        return  # keep the old state; the next run tries again
    queries = list(dict.fromkeys(list(cfg.watch_players) + _plan_names(os.environ.get("PAGE_URL", ""))))
    ids, missing = _resolve(lg, queries)
    # Keep following anyone we were tracking who isn't healthy yet, even if he left the lists.
    ids += [int(pid) for pid, p in old_state.items() if p.get("status") != "Healthy" and int(pid) not in ids]
    new_state = snapshot(lg, cfg, ids)
    if not new_state:
        print("ESPN returned no player cards; keeping the old state.")
        return

    text = build_message(old_state, new_state, first_run, missing)
    page = os.environ.get("PAGE_URL", "").strip()
    if text and page and not first_run:
        text += "\n\n" + page.rstrip("/") + "/#injuries"
    print(text or f"No changes for {len(new_state)} tracked players.")
    if text and not dry:
        try:
            post(hook, text)
        except Exception as exc:
            print(f"Couldn't post to Discord ({exc}); will retry these changes next run.")
            return  # don't save, so the same changes are sent next time
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(carry_forward(old_state, new_state), indent=1))


if __name__ == "__main__":
    main()
