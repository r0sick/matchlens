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
| goals | 1.68 | 1.4 |
| xG | 1.64 | 1.4 |
| shots / on target | 13.9 / 5.1 | 12.5 / 4.3 |
| passes / accuracy | 496 / 81.5% | 470 / 81% |
| corners / crosses | 4.2 / 17.7 | 5.0 / 16 |
| fouls / yellows / offsides | 10.1 / 1.6 / 1.8 | 10.5 / 1.9 / 1.8 |
| tackles / interceptions / dribbles | 18.5 / 10.8 / 9.0 | 17 / 9 / 9 |
| distance / sprints | 109.6 km / 125 | 110 km / ~120 |

Home win / draw / away win: 44% / 22% / 34%. Ball in play ≈ 59 min. Reference values are approximate league-wide averages used as calibration targets.

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
