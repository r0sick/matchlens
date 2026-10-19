# MatchSim event schema (v1.0)

Every match folder contains:

| File | Purpose | Live-safe? |
|---|---|---|
| `events.jsonl` / `events.jsonl.gz` | One JSON event per line, sorted by `match_time_s` | yes |
| `metadata.json` | Teams, line-ups with attributes, venue, referee, weather, pre-match context | yes |
| `box_score.json` | Final team/player aggregates (for validation and recaps) | post-match only |
| `ground_truth.json` | Hidden latent state that drove the simulation (momentum, chaos, tactical intent per minute) | **no** – evaluation only |
| `events.csv` | Flat export (`--csv`), `details` kept as a JSON string | yes |

## Coordinates

- Pitch 105 × 68 m.
- `location` / `end_location`: the **acting team's attacking frame**. x = 0 → 105 toward the opponent's goal, y = 0 → 68 from the left touchline to the right when facing that goal. A pass at x = 90 is always in the final third of the team that made it.
- `location_abs` / `end_location_abs`: fixed **broadcast frame** for overlays. x = 0 is the left goal line on screen. Home attacks right in period 1 and left in period 2 (`metadata.coordinates`).

## Common fields

| Field | Example | Notes |
|---|---|---|
| `event_id` | `M000042-00051` | Unique; numbered in creation order |
| `seq` | `24` | Chronological order within the match – use this, not `event_id` |
| `period` | `1` / `2` | |
| `t` | `39.3` | Seconds since period kick-off |
| `match_time_s` | `3006.3` | Continuous playing clock across periods (no half-time gap); drives replay pacing |
| `clock`, `minute`, `second` | `"47:03"`, `47`, `3` | Broadcast clock (2nd half starts at 45:00) |
| `display_minute` | `"48'"`, `"45+2'"` | Ready for graphics |
| `type` | `"pass"` | See below |
| `team_id`, `team_side` | `"C01"`, `"home"` | Team performing the event |
| `player_id`, `player_name`, `shirt` | | `null` for team/match events |
| `possession_id`, `possession_team_id` | `107`, `"C02"` | Possession chain the event belongs to |
| `play_pattern` | `regular_play`, `from_counter`, `from_corner`, `from_free_kick`, `from_throw_in`, `from_goal_kick`, `from_kick_off`, `from_penalty` | |
| `outcome` | `complete` / `incomplete` / `won` / `goal` … | Type-specific |
| `duration_s` | `1.02` | Ball flight / action duration |
| `score` | `{"home":0,"away":0}` | Score **before** the event (the `goal` event shows the score after) |
| `details` | `{...}` | Type-specific payload |

## Event types and `details`

| type | outcome | details |
|---|---|---|
| `match_start`, `match_end`, `period_start`, `period_end`, `added_time` | – | `final_score`, `home_attacks`, `minutes` |
| `kick_off` | – | – |
| `pass` | `complete`, `incomplete`, `offside` | `recipient_id/name`, `length_m`, `angle_deg`, `height` (ground/low/high), `pass_type` (ground_pass, through_ball, long_ball, switch, cross, corner, free_kick, throw_in, goal_kick, gk_throw, kick_off), `body_part`, `under_pressure`, `defenders_in_lane`, `receiver_space_m`, `progressive_distance_m`, `into_final_third`, `into_box`, `ball_speed_kmh` (release speed), `flight_time_s`, `switch`, `cross`, `key_pass`, `assist`, `provider_completion_prob`, `defenders_in_box` (crosses) |
| `carry` | – | `distance_m`, `progressive_m`, `speed_kmh` |
| `dribble` | `complete`, `incomplete` | `opponent_id/name`, `under_pressure`, `nutmeg` |
| `dribbled_past` | – | `by_player_id` |
| `pressure` | – | `pressed_player_id/name`, `distance_to_ball_m`, `counterpress` |
| `tackle` | `won`, `lost` | `opponent_id/name` |
| `interception`, `ball_recovery` | `won` | – |
| `clearance` | – | `body_part`, `under_pressure` |
| `block` | – | `shot_event_id` |
| `aerial_duel` | `won`, `lost` | `opponent_id` (emitted once per player) |
| `shot` | `goal`, `saved`, `off_target`, `blocked`, `post` | `xg` (provider model), `body_part`, `technique` (normal, volley, half_volley, chip, curler, header, free_kick, penalty), `shot_speed_kmh`, `distance_m`, `angle_deg`, `under_pressure`, `big_chance`, `first_time`, `end_z_m`, `on_target`, `key_pass_id`, `key_pass_player_id`, `goalkeeper_id` |
| `goal` | – | `shot_event_id`, `xg`, `assist_player_id/name`, `own_goal`, `body_part`, `technique`, `score_after` |
| `goalkeeper` | `success` | `action` (save, claim), `held`, `shot_event_id`, `shot_xg`, `shot_speed_kmh` |
| `foul` | – | `fouled_player_id/name`, `penalty`, `advantage`, `tactical` |
| `card` | – | `card` (yellow, second_yellow, red), `foul_event_id`, `reason` |
| `offside` | – | `pass_event_id`, `defensive_line_x` |
| `ball_out` | – | `restart` (throw_in, goal_kick, corner) |
| `possession_change` | – | `from_team_id`, `to_team_id`, `reason`, `previous_possession` {`duration_s`, `passes`, `start_x`, …} |
| `substitution` | – | `player_off_*`, `player_on_*`, `role`, `reason` (tactical/injury), `player_off_stamina_pct`, `subs_used` |
| `injury` | – | `severity` |
| `sprint` | – | `top_speed_kmh`, `distance_m`, `session_top_speed_kmh`, `sprint_count` (sprint = > ~24 km/h) |
| `physical_snapshot` | – | every 5 min per team: `players[]` with `distance_m`, `hi_run_m`, `sprints`, `top_speed_kmh`, `stamina_pct` |

## Metadata highlights

- `home` / `away`: club identity (name, abbr, nickname, colours, market language), formation, `style_profile`, `starting_xi` and `bench` with positions, nationality, age, foot, height and 12 attributes.
- `referee` (with `strictness`), `weather`, `venue`, `attendance`, `kickoff_utc`.
- `pre_match` (season mode): standings and form, head-to-head this season, every player's season and career totals, `milestones_watch` (e.g. one goal from a 100th career goal), `scoring_streaks`. All derived from matches already simulated, so storylines are consistent with the data.

## Ground truth (evaluation only)

`ground_truth.timeline[]` per minute: `momentum_home` (−1…1), `chaos` (0…1), live tactical `home_style` / `away_style` (press, directness, line height, tempo…), average stamina and score. Use it to check whether the interpretation layer detects momentum swings, pressing changes and "control vs chaos" from events alone. Never feed it to the live pipeline.
