"""Does the published plan need rebuilding?

Two reasons to rebuild, both checked with one small ESPN request:
- your roster, or this week's opponent's, changed since the page was built (an add, drop or IR move);
- a new fantasy day has started since the page was built, and no full update has run for it yet.
  That covers a scheduled run GitHub started late or skipped, which happens when it's busy.

Prints the answer and, inside GitHub Actions, sets the step outputs `changed` (true/false) and
`reason` (roster-change or new-day). Uses only Python's standard library, so it runs in a few seconds.

    python -m planner.check
"""
import json
import os
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import Config

ENDPOINT = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{year}/segments/0/leagues/{league}"
IR_SLOT = 13
ET = ZoneInfo("America/New_York")
# A fantasy day counts as over once its late West Coast games (and overtime) are final.
DAY_ENDS_HOUR_ET = 3


def fantasy_day(now=None):
    """Today's fantasy day as an ISO date: the Eastern date, rolled back until 3 am ET."""
    now = (now or datetime.now(ET)).astimezone(ET)
    return (now - timedelta(hours=DAY_ENDS_HOUR_ET)).date().isoformat()


def fingerprint(entries):
    """(player id, on IR?) pairs -> a stable string. The same function is used when the page is built."""
    return ",".join(f"{pid}{'i' if ir else ''}" for pid, ir in sorted(entries))


def _get(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "fantasy-planner", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def espn_state(cfg):
    """(roster fingerprint, ESPN's current scoring period) from one request."""
    cookies = []
    if cfg.espn_s2:
        cookies.append(f"espn_s2={cfg.espn_s2}")
    if cfg.swid:
        cookies.append(f"SWID={cfg.swid}")
    url = ENDPOINT.format(year=cfg.year, league=cfg.league_id) + "?view=mRoster&view=mMatchup&view=mStatus"
    data = _get(url, {"Cookie": "; ".join(cookies)} if cookies else None)
    rosters = {t.get("id"): (t.get("roster") or {}).get("entries") or [] for t in data.get("teams", [])}
    if cfg.team_id not in rosters:
        raise LookupError(f"Team {cfg.team_id} not found in league {cfg.league_id}")
    opp_id = _opponent(data, cfg.team_id)

    def fp(tid):
        return fingerprint((e.get("playerId"), e.get("lineupSlotId") == IR_SLOT) for e in rosters.get(tid, []))
    return combined(fp(cfg.team_id), fp(opp_id) if opp_id in rosters else None), data.get("scoringPeriodId")


def espn_fingerprint(cfg):
    return espn_state(cfg)[0]


def combined(mine, opp):
    """Your roster plus this week's opponent's, so a move by either side triggers a rebuild."""
    return mine if opp is None else f"{mine}|{opp}"


def _opponent(data, team_id):
    """This matchup period's opponent from ESPN's schedule, or None if it can't be read."""
    period = (data.get("status") or {}).get("currentMatchupPeriod")
    for m in data.get("schedule") or []:
        if m.get("matchupPeriodId") != period:
            continue
        h, a = (m.get("home") or {}).get("teamId"), (m.get("away") or {}).get("teamId")
        if team_id in (h, a):
            return a if h == team_id else h
    return None


def decide(published, current, espn_sp, today):
    """(rebuild?, reason code, explanation) from the published plan.json, ESPN's roster and the day."""
    if current is None:
        return False, "", ""
    if not published:
        return True, "roster-change", "the published plan has no roster record yet"
    if published.get("roster_fp") != current:
        return True, "roster-change", "your roster or your opponent's changed since the last update"
    day, sp = published.get("day"), published.get("espn_sp")
    if not day:
        return True, "new-day", "the published plan doesn't say which day it's for (built by an older version)"
    if day < today:
        return True, "new-day", f"the plan is for {day} but it's now {today}"
    if sp is not None and espn_sp is not None and espn_sp > sp and day <= today:
        # ESPN has moved to the next scoring period since the plan was built: the night's games are final.
        return True, "new-day", f"ESPN moved on to a new scoring period ({sp} -> {espn_sp})"
    return False, "", "no roster change on either side and the plan is for today"


def main():
    cfg = Config.from_env()
    page = os.environ.get("PAGE_URL", "").rstrip("/")
    published, why = None, ""
    try:
        published = _get(page + "/plan.json?t=" + str(int(datetime.now().timestamp())))
    except Exception as exc:
        why = f"couldn't read the published plan ({exc})"
    try:
        current, espn_sp = espn_state(cfg)
    except Exception as exc:  # if ESPN is unreachable, don't rebuild; the next scheduled run will catch up
        current, espn_sp, why = None, None, f"couldn't read your roster from ESPN ({exc})"
    changed, reason, text = decide(published if not why else None, current, espn_sp, fantasy_day())
    if why and current is not None and published is None and "published plan" in why:
        changed, reason, text = False, "", why  # page unreachable: let the scheduled runs handle it
    print(f"Rebuild: {'yes' if changed else 'no'} ({text or why})")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")
            f.write(f"reason={reason}\n")


if __name__ == "__main__":
    main()
