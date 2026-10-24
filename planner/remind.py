"""Post a Discord reminder shortly before the roster window closes.

Runs on its own hourly schedule and only reads the published plan.json, so it makes no ESPN requests
and needs nothing beyond Python's standard library. It posts once per deadline: each run covers the
window from 15 to 75 minutes ahead, and consecutive hourly runs don't overlap.

    python -m planner.remind            # uses PAGE_URL and DISCORD_WEBHOOK_URL
    python -m planner.remind --dry-run  # print instead of posting
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

AHEAD_MIN, AHEAD_MAX = 15, 75


def due(deadlines, now):
    lo, hi = now + timedelta(minutes=AHEAD_MIN), now + timedelta(minutes=AHEAD_MAX)
    return [d for d in deadlines if lo <= datetime.fromisoformat(d["lock"]) < hi]


def message(d, now, page):
    mins = round((datetime.fromisoformat(d["lock"]) - now).total_seconds() / 60)
    lines = [f"⏰ Roster window closes in about {mins} minutes, at {d['lock_txt']}. {d['why']}."]
    if d["moves"]:
        lines.append("Before then:")
        lines += [f"• {m}" for m in d["moves"]]
    else:
        lines.append("No pickups planned. Just check your lineup and late scratches.")
    if page:
        lines.append(page)
    return "\n".join(lines)


def main():
    page = os.environ.get("PAGE_URL", "").strip()
    hook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    dry = "--dry-run" in sys.argv
    if not hook and not dry:
        print("DISCORD_WEBHOOK_URL isn't set, so there's nowhere to send reminders.")
        return
    url = page.rstrip("/") + "/plan.json"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            plan = json.load(r)
    except Exception as exc:
        print(f"Couldn't read {url}: {exc}")
        return
    now = datetime.now(timezone.utc)
    for d in due(plan.get("deadlines") or [], now):
        text = message(d, now, page)
        print(text)
        if not dry:
            req = urllib.request.Request(hook, data=json.dumps({"content": text}).encode(),
                                         headers={"Content-Type": "application/json", "User-Agent": "fantasy-planner"})
            urllib.request.urlopen(req, timeout=15)


if __name__ == "__main__":
    main()
