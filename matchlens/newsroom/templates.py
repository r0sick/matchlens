"""Deterministic narrator: instant, always-available texts built straight from a fact sheet.

Used (1) as the immediate first version of every narrative, so graphics never wait for a
model, (2) whenever no AI provider is configured, and (3) as the safe fallback when the AI
output fails the fact check. English and Spanish are supported.
"""
from __future__ import annotations

SITUATION = {
    "en": {"opener": "opens the scoring", "equaliser": "levels it", "go_ahead": "puts them ahead",
           "extends_lead": "extends the lead", "pulls_one_back": "pulls one back"},
    "es": {"opener": "abre el marcador", "equaliser": "iguala el partido", "go_ahead": "pone por delante a su equipo",
           "extends_lead": "amplía la ventaja", "pulls_one_back": "recorta distancias"},
}
CONTROL = {"en": {"chaotic": "chaotic", "controlled": "controlled", "balanced": "finely balanced"},
           "es": {"chaotic": "caótico", "controlled": "controlado", "balanced": "equilibrado"}}


def one_in(p_pct: int | None) -> int | None:
    return None if not p_pct else max(1, round(100 / p_pct))


def score_str(sheet) -> str:
    s = sheet["match"]["score"]
    return f'{sheet["home"]["abbr"]} {s["home"]}-{s["away"]} {sheet["away"]["abbr"]}'


def leader(sheet, block="match"):
    wp = sheet["match"].get("win_probability_pct") or {}
    if not wp:
        return None, None
    side = max(("home", "draw", "away"), key=lambda k: wp[k])
    return side, wp[side]


def render(sheet: dict, lang: str = "en") -> dict:
    lang = lang if lang in ("en", "es") else "en"
    fn = {"goal": goal, "red_card": red_card, "big_chance": big_chance, "state_of_play": state_of_play,
          "half_time": recap, "full_time": recap}[sheet["kind"]]
    return fn(sheet, lang)


def goal(s, lang):
    g, sc = s["goal"], s.get("scorer") or {}
    name, team = sc.get("name", "?"), g["team"]
    sit = SITUATION[lang][g["situation"]]
    wp = s.get("win_probability") or {}
    odds = one_in(g.get("chance_scored_pct"))
    extra_en, extra_es = [], []
    if s.get("streak"):
        n = s["streak"]["matches_in_a_row_incl_today"]
        extra_en.append(f"{name} has now scored in {n} matches in a row.")
        extra_es.append(f"{name} ya suma {n} partidos seguidos marcando.")
    if s.get("milestone"):
        v = s["milestone"]["value"]
        extra_en.append(f"It is goal number {v} of his career.")
        extra_es.append(f"Es el gol número {v} de su carrera.")
    if lang == "es":
        cap = f"¡Gol de {name}! {score_str(s)}"
        com = f"{name} {sit} para el {team}" + (f", asistido por {g['assist']}" if g.get("assist") else "") + "."
        fan = (f"Una ocasión que solo entra 1 de cada {odds} veces" if odds and odds >= 4 else "Una ocasión clara") + \
              (f", y las opciones de victoria del {team} pasan del {wp['before_pct']}% al {wp['after_pct']}%." if wp else ".")
        ana = f"xG {g['xg']:.2f} ({g.get('chance_scored_pct')}%)" + \
              (f"; probabilidad de victoria {team} {wp['before_pct']}% → {wp['after_pct']}%." if wp else ".")
        return {"caption": cap, "commentary": " ".join([com] + extra_es), "fan": fan, "analyst": ana}
    cap = f"Goal! {name} — {score_str(s)}"
    com = f"{name} {sit} for {team}" + (f", set up by {g['assist']}" if g.get("assist") else "") + "."
    fan = (f"That chance goes in only about 1 time in {odds}" if odds and odds >= 4 else "A clear-cut chance, taken") + \
          (f", and {team}'s chance of winning jumps from {wp['before_pct']}% to {wp['after_pct']}%." if wp else ".")
    ana = f"xG {g['xg']:.2f} ({g.get('chance_scored_pct')}% scoring probability)" + \
          (f"; {team} win probability {wp['before_pct']}% → {wp['after_pct']}%." if wp else ".")
    return {"caption": cap, "commentary": " ".join([com] + extra_en), "fan": fan, "analyst": ana}


def red_card(s, lang):
    c, p = s["card"], s.get("player") or {}
    wp = s.get("win_probability") or {}
    name, team, n = p.get("name", "?"), c["team"], c["players_left_on_pitch"]
    opp = s["away" if c["side"] == "home" else "home"]["short_name"]
    if lang == "es":
        return {"caption": f"Roja para {name} ({team})",
                "commentary": f"{name} se va expulsado y el {team} se queda con {n}.",
                "fan": f"Con un jugador más, las opciones del {opp} suben" + (f" al {wp['after_pct']}%." if wp else "."),
                "analyst": f"Inferioridad numérica ({n} v 11)" + (f"; victoria {opp} {wp['before_pct']}% → {wp['after_pct']}%." if wp else ".")}
    return {"caption": f"Red card: {name} ({team})",
            "commentary": f"{name} is sent off and {team} are down to {n}.",
            "fan": f"With an extra player, {opp}'s chance of winning rises" + (f" to {wp['after_pct']}%." if wp else "."),
            "analyst": f"{n} v 11" + (f"; {opp} win probability {wp['before_pct']}% → {wp['after_pct']}%." if wp else ".")}


