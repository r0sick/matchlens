# MatchLens – synthetic football data generator (stage 0)

Football-realistic, fully synthetic match events for the hackathon pipeline
(ingest → interpret → explain → render → personalise). No real league data; clubs,
players and referees are invented.

## Quick start (Python 3.10+, standard library only)

```bash
python -m matchsim league  --out data                                  # 10 clubs, 230 players -> data/league.json
python -m matchsim match   --home THR --away KMU --seed 42 --out data/matches --csv
python -m matchsim season  --out data/season_2026-27                   # 18 matchdays, 90 matches (~25 s)
python -m matchsim replay  data/matches/M000042 --speed 30             # live ticker, 1 match minute = 2 s
python -m matchsim replay  data/matches/M000042 --speed 60 --format jsonl   # raw live feed on stdout
python tools/validate.py -n 200                                        # realism check
```

## Stage 1 – live match intelligence (`matchlens/`)

```bash
python -m matchlens data/matches/M000042 --speed 60           # live dashboard: stats, win probability, alerts
python -m matchlens data/matches/M000042 --speed 600 --alerts-only --no-minor
python tools/match_report.py data/matches/M000042 --out report.png   # chart vs hidden ground truth
python tools/train_models.py --matches 3000                   # retrain models (needs numpy + scikit-learn)
```

- `matchlens/state.py` – `MatchState.update(event)` keeps live team/player stats, possession (total and last 5 min), field tilt, PPDA, momentum index, chaos index, live player ratings, and emits alerts (goal, win-probability swing, sprint ≥ 33 km/h, shot ≥ 105 km/h, hard pass completed, 45 m+ pass, big chance missed, 10 km covered, cards, subs). Uses only events seen so far.
- `matchlens/models.py` – pass difficulty (0–100 with reasons), win/draw/loss probability, next-goal probability and chaos index. All exported as JSON coefficients in `matchlens/model_files/`, so the live app needs no ML libraries and every number can be explained term by term.
- `model_files/training_report.json` – held-out evaluation: log loss vs naive prior, calibration tables, and correlation of the momentum and chaos indices with the simulation's hidden ground truth.

## Stage 2 – live server (`matchlens/server.py`)

```bash
pip install -r requirements.txt               # fastapi, uvicorn, Agent Framework, MCP
uvicorn matchlens.server:app --reload         # then open http://localhost:8000
python -m pytest -q                           # end-to-end tests (pip install -r requirements-dev.txt)
```

The server replays any demo or season match through the live engine and streams timed, machine-readable
messages over a WebSocket (`/ws/{match_id}?speed=60`): `hello`, `state`, `event`, `alert`,
`win_prob_swing`, `minute`, `players`, `session`. Several screens can watch the same match. Pause, resume,
speed and restart work over the socket or REST. The full message spec is in `OVERLAY.md`; the page at `/`
is a test client showing the scoreboard, win probability, stats and alert feed.

## Stage 3 – the app (`http://localhost:8000`)

One stream, three ways to watch it (switch at the top right):

- **Broadcast** – a live 2D "event cam" of the pitch with broadcast graphics: score bug, win-probability strip,
  momentum ribbon, player name tags with speed and pass-difficulty indicators, and lower thirds for goals, cards,
  substitutions, rocket shots, top speeds and win-probability swings.
  Add `?view=overlay` for the graphics alone on a transparent background, ready to layer over video in OBS or vMix.
- **Analyst** – win probability, xG race, momentum and chaos charts, shot map, pass map coloured by difficulty,
  team stats and a sortable player table with live ratings.
- **Fan** – the score, a plain-language headline of who is on top and why, a win-probability tug of war,
  the story of the match with "why it matters" context, and a card for the player you follow.

**Preferences** (saved in the browser): language (English, Spanish), favourite club, player to follow. The
followed player gets a ★ on the pitch tags, in the feeds and timeline, and their own stats card.
Links can carry settings: `/?match=M000042&mode=fan&speed=60&from=60&lang=es`.

## Stage 4 – AI newsroom: multi-agent narratives on Microsoft Foundry (`matchlens/newsroom/`)

Every important moment (goals, red cards, big chances, a "state of play" read every 15 minutes,
half time and full time) is turned into commentary, a plain-language fan line, a data-rich analyst
line and, at half/full time, a studio script, article, social post and player of the match, in
several languages. It is built with **Microsoft Agent Framework** on **Microsoft Foundry**:

```
 live engine ──► fact sheet ──► Analyst ──► Writer ──► Fact checker ──► Localisers ──► Publisher
 (matchlens)   (every number     (calls the    (two       (code, not a    (one agent     (WebSocket
               the AI may use)   MCP tools)    audiences)  model)  │       per language,  "narrative"
                                       ▲                           │       concurrent)    message)
                                       └──── retry with the exact problems (max 2) ───┘
```

- **Grounded by construction.** A deterministic fact sheet (`matchlens/facts.py`) holds every number
  the writers may quote. The fact checker rejects any number that is not in the fact sheet or in a tool
  result the agents actually received, jargon in fan texts, and goal stories that don't name the scorer.
  Failures go back to the writer with the exact problems; after two retries the safe template text is used.
