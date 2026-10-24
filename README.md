# NBA 9-cat matchup planner (ESPN)

Every day, GitHub runs this planner against your ESPN league and publishes a fresh matchup plan as a web page:

- your chance to win each category and the week, from thousands of simulations
- the best free-agent pickups for **this** matchup, with who to drop
- who to start each day in your 10 active spots
- injuries and players whose minutes are trending up
- a countdown to when today's roster window closes, with the moves to make before then
- moves for the last day of the matchup that use spare adds to set up next week
- a projection of every team's 9-category totals for the week, with your rank in each category and your chance of beating each team
- a **My players** tab with per-game averages (season, last 15, last 7, last season) you can filter and sort, and each player's last 10 games
- an **Injury watch** tab that tracks injured stars (like Jimmy Butler) and tells you when to add them before anyone else

It pulls rosters, stats (blending season and last 7/15 days), schedules, injury status, free agents, stats already earned this week and your adds used, all from ESPN.

## Setup (about 10 minutes, once)

### 1. Put the files on GitHub
1. Sign in at github.com and create a **new public repository** (for example `matchup-planner`).
2. On the repo page, choose **Add file → Upload files** and drag in everything from this folder.
3. Check that `.github/workflows/daily.yml` uploaded. On a Mac, Finder hides folders that start with a dot. If it's missing, choose **Add file → Create new file**, type `.github/workflows/daily.yml` as the name, and paste in the file's contents.

### 2. Find your league and team IDs
Open your team on the ESPN fantasy website. The address looks like
`https://fantasy.espn.com/basketball/team?leagueId=123456&teamId=3`. Note both numbers.

