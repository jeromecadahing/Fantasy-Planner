# NBA 9-cat matchup planner (ESPN)

Every day, GitHub runs this planner against your ESPN league and publishes a fresh matchup plan as a web page:

- your chance to win each category and the week, from thousands of simulations
- the best free-agent pickups for **this** matchup, with who to drop
- who to start each day in your 10 active spots
- injuries and players whose minutes are trending up

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

After that it updates on its own around 11 am and 6 pm Eastern. You can also press **Run workflow** any time, for example right after big injury news (the GitHub mobile app works for this).

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
This writes `site/index.html` using a fictional matchup.
