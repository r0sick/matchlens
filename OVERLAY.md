# MatchLens live protocol (v1)

Every screen – broadcast overlay, analyst dashboard, fan app – connects to the same
WebSocket and receives the same timed, machine-readable messages.

```
ws://<host>/ws/{match_id}?speed=60&from_minute=0&restart=0
```

- `speed`: replay speed (1 = real time, 60 = one match minute per second). Used only when the connection starts a new session.
- `from_minute`: start the replay at this minute (earlier events are processed silently, so stats are correct).
- `restart=1`: restart the session from `from_minute`; everyone watching receives a fresh `hello`.

Several clients can watch the same match; they share one session and receive identical messages.

A reference renderer is included: `http://localhost:8000/?match=M000042&view=overlay` draws the score bug,
win-probability strip, momentum ribbon and lower thirds on a transparent background (browser source in OBS / vMix).

## Envelope

Every message has the same envelope, so a renderer can schedule it against the match clock:

```json
{
  "v": 1,
  "type": "alert",
  "match_id": "M000042",
  "seq": 512,
  "period": 2,
  "clock": "76:14",
  "display_minute": "77'",
  "match_time_s": 4183.6,
  "wall_ts": 1792500123.412,
  "payload": { }
}
```

| Field | Meaning |
|---|---|
| `seq` | Strictly increasing per session; use it to detect gaps and order messages |
| `clock`, `display_minute`, `period` | Broadcast clock at the moment the message was produced (`"45+2'"` style in stoppage time) |
| `match_time_s` | Continuous playing time in seconds; the timeline to sync overlays against |
| `wall_ts` | Server wall-clock time (epoch seconds) when sent; `now - wall_ts` is the delivery latency |

## Message types

| type | when | payload |
|---|---|---|
| `hello` | First message after connecting (and after a restart) | `match` (competition, venue, referee, weather, coordinates), `home` / `away` (name, abbr, colours, formation, starting XI, bench), `pre_match` (standings, form, milestones, streaks), `state` (current snapshot), `series` (minute-by-minute history so far), `recent_alerts` (last 40 alerts) |
| `state` | Every second of wall time, and immediately after goals, cards, subs, kick-offs and period changes | Score, clock, team stats, possession (total, last 5 min), field tilt (total, last 10 min), PPDA, momentum (−100 away … +100 home), chaos (0–100), win probability, next-goal probability, match top speed, `session` status |
| `event` | Every match event except physical snapshots | `event_id`, `type`, `team_side`, `player_id`, `player_name`, `shirt`, `location_abs`, `end_location_abs` (broadcast frame, metres), `outcome`, `play_pattern`, `details`, and `derived.pass_difficulty` / `derived.difficulty_reasons` for passes |
| `alert` | When something on-screen-worthy happens | `alert` (goal, card, substitution, speed, rocket_shot, hard_pass, long_pass, big_chance_missed, distance), `side`, `player_id`, `player_name`, `data` (alert-specific numbers) |
| `win_prob_swing` | A goal, card or shot moves any outcome by 3 points or more | `cause`, `cause_event_id`, `before`, `after`, `swing_pts` |
| `minute` | Once per match minute | Chart point: score, xG, momentum, chaos, possession, field tilt, win probability |
| `players` | Every 10 s of wall time and at period end | Per-player live stats and rating (passes, accuracy, average pass difficulty, xG, xA, key passes, tackles, distance, top speed, rating …) |
| `narrative` | A goal, red card, big chance or 15-minute state-of-play read. Sent twice with the same `moment_id`: first `status: "draft"` (instant template text), then `status: "final"` (AI newsroom) | `moment_id`, `kind`, `display_minute`, `status`, `source`, `model`, `fallback`, `texts` {lang: {`caption`, `commentary`, `fan`, `analyst`}}, `trace`, `latency_ms` |
| `recap` | Half time and full time, draft then final, like `narrative` | `texts` {lang: {`headline`, `studio_script`, `article`, `social`, `player_of_the_match`}} |
| `fantasy` | Every 5 s of wall time and right after goals, cards, subs, saves and period ends | `matchday` (null outside the Fantasy season), `points` {player_id: {`points`, `minutes`, `position`, `reasons` [{`code`, `label`, `count`, `pts`}], `rating`, `provisional`}}, `quotes` {`open`, `next_goal` {home, none, away}, `scorer` {player_id: p}, `booked` {player_id: p}} |
| `calls` | To one viewer only: after connecting, after placing a call and when one of their calls settles | `points`, `won`, `lost`, `calls` [{`call_id`, `kind`, `target`, `label`, `p`, `pays`, `minute`, `status`}], optional `placed` / `settled` |
| `session` | On pause, resume, speed change, restart and full time | `speed`, `paused`, `done`, `progress`, `viewers` |
| `error` | Bad match id or command | `message` |

## Alert data

| alert | `data` |
|---|---|
| `goal` | `score`, `xg`, `assist` |
| `card` | `card` (yellow, second_yellow, red) |
| `substitution` | `on`, `off`, `reason` |
| `speed` | `top_speed_kmh`, `match_record`, `distance_m` (sprints ≥ 35 km/h, or a new match top speed ≥ 32 km/h) |
| `rocket_shot` | `shot_speed_kmh`, `outcome` (shots ≥ 105 km/h) |
| `hard_pass` | `difficulty` (0–100), `reasons`, `length_m`, `recipient` (completed passes with difficulty ≥ 75) |
| `long_pass` | `length_m`, `ball_speed_kmh`, `recipient` (completed passes ≥ 60 m) |
| `big_chance_missed` | `xg`, `outcome` (xG ≥ 0.30, not scored) |
| `distance` | `km` (10 and 12 km milestones) |

## No look-ahead

The stream only contains what is knowable at that moment. Provider annotations that are added after the fact
(`key_pass`, `assist`, `provider_completion_prob` on pass events) are stripped; key passes and assists are
credited when the shot or goal happens.

## Controls

Send JSON over the socket, or POST it to `/api/sessions/{match_id}/control`:

```json
{"action": "pause"}
{"action": "resume"}
{"action": "speed", "speed": 120}
{"action": "restart", "speed": 60, "from_minute": 70}
{"action": "lang", "lang": "fr"}      // WebSocket only: also translate narratives into this language
{"action": "call", "kind": "scorer", "target": "P0106"}   // WebSocket only: a live call (next_goal: home|none|away; scorer / booked: player_id)
{"action": "calls"}                   // WebSocket only: resend my calls
```

Pass `?viewer=<token>` on the WebSocket so a viewer keeps their calls across reconnects.
A correct call pays `round(10 / p)` call points, where `p` is the model probability when it was made
(at most 3 open calls). Calls never change Fantasy points.

The WebSocket also accepts `?lang=fr`. The newsroom writes English plus the viewers' languages and the
clubs' home-market languages (up to three).

## REST

| Endpoint | Returns |
|---|---|
| `GET /api/matches` | Available matches (demo and season), no final scores |
| `GET /api/matches/{match_id}` | Match summary and session status |
| `GET /api/sessions/{match_id}/state` | Full current snapshot, including every player |
| `GET /api/fantasy/meta` | Budget, squad shape, club limit, clubs |
| `GET /api/fantasy/players?matchday=10` | Every player as of a matchday: price, points, form, goals, xG, projection (earlier matchdays only) |
| `GET /api/fantasy/squad?matchday=10&match_id=…` | A suggested 15-player squad within budget |
| `POST /api/fantasy/advice` | `{player_id, squad, matchday, bank, lang}` → Transfer Advisor verdict, reasons, replacements, texts, trace |