### 3. Private leagues only: copy two ESPN cookies
Most leagues are private, so ESPN needs proof you're a member.
1. On a computer, sign in to ESPN fantasy in Chrome.
2. Open DevTools (F12) → **Application** → **Cookies** → `https://fantasy.espn.com`.
3. Copy the values of `espn_s2` and `SWID` (keep SWID's curly braces).

Treat these like a password. Only put them in GitHub secrets, never in a file in the repo.

### 4. Add your secrets
In the repo: **Settings → Secrets and variables → Actions → New repository secret**. Add:

| Name | Value |
|---|---|
| `LEAGUE_ID` | your league ID |
| `TEAM_ID` | your team ID |
| `ESPN_S2` | the espn_s2 cookie (private leagues) |
| `SWID` | the SWID cookie (private leagues) |
| `DISCORD_WEBHOOK_URL` | optional: posts a summary to a Discord channel each run |

### 5. Turn on the web page
**Settings → Pages → Build and deployment → Source: GitHub Actions.**

### 6. Run it
**Actions** tab → **Daily matchup plan** → **Run workflow**. When it finishes (about a minute), your plan is at
`https://YOUR-USERNAME.github.io/REPO-NAME/`. Bookmark it on your phone.

After that it updates on its own:

| When (UK time, winter) | Why |
|---|---|
| about 8:15 am | Main plan, after every game from the night before is final |
| about 10:15 am | Backup, in case GitHub or ESPN was slow |
| about 9:45 pm | Refresh for the day's injury reports, before the usual midnight UK tip-off |
| hourly, 9:30 am to 11:30 pm | Roster check: rebuilds the plan only if you've added, dropped or moved someone to IR |

The roster check means that after you make a move in ESPN, the plan catches up within about an hour without you doing anything. Each check is a single small ESPN request; when nothing has changed it stops there, so the Actions tab will show many short runs where the build step is skipped. That's normal. If a check rebuilds the plan, the Discord summary starts with "Roster change spotted".

Add an hour to each in UK summer time. You can also press **Run workflow** any time, for example right after big injury news (the GitHub mobile app works for this). To change the times, edit the `cron` lines at the top of `.github/workflows/daily.yml` (they're in UTC).

## Roster deadline reminders
The top of the page shows when today's roster window closes, which is when your first player (or the player you're picking up) tips off, with a live countdown and the moves to make before then. Times are shown in UK time first, then Eastern.

Two ways to get reminded without opening the page:
- **Calendar:** the page publishes a calendar feed with an event at each day's deadline, listing that day's moves, and alerts 60 and 15 minutes before. Subscribe once and it keeps updating.
  - **iPhone or Mac:** tap **Add deadlines to your calendar** on the page and choose **Subscribe**. To make it refresh quickly, go to Settings → Calendar → Accounts → Fetch New Data and pick every 15 minutes.
  - **Android:** the link reads **Add deadlines to Google Calendar** and opens Google Calendar's Add calendar screen; tap **Add**. If that doesn't open, on a computer go to Google Calendar, click **+** next to **Other calendars**, choose **From URL**, and paste the address from **Copy calendar link** (`https://YOUR-USERNAME.github.io/REPO-NAME/reminders.ics`). To see it on your phone, open the Google Calendar app's Settings, tap the new calendar and turn on **Sync**. Google only refreshes subscribed calendars every several hours, so the Discord reminder is more reliable on Android.

  Calendar apps refresh on their own schedule, so treat the page as the source of truth if a plan changes late.
- **Discord:** if you've set `DISCORD_WEBHOOK_URL`, the **Roster deadline reminder** workflow posts about an hour before each deadline with the moves to make. It reads the published page only, so it doesn't use any ESPN requests.

## Set up next week
Adds reset when a new matchup starts, so any you still have on the last day are free. The **Set up next week** panel (under the streaming plan) uses them: it finds the free agents who add the most starter games to next week's lineup, counting only games on days you'd have room to start them, weighted by how good they are. It suggests who to drop: streamers from this week first, and a regular only for someone at least as good over the season. If the player to drop still has a game on the last day, it tells you to wait until that game ends. These moves also show in the deadline banner and Discord on the last day.

Next week is assumed to be the Monday to Sunday after this matchup. For a longer one, like the All-Star break, set `NEXT_MATCHUP_END`.

## Your week across the league
Under the streaming plan, a table projects every team's final 9-category totals for this matchup week: what each team has already earned, plus the rest of the week simulated from its current roster. It shows your rank in each category (green near the top, red near the bottom), a second row for your totals if you follow the streaming plan, and your chance of beating each team if you played them. Other teams are shown without any pickups, so they may finish a little higher than projected.

## Injury watch
Lists injured players worth tracking: anyone on your `WATCH_PLAYERS` list (Jimmy Butler by default), injured free agents who'd be good enough to start for you, and your own injured players. For each one it shows ESPN's status and return estimate, how many games his team has left after that, how good he was when healthy (last season's numbers if he's barely played this season), his ownership trend, and the latest ESPN news.

It then gives a verdict:
- **Add now** (or **Claim now** if he's on waivers): he's about to return, has been upgraded, or other managers have started adding him. Also used when your IR slot is free, since stashing him there costs only an add.
- **Stash by** a date: about two weeks before his expected return, so you get ahead of the rush without wasting a bench spot for weeks.
- **Watch**: no return date yet. Add him the moment that changes.
- **Pass**: even healthy he wouldn't make your lineup, or he'd come back with too few games left.

To change who's tracked, set the `WATCH_PLAYERS` variable (below), for example `Jimmy Butler, Ja Morant`.

## What-if scenarios
The page has a **What if…** section. Pick a start day (today or any later day in the matchup), a free agent and who you'd drop, and it shows how your chance to win the week and each category would change. Every combination is simulated when the page is built, so it answers instantly. Early in the week this adds up to about a minute to each run.

For players who aren't in that list, like a trade target or someone on your opponent's team, go to **Actions → Daily matchup plan → Run workflow** and type a scenario in the box:

```
add: Jalen Brunson; drop: Grant Sato
add: Naz Reid, Josh Hart; drop: Grant Sato, Luca Varga; day: Thu
```

Names can be partial if they're unique ("brunson"). If you add a player from your opponent's roster, it's treated as a trade: they lose him and get the players you drop. The result appears at the top of the What if section and in the Discord message. The next scheduled run clears it; to keep a scenario on the page, set it as the `WHAT_IF` variable instead.

## Optional settings
Add these under **Settings → Secrets and variables → Actions → Variables** only if the defaults don't fit.

| Variable | Default | What it does |
|---|---|---|
| `ACTIVE_SLOTS` | 10 | Active lineup spots per day |
| `ROSTER_SIZE` | 13 | Active plus bench spots (IR not included) |
| `MAX_ADDS` | 6 | Adds allowed per matchup |
| `ADD_DELAY_DAYS` | 0 | 1 if pickups can't play until the next day |
| `KEEP_PLAYERS` | none | Comma-separated names never suggested as drops |
| `MATCHUP_END` | this Sunday | Last day of a longer matchup, like `2026-11-01` for an opening week or the All-Star break |
| `YEAR` | automatic | ESPN season year (2026-27 is 2027) |
| `WHAT_IF` | none | A scenario to show on every run, like `add: Jalen Brunson; drop: Grant Sato` |
| `WHATIF_SIMS` | 600 | Simulations per add/drop pair in the What if picker. Lower it if runs get slow |
| `NEXT_MATCHUP_END` | the Sunday after | Last day of next week's matchup, if it's longer than a week |
| `WATCH_PLAYERS` | Jimmy Butler | Comma-separated injured players to track on the Injury watch tab |

## Good to know
- **The page is public.** Anyone with the address can see your rosters and plan. Your ESPN cookies stay private in GitHub secrets.
- **ESPN cookies expire** every so often. If a run fails with "ESPN refused access", copy fresh ones into the secrets.
- **The ESPN data feed is unofficial.** If ESPN changes it, runs may fail until the `espn-api` library is updated.
- **Inactive repos pause.** GitHub pauses scheduled runs in a repo with no activity for 60 days and emails you first. Click the button in that email, or make any small edit, to keep it going all season.
- **Scheduled runs can start late** when GitHub is busy. Check the "Updated" time on the page, and always check ESPN for late scratches before games lock.
- **Positions are ignored.** The plan assumes any healthy player can fill an active spot.

## Try it without ESPN
```
pip install -r requirements.txt
python -m planner.main --demo
```
This writes `site/index.html`, `site/plan.json` and `site/reminders.ics` using a fictional matchup.
