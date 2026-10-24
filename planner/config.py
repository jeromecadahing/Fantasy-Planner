"""Settings, read from environment variables (GitHub secrets and variables)."""
import os
from dataclasses import dataclass, field
from datetime import date


def _env(name, default=""):
    value = os.environ.get(name, "")
    return value.strip() if value and value.strip() else default


def _int(name, default):
    try:
        return int(_env(name, str(default)))
    except ValueError:
        raise SystemExit(f"{name} must be a whole number, got {os.environ.get(name)!r}")


def _season_year():
    # ESPN names a season by the year it ends: 2026-27 is 2027.
    today = date.today()
    return today.year + 1 if today.month >= 8 else today.year


@dataclass
class Config:
    league_id: int = 0
    team_id: int = 0
    year: int = field(default_factory=_season_year)
    espn_s2: str = ""
    swid: str = ""
    active_slots: int = 10
    lineup_slots: tuple = ()
    roster_size: int = 13
    max_adds: int = 6
    add_delay_days: int = 0
    keep_players: tuple = ()
    matchup_end: str = ""
    fa_pool: int = 60
    discord_webhook: str = ""
    reserve_adds: int = 1
    plan_sims: int = 1200
    sims: int = 4000
    pickup_sims: int = 2500
    what_if: str = ""
    whatif_sims: int = 600
    watch_players: tuple = ()
    next_matchup_end: str = ""

    @classmethod
    def from_env(cls):
        keep = tuple(n.strip().lower() for n in _env("KEEP_PLAYERS").split(",") if n.strip())
        return cls(
            league_id=_int("LEAGUE_ID", 0),
            team_id=_int("TEAM_ID", 0),
            year=_int("YEAR", _season_year()),
            espn_s2=_env("ESPN_S2"),
            swid=_env("SWID"),
            active_slots=_int("ACTIVE_SLOTS", 10),
            lineup_slots=tuple(x.strip().upper() for x in _env("LINEUP_SLOTS").split(",") if x.strip()),
            roster_size=_int("ROSTER_SIZE", 13),
            max_adds=_int("MAX_ADDS", 6),
            add_delay_days=_int("ADD_DELAY_DAYS", 0),
            keep_players=keep,
            matchup_end=_env("MATCHUP_END"),
            fa_pool=_int("FA_POOL", 60),
            discord_webhook=_env("DISCORD_WEBHOOK_URL"),
            reserve_adds=_int("RESERVE_ADDS", 1),
            plan_sims=_int("PLAN_SIMS", 1200),
            sims=_int("SIMS", 4000),
            pickup_sims=_int("PICKUP_SIMS", 2500),
            what_if=_env("WHAT_IF"),
            whatif_sims=_int("WHATIF_SIMS", 600),
            next_matchup_end=_env("NEXT_MATCHUP_END"),
            watch_players=tuple(n.strip() for n in _env("WATCH_PLAYERS").split(",") if n.strip()),
        )
