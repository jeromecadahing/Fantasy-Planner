"""Has your ESPN roster, or this week's opponent's, changed since the page was last built?

One small ESPN request (your league's rosters) compared with the fingerprint saved in the
published plan.json. Prints the answer and, inside GitHub Actions, sets the step output
`changed` so the workflow only rebuilds the plan when you've actually added, dropped or moved
someone to IR. Uses only Python's standard library, so it runs in a few seconds.

    python -m planner.check
"""
import json
import os
import urllib.request

from .config import Config

ENDPOINT = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{year}/segments/0/leagues/{league}"
IR_SLOT = 13


def fingerprint(entries):
    """(player id, on IR?) pairs -> a stable string. The same function is used when the page is built."""
    return ",".join(f"{pid}{'i' if ir else ''}" for pid, ir in sorted(entries))


def _get(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "fantasy-planner", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def espn_fingerprint(cfg):
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
    return combined(fp(cfg.team_id), fp(opp_id) if opp_id in rosters else None)


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


def main():
    cfg = Config.from_env()
    page = os.environ.get("PAGE_URL", "").rstrip("/")
    changed, why = False, ""
    try:
        published = _get(page + "/plan.json").get("roster_fp")
    except Exception as exc:
        published, why = None, f"couldn't read the published plan ({exc})"
    try:
        current = espn_fingerprint(cfg)
    except Exception as exc:  # if ESPN is unreachable, don't rebuild; the next scheduled run will catch up
        current, why = None, f"couldn't read your roster from ESPN ({exc})"
    if current and published is None and not why:
        changed, why = True, "the published plan has no roster record yet"
    elif current and published and current != published:
        changed, why = True, "your roster or your opponent's changed since the last update"
    elif current and published:
        why = "no roster change on either side since the last update"
    print(f"Rebuild: {'yes' if changed else 'no'} ({why})")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")


if __name__ == "__main__":
    main()