def big_chance(s, lang):
    c, p = s["chance"], s.get("player") or {}
    name, team, odds = p.get("name", "?"), c["team"], c["usually_scored_pct"]
    if lang == "es":
        return {"caption": f"¡Perdona {name}!",
                "commentary": f"Ocasión clarísima para {name} y el {team} no la aprovecha.",
                "fan": f"Una ocasión que se marca {odds} de cada 100 veces.",
                "analyst": f"xG {c['xg']:.2f} sin gol ({c['outcome']}); xG {team} acumulado {s['match']['xg'][c['side']]:.2f}."}
    return {"caption": f"Big chance missed by {name}",
            "commentary": f"A golden opportunity for {name}, and {team} cannot take it.",
            "fan": f"Chances like that are usually scored {odds} times in 100.",
            "analyst": f"{c['xg']:.2f} xG not converted ({c['outcome']}); {team} now on {s['match']['xg'][c['side']]:.2f} xG."}


def state_of_play(s, lang):
    m, last, press = s["match"], s.get("last_15_min") or {}, s["pressing_and_territory"]
    side = "home" if m["momentum"] >= 0 else "away"
    team = s[side]["short_name"]
    ctl = CONTROL[lang][m["control"]]
    xg = last.get("xg", {"home": 0, "away": 0})
    tilt = press["field_tilt_last_10_pct"][side]
    ppda = press["ppda_last_15"]
    presser = "home" if ppda["home"] < ppda["away"] else "away"
    if lang == "es":
        top = f"Domina el {team}" if abs(m["momentum"]) >= 25 else "Partido igualado"
        return {"caption": f"{m['minute']}: {top}",
                "commentary": f"Partido {ctl}. En los últimos 15 minutos {'manda el ' + team if abs(m['momentum']) >= 25 else 'nadie se impone'}.",
                "fan": (f"El {team} está mandando: juega el {tilt}% del tiempo en campo rival." if abs(m["momentum"]) >= 25
                        else "Ningún equipo se impone por ahora."),
                "analyst": f"PPDA últimos 15': {ppda['home']} vs {ppda['away']} (presiona más el {s[presser]['short_name']}); field tilt {tilt}%."}
    top = f"{team} on top" if abs(m["momentum"]) >= 25 else "Evenly poised"
    return {"caption": f"{m['minute']} — {top}",
            "commentary": f"A {ctl} game so far, and {team + ' have had the better of the last 15 minutes' if abs(m['momentum']) >= 25 else 'neither side has the upper hand over the last 15 minutes'}.",
            "fan": (f"{team} are in charge, playing {tilt}% of the game in the opposition half." if abs(m["momentum"]) >= 25
                    else "Neither side has taken control yet."),
            "analyst": f"PPDA last 15': {ppda['home']} vs {ppda['away']} ({s[presser]['short_name']} pressing harder); field tilt {tilt}%."}


def recap(s, lang):
    m, ts = s["match"], s["team_stats"]
    H, A = s["home"]["short_name"], s["away"]["short_name"]
    h, a = m["score"]["home"], m["score"]["away"]
    goals = ", ".join(f'{g["scorer"]} {g["minute"]}' for g in s.get("goals", [])) or ("sin goles" if lang == "es" else "no goals")
    top = (s.get("top_players") or [{}])[0]
    ft = s["kind"] == "full_time"
    if lang == "es":
        head = (f"Final: {H} {h}-{a} {A}" if ft else f"Descanso: {H} {h}-{a} {A}")
        script = (f"{head}. Goles: {goals}. "
                  f"Tiros {ts['home']['shots']}-{ts['away']['shots']}. Partido {CONTROL['es'][m['control']]}.")
        return {"headline": head, "studio_script": script, "article": script,
                "social": f"{head} | {goals}", "player_of_the_match":
                    {"name": top.get("name"), "reason": f"Nota {top.get('rating')} con {top.get('key_passes', 0)} pases clave."}}
    head = (f"Full time: {H} {h}-{a} {A}" if ft else f"Half time: {H} {h}-{a} {A}")
    script = (f"{head}. Goals: {goals}. "
              f"Shots {ts['home']['shots']}-{ts['away']['shots']}. A {CONTROL['en'][m['control']]} contest.")
    return {"headline": head, "studio_script": script, "article": script, "social": f"{head} | {goals}",
            "player_of_the_match": {"name": top.get("name"),
                                    "reason": f"Rated {top.get('rating')} with {top.get('key_passes', 0)} key passes."}}