- **MCP server over the live engine** (`matchlens/mcp_server.py`, mounted at `/mcp`): `list_matches`,
  `get_match_state`, `get_player`, `get_timeline`, `get_pre_match`, `get_moments`. The analyst and recap
  agents call it for context; GitHub Copilot in VS Code can use it too (`.vscode/mcp.json`), so you can ask
  Copilot about the live match.
- **Never blocks the broadcast.** Each moment is published instantly from templates (`status: "draft"`)
  and upgraded in place when the agents finish (`status: "final"`). A bounded, deadline-aware queue drops
  low-priority moments when the replay outruns the models; goals, red cards and recaps are never dropped.
- **Transparent.** Each narrative ships with a trace (agents, tool calls, fact-check results, retries,
  timings) shown in the app under "How this was written", and a badge: AI · fact-checked, or auto text.

### Connect your Foundry project

1. In the Foundry portal deploy a small chat model (e.g. a GPT "mini" model) in your project.
2. Copy `.env.example` to `.env` and fill in `FOUNDRY_PROJECT_ENDPOINT` (project Overview page) and
   `FOUNDRY_MODEL` (the deployment name).
3. Sign in once with the Azure CLI: `az login` (or use the API-key option in `.env.example`).
4. Check it: `python -m matchlens.newsroom` prints the agents' texts and the trace for one goal.
5. Run the app as usual (`uvicorn matchlens.server:app`); the top bar shows "AI newsroom: Microsoft Foundry".

Without a `.env` everything still works with template texts (English and Spanish).

In code, the ingest stage can consume the same feed:

```python
from matchsim.replay import load_match, iter_live
m = load_match("data/matches/M000042")
for ev in iter_live(m["events"], speed=60):
    ...  # push into the interpretation layer
```

## What the engine models

- **Fictional Aurora League**: 10 clubs across 7 fan markets (en, es, fr, de, it, pt, nl) with distinct formations (4-3-3, 4-2-3-1, 4-4-2, 3-5-2, 3-4-3) and tactical styles (possession, press, directness, tempo, width, line height). Squads of 23 with 14 nationalities and 12 attributes per player.
- **Possession-chain engine**: each touch can be pressed, then becomes a carry + pass, dribble, cross, shot or clearance. Outcomes depend on attributes, both teams' shapes (defenders in the passing lane, receiver space, offside line), fatigue, weather and squad quality.
- **Latent match story**: a momentum process (home advantage, goal shocks) and a chaos level (goals, red cards, late pressure) drive phases of control and chaos; trailing teams push higher and press harder after ~55', leaders drop deeper. These are exported as hidden ground truth so explainability can be scored.
- **Tracking-lite**: sprints with top speed, distance and high-intensity running per player, 5-minute physical snapshots, ball release speed per pass and shot speed per shot – the raw material for speed/distance overlays.
- **Season mode**: standings, form, head-to-head, season and career stats, scoring streaks and milestone watch lists feed each match's pre-match context.

## Realism check (200 matches, per team per match)

| metric | sim | typical top flight |
|---|---|---|
| goals | 1.55 | 1.4 |
| xG | 1.52 | 1.4 |
| shots / on target | 13.2 / 4.8 | 12.5 / 4.3 |
| passes / accuracy | 494 / 80.1% | 470 / 81% |
| corners / crosses | 3.9 / 17.0 | 5.0 / 16 |
| fouls / yellows / offsides | 10.5 / 1.7 / 2.0 | 10.5 / 1.9 / 1.8 |
| tackles / interceptions / dribbles | 18.6 / 11.4 / 8.8 | 17 / 9 / 9 |
| distance / sprints | 110.2 km / 125 | 110 km / ~120 |

Home win / draw / away win over 400 matches: 43% / 22% / 35%. Ball in play ≈ 58 min. Reference values are approximate league-wide averages used as calibration targets.

## Model quality (held-out 20% of 3,000 training matches)

| model | metric | ours | scoreline + clock only | no information |
|---|---|---|---|---|
| win / draw / loss | log loss | **0.582** | 0.648 | 1.047 |
| next goal | log loss | **0.873** | 0.925 | 1.099 |
| pass difficulty | AUC | **0.79** | – | 0.50 |

Momentum index vs the simulation's hidden momentum: correlation 0.64. Chaos index vs hidden chaos: 0.43 (it tracks the direction well but under-reads the most extreme spells). Full tables in `matchlens/model_files/training_report.json`.

## Files

- `matchsim/league.py` – clubs, formations, squad generation
- `matchsim/engine.py` – match simulator
- `matchsim/season.py` – fixtures, standings, player context, milestones
- `matchsim/replay.py` – real-time feed and ticker
- `matchsim/stats.py` – box score
- `tools/validate.py` – calibration report
- `SCHEMA.md` – event and file schema

## Next stages

1. **Ingest + interpret**: streaming state store (possession %, field tilt, PPDA, xG race, pass difficulty, sprint thresholds).
2. **Explain**: momentum/control-vs-chaos detector scored against `ground_truth.json`; "why it matters" context (win probability swing, xG added, milestone).
3. **Render**: timed overlay JSON over WebSocket + browser overlay.
4. **Personalise + narrate**: analyst vs casual modes, favourite club/player focus, Azure OpenAI narratives in the fan's language.
