"""Run the planner: python -m planner.main [--demo] [--out site]"""
import argparse
import json
import os
import sys

import requests

from . import demo, extras, report, sim
from .config import Config


def main():
    ap = argparse.ArgumentParser(description="9-cat matchup planner for ESPN fantasy basketball")
    ap.add_argument("--demo", action="store_true", help="use fictional demo data instead of ESPN")
    ap.add_argument("--out", default="site", help="folder to write index.html into")
    args = ap.parse_args()

    cfg = Config.from_env()
    if args.demo:
        data = demo.load()
    else:
        from . import espn_source
        data = espn_source.load(cfg)

    plan = sim.build_plan(data, cfg)
    plan["deadlines"] = extras.deadlines(data, plan, cfg)
    extras.advise(data, cfg, plan)
    page = os.environ.get("PAGE_URL", "")
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "reminders.ics"), "w", encoding="utf-8", newline="") as f:
        f.write(extras.ics(plan["deadlines"], page))
    with open(os.path.join(args.out, "index.html"), "w", encoding="utf-8") as f:
        f.write(report.render(data, plan))
    with open(os.path.join(args.out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump({"result": plan["result"], "picks": plan["picks"], "notes": plan["notes"],
                   "scenario": plan.get("scenario"), "deadlines": plan["deadlines"],
                   "injury_watch": [{k: x.get(k) for k in ("name", "team", "status", "owner", "ret", "verdict", "why")}
                                    for x in data.get("injury_watch") or []]}, f, indent=1)

    text = report.summary(data, plan)
    print(text)
    if cfg.discord_webhook:
        try:
            requests.post(cfg.discord_webhook, json={"content": text + (f"\n{page}" if page else "")}, timeout=15)
        except requests.RequestException as exc:
            print(f"Discord message failed: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
