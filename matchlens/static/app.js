/* MatchLens client: one WebSocket stream, three ways to watch it (broadcast, analyst, fan). */
'use strict';

// ------------------------------------------------------------------ i18n
const I18N = {
  en: {
    watch: 'Watch', pause: 'Pause', resume: 'Resume', broadcast: 'Broadcast', analyst: 'Analyst', fan: 'Fan',
    preferences: 'Preferences', key_moments: 'Key moments', match_stats: 'Match stats', on_the_ball: 'On the ball',
    overlay_hint: 'Add ?view=overlay to the address for a transparent graphics layer you can put over a video feed in OBS or vMix.',
    win_prob: 'Win probability', xg_race: 'xG race', momentum_chaos: 'Momentum and chaos', team_stats: 'Team stats',
    shot_map: 'Shot map', shot_legend: 'Circle size = xG. Filled = goal.', pass_map: 'Completed passes, last 10 minutes',
    pass_legend: 'Line colour = pass difficulty: green easy, yellow medium, red hard.', players: 'Players',
    story: 'The story so far', language: 'Language', fav_club: 'Favourite club', fav_player: 'Player to follow',
    cancel: 'Cancel', save: 'Save', none: 'None', draw: 'Draw', connecting: 'Connecting…', live: 'Live',
    paused: 'Paused', full_time: 'Full time', disconnected: 'Disconnected – press Watch to reconnect',
    first_half: '1st half', second_half: '2nd half', win: 'win',
    // stats
    s_xg: 'xG', s_shots: 'Shots (on target)', s_poss: 'Possession', s_poss5: 'Possession, last 5 min',
    s_tilt: 'Field tilt, last 10 min', s_pass: 'Pass accuracy', s_ppda: 'PPDA (lower = more pressing)',
    s_corners: 'Corners', s_fouls: 'Fouls / yellow cards', s_dist: 'Distance (km)', s_sprints: 'Sprints',
    // table
    t_player: 'Player', t_rating: 'Rating', t_passes: 'Passes', t_acc: 'Acc %', t_diff: 'Avg difficulty', t_xg: 'xG',
    t_xa: 'xA', t_shots: 'Shots', t_kp: 'Key passes', t_tk: 'Tackles won', t_dist: 'km', t_top: 'Top km/h',
    // momentum
    momentum: 'Momentum', chaos: 'Chaos', on_top: '{team} on top', level: 'Even',
    // captions
    goal: 'Goal! {player} ({team})', goal_k: 'GOAL', assist: 'Assist: {name}.',
    goal_why: 'A {xg} xG chance – scored about {pct}% of the time.',
    swing: '{team} win chance {b}% → {a}%.',
    card_yellow: 'Yellow card for {player} ({team})', card_red: 'Red card for {player} ({team})',
    card_second_yellow: 'Second yellow – {player} ({team}) is sent off', card_k: 'CARD',
    sub: '{team} change: {on} on for {off}', sub_k: 'SUB',
    big_chance: 'Big chance missed by {player} ({team})', big_chance_why: 'Worth {xg} xG – usually scored {pct}% of the time.',
    rocket: '{player} unleashes a {kmh} km/h shot', rocket_k: 'SHOT SPEED',
    speed: '{player} clocks {kmh} km/h', speed_record: 'Fastest sprint of the match so far', speed_k: 'TOP SPEED',
    hard_pass: '{player} completes a difficulty-{d} pass to {to}', hard_pass_k: 'PASS OF NOTE',
    long_pass: '{player} finds {to} with a {m} m pass', distance: '{player} has run {km} km',
    swing_k: 'WIN PROBABILITY', swing_title: 'Win probability shifts after a {cause}',
    // headline
    h_ft_win: 'Full time: {team} win {score}.', h_ft_draw: 'Full time: honours even at {score}.',
    h_on_top: '{team} are on top, with {poss}% of the ball in the last five minutes.',
    h_even: 'Neither side is in control right now.', h_fav: '{team} are {p}% favourites to win.',
    h_draw: 'A draw is the most likely result ({p}%).', h_chaos: 'It has turned scrappy: the ball keeps changing hands.',
    h_pre: 'Kick-off is coming up.',
    follow_prompt: 'Follow one player through the match: pick them in Preferences.', follow_btn: 'Choose a player',
    f_rating: 'Rating', f_passes: 'Passes', f_xg: 'xG', f_shots: 'Shots', f_kp: 'Key passes', f_tk: 'Tackles won',
    f_dist: 'Distance', f_top: 'Top speed', not_in_match: '{name} is not in this match.',
    on_bench: 'On the bench', subbed_off: 'Substituted',
    // newsroom
    ai_badge: 'AI · fact-checked', auto_badge: 'Auto text', fallback_badge: 'Safe text (AI check failed)',
    ai_on: 'AI newsroom: {src}', ai_off: 'AI newsroom off – template texts', sop_k: 'STATE OF PLAY',
    ht_k: 'HALF TIME', ft_k: 'FULL TIME', analyst_notes: 'Analyst notes', match_report: 'Match report',
    recap_wait: 'The report appears at half time and full time.', script: 'Studio script', article: 'Article',
    social: 'Social post', potm: 'Player of the match', standout: 'Standout so far', how_made: 'How this was written',
    lang_hint: 'Menus are in English or Spanish; match commentary is written in every listed language.',
    st_analyst: 'Analyst', st_writer: 'Writer', st_fact_check: 'Fact check', st_recap_editor: 'Studio editor',
    st_localiser: 'Translator', tools: 'tools', retry: 'retry', secs: 's',
    // fantasy
    fantasy: 'Fantasy', my_squad: 'My squad', live_pts: 'live points', reset_squad: 'Use suggested squad',
    squad_hint: 'Tap ★ to pick your captain (double points). Ask the advisor about any player.',
    advisor: 'Transfer Advisor', advisor_hint: 'Choose “Advice” on a player: hold, watch or sell, with the reasons and affordable replacements.',
    calls: 'Live calls', call_pts: 'call points', my_calls: 'My calls', no_calls: 'No calls yet.',
    calls_hint: 'Predict what happens next. Odds come from the live models; a correct call pays 10 ÷ its probability. Calls never change Fantasy points.',
    fx_meta: 'Matchday {md} · €{cost}m of €{budget}m · bank €{bank}m', fx_unavailable: 'Fantasy uses the Aurora League season: pick a Matchday match to play.',
    in_match: 'In this match', not_playing: 'Not in this match', advice: 'Advice', asking: 'The advisor is looking at {name}…',
    next_goal: 'Next goal', no_more: 'No more goals', scorer: 'To score', booked: 'To be booked', pays: 'pays {n}',
    won: 'won', lost: 'lost', open_call: 'open', calls_closed: 'Calls are closed: the match is over.',
    replacements: 'Affordable replacements', transfer_in: 'Transfer in', ppm: '{p} pts/match projected',
    v_HOLD: 'Hold', v_WATCH: 'Watch', v_SELL: 'Sell', st_scout: 'Scout (rules)', st_advisor: 'Advisor',
    r_appearance: 'Played', r_appearance_60: '60+ min', r_goal: 'Goal', r_assist: 'Assist', r_clean_sheet: 'Clean sheet',
    r_conceded: 'Conceded', r_saves: 'Saves', r_defensive: 'Defensive work', r_yellow: 'Yellow', r_red: 'Red',
    r_own_goal: 'Own goal', r_bonus: 'Bonus', provisional: 'provisional', captain: 'Captain',
    f_form: 'form', f_pts: 'pts', transferred: '{out} out, {in} in.',
    v_pitch: 'Pitch', v_list: 'List', bench: 'Bench', swap: 'Swap into the XI', swap_hint: 'Tap a highlighted starter to swap {name} in.',
    fixtures: 'Next fixtures', fdr_legend: 'Colour = opponent difficulty: green easy, red hard. H home, A away. Ø = average difficulty.',
    md_short: 'MD', make_captain: 'Make captain', close: 'Close', radar: 'Strengths and weaknesses', scorecard: 'Scorecard',
    radar_hint: 'Percentile against the {n} {pos} players with 270+ minutes (100 = best in the league).',
    radar_few: 'Not enough minutes yet (fewer than {m}) for a fair comparison.',
    hexagon: 'Attribute analysis', attributes: 'Attributes', hx_rating: 'Rating (attributes)', hx_season: 'This season (percentile vs position)',
    measured: 'Measured in this season’s matches: percentile against the same position (1–99)',
    attrs_hint: '◉ = measured in this season’s matches, as a percentile against players in the same position (needs {m}+ minutes). Other values are scouting attributes (1–99).',
    hx_pac: 'Pace', hx_sho: 'Shooting', hx_pas: 'Passing', hx_dri: 'Dribbling', hx_def: 'Defending', hx_phy: 'Physical',
    hx_div: 'Diving', hx_han: 'Handling', hx_kic: 'Kicking', hx_ref: 'Reflexes', hx_spd: 'Speed', hx_pos: 'Positioning',
    sa_pace: 'Pace', sa_top_speed: 'Top speed', sa_sprints90: 'Sprints per 90', sa_finishing: 'Finishing', sa_shot_power: 'Shot power',
    sa_positioning: 'Positioning', sa_shots90: 'Shots per 90', sa_xg90: 'xG per 90', sa_passing: 'Passing', sa_vision: 'Vision',
    sa_pass_acc: 'Pass accuracy', sa_kp90: 'Key passes per 90', sa_prog90: 'Progressive actions per 90', sa_dribbling: 'Dribbling',
    sa_composure: 'Composure', sa_drb90: 'Dribbles per 90', sa_tackling: 'Tackling', sa_aerial: 'Heading / aerial', sa_def90: 'Defensive actions per 90',
    sa_stamina: 'Stamina', sa_dist90: 'Distance per 90', sa_availability: 'Availability', sa_keeping: 'Goalkeeping', sa_saves90: 'Saves per 90',
    sa_clean_sheets: 'Clean-sheet rate', sa_conceded90: 'Goals conceded per 90 (fewer = higher)', sa_save_pct: 'Save percentage',
    st_starter: 'Starter', st_rotation: 'Rotation', st_bench: 'Bench role', st_not_playing: 'Not playing', st_unknown: 'No data yet',
    form_pct_hint: 'Form over the last 3 matchdays, as a percentile among players in the same position',
    last3_md: 'last 3 MDs', price: 'Price', p_points: 'Points', p_avg: 'Avg / match', p_last3: 'Avg last 3', p_home: 'Avg home', p_away: 'Avg away',
    p_proj: 'Projected', p_apps: '{m} matches · {s} starts · {min} minutes', role: 'Usual position', by_md: 'Points by matchday',
    last5: 'Last 5 matches', next5: 'Next 5 fixtures', season_stats: 'Season stats', did_not_play: 'did not play', sub_on: 'sub',
    s_goals: 'Goals', s_assists: 'Assists', s_def: 'Defensive actions', s_saves: 'Saves', s_cards: 'Yellow / red',
    foot_left: 'left foot', foot_right: 'right foot', foot_both: 'both feet',
  },
  es: {
    watch: 'Ver', pause: 'Pausa', resume: 'Reanudar', broadcast: 'Retransmisión', analyst: 'Analista', fan: 'Afición',
    preferences: 'Preferencias', key_moments: 'Momentos clave', match_stats: 'Estadísticas', on_the_ball: 'Con el balón',
    overlay_hint: 'Añade ?view=overlay a la dirección para obtener una capa gráfica transparente sobre la señal de vídeo en OBS o vMix.',
    win_prob: 'Probabilidad de victoria', xg_race: 'Carrera de xG', momentum_chaos: 'Dominio y caos', team_stats: 'Estadísticas de equipo',
    shot_map: 'Mapa de tiros', shot_legend: 'Tamaño del círculo = xG. Relleno = gol.', pass_map: 'Pases completados, últimos 10 minutos',
    pass_legend: 'Color de la línea = dificultad del pase: verde fácil, amarillo media, rojo difícil.', players: 'Jugadores',
    story: 'La historia del partido', language: 'Idioma', fav_club: 'Equipo favorito', fav_player: 'Jugador a seguir',
    cancel: 'Cancelar', save: 'Guardar', none: 'Ninguno', draw: 'Empate', connecting: 'Conectando…', live: 'En directo',
    paused: 'En pausa', full_time: 'Final', disconnected: 'Desconectado: pulsa Ver para reconectar',
    first_half: '1.ª parte', second_half: '2.ª parte', win: 'gana',
    s_xg: 'xG', s_shots: 'Tiros (a puerta)', s_poss: 'Posesión', s_poss5: 'Posesión, últimos 5 min',
    s_tilt: 'Dominio territorial, últimos 10 min', s_pass: 'Precisión de pase', s_ppda: 'PPDA (menos = más presión)',
    s_corners: 'Córners', s_fouls: 'Faltas / amarillas', s_dist: 'Distancia (km)', s_sprints: 'Sprints',
    t_player: 'Jugador', t_rating: 'Nota', t_passes: 'Pases', t_acc: '% acierto', t_diff: 'Dificultad media', t_xg: 'xG',
    t_xa: 'xA', t_shots: 'Tiros', t_kp: 'Pases clave', t_tk: 'Entradas ganadas', t_dist: 'km', t_top: 'Vel. máx.',
    momentum: 'Dominio', chaos: 'Caos', on_top: 'Domina {team}', level: 'Igualado',
    goal: '¡Gol! {player} ({team})', goal_k: 'GOL', assist: 'Asistencia: {name}.',
    goal_why: 'Una ocasión de {xg} xG: se marca aproximadamente el {pct}% de las veces.',
    swing: 'Opciones de victoria de {team}: {b}% → {a}%.',
    card_yellow: 'Amarilla para {player} ({team})', card_red: 'Roja para {player} ({team})',
    card_second_yellow: 'Segunda amarilla: {player} ({team}) es expulsado', card_k: 'TARJETA',
    sub: 'Cambio de {team}: entra {on}, sale {off}', sub_k: 'CAMBIO',
    big_chance: 'Ocasión clara fallada por {player} ({team})', big_chance_why: 'Valía {xg} xG: suele marcarse el {pct}% de las veces.',
    rocket: '{player} dispara a {kmh} km/h', rocket_k: 'POTENCIA',
    speed: '{player} alcanza {kmh} km/h', speed_record: 'El sprint más rápido del partido', speed_k: 'VELOCIDAD',
    hard_pass: '{player} completa un pase de dificultad {d} a {to}', hard_pass_k: 'PASE DESTACADO',
    long_pass: '{player} encuentra a {to} con un pase de {m} m', distance: '{player} lleva {km} km recorridos',
    swing_k: 'PROBABILIDAD', swing_title: 'La probabilidad de victoria cambia tras un {cause}',
    h_ft_win: 'Final: gana {team} por {score}.', h_ft_draw: 'Final: reparto de puntos, {score}.',
    h_on_top: '{team} domina, con el {poss}% del balón en los últimos cinco minutos.',
    h_even: 'Ningún equipo controla el partido ahora mismo.', h_fav: '{team} tiene un {p}% de opciones de ganar.',
    h_draw: 'El empate es el resultado más probable ({p}%).', h_chaos: 'El partido se ha roto: el balón cambia de manos constantemente.',
    h_pre: 'El partido está a punto de empezar.',
    follow_prompt: 'Sigue a un jugador durante todo el partido: elígelo en Preferencias.', follow_btn: 'Elegir jugador',
    f_rating: 'Nota', f_passes: 'Pases', f_xg: 'xG', f_shots: 'Tiros', f_kp: 'Pases clave', f_tk: 'Entradas ganadas',
    f_dist: 'Distancia', f_top: 'Vel. máx.', not_in_match: '{name} no juega este partido.',
    on_bench: 'En el banquillo', subbed_off: 'Sustituido',
    ai_badge: 'IA · verificado', auto_badge: 'Texto automático', fallback_badge: 'Texto seguro (falló la verificación)',
    ai_on: 'Redacción IA: {src}', ai_off: 'Redacción IA desactivada: textos automáticos', sop_k: 'LECTURA',
    ht_k: 'DESCANSO', ft_k: 'FINAL', analyst_notes: 'Notas del analista', match_report: 'Crónica',
    recap_wait: 'La crónica aparece al descanso y al final.', script: 'Guion de plató', article: 'Crónica',
    social: 'Redes sociales', potm: 'Jugador del partido', standout: 'El más destacado', how_made: 'Cómo se ha escrito',
    lang_hint: 'Los menús están en inglés o español; los comentarios se escriben en todos los idiomas de la lista.',
    st_analyst: 'Analista', st_writer: 'Redactor', st_fact_check: 'Verificación', st_recap_editor: 'Editor',
    st_localiser: 'Traductor', tools: 'herramientas', retry: 'reintento', secs: 's',
    fantasy: 'Fantasy', my_squad: 'Mi plantilla', live_pts: 'puntos en directo', reset_squad: 'Usar plantilla sugerida',
    squad_hint: 'Pulsa ★ para elegir capitán (puntos dobles). Pide consejo sobre cualquier jugador.',
    advisor: 'Asesor de fichajes', advisor_hint: 'Pulsa «Consejo» en un jugador: mantener, vigilar o vender, con los motivos y sustitutos asequibles.',
    calls: 'Predicciones en directo', call_pts: 'puntos de predicción', my_calls: 'Mis predicciones', no_calls: 'Aún no hay predicciones.',
    calls_hint: 'Predice lo que va a pasar. Las cuotas salen de los modelos en directo; un acierto paga 10 ÷ su probabilidad. Las predicciones nunca cambian los puntos Fantasy.',
    fx_meta: 'Jornada {md} · {cost} M€ de {budget} M€ · banco {bank} M€', fx_unavailable: 'Fantasy usa la temporada de la Aurora League: elige un partido de una jornada.',
    in_match: 'Juega este partido', not_playing: 'No juega este partido', advice: 'Consejo', asking: 'El asesor está analizando a {name}…',
    next_goal: 'Próximo gol', no_more: 'No habrá más goles', scorer: 'Marca', booked: 'Ve tarjeta', pays: 'paga {n}',
    won: 'acertada', lost: 'fallada', open_call: 'abierta', calls_closed: 'Predicciones cerradas: el partido ha terminado.',
    replacements: 'Sustitutos asequibles', transfer_in: 'Fichar', ppm: '{p} pts/partido previstos',
    v_HOLD: 'Mantener', v_WATCH: 'Vigilar', v_SELL: 'Vender', st_scout: 'Ojeador (reglas)', st_advisor: 'Asesor',
    r_appearance: 'Jugó', r_appearance_60: '60+ min', r_goal: 'Gol', r_assist: 'Asistencia', r_clean_sheet: 'Portería a cero',
    r_conceded: 'Goles encajados', r_saves: 'Paradas', r_defensive: 'Trabajo defensivo', r_yellow: 'Amarilla', r_red: 'Roja',
    r_own_goal: 'Gol en propia', r_bonus: 'Bonus', provisional: 'provisional', captain: 'Capitán',
    f_form: 'forma', f_pts: 'pts', transferred: 'Sale {out}, entra {in}.',
    v_pitch: 'Campo', v_list: 'Lista', bench: 'Banquillo', swap: 'Meter en el once', swap_hint: 'Pulsa un titular resaltado para meter a {name}.',
    fixtures: 'Próximos partidos', fdr_legend: 'Color = dificultad del rival: verde fácil, rojo difícil. H casa, A fuera. Ø = dificultad media.',
    md_short: 'J', make_captain: 'Hacer capitán', close: 'Cerrar', radar: 'Fortalezas y debilidades', scorecard: 'Ficha',
    radar_hint: 'Percentil frente a los {n} jugadores {pos} con más de 270 minutos (100 = el mejor de la liga).',
    radar_few: 'Aún no tiene minutos suficientes (menos de {m}) para compararlo con justicia.',
    hexagon: 'Análisis de atributos', attributes: 'Atributos', hx_rating: 'Valoración (atributos)', hx_season: 'Esta temporada (percentil por posición)',
    measured: 'Medido en los partidos de esta temporada: percentil frente a su posición (1–99)',
    attrs_hint: '◉ = medido en los partidos de esta temporada, como percentil frente a jugadores de su posición (requiere {m}+ minutos). El resto son atributos de ojeo (1–99).',
    hx_pac: 'Ritmo', hx_sho: 'Tiro', hx_pas: 'Pase', hx_dri: 'Regate', hx_def: 'Defensa', hx_phy: 'Físico',
    hx_div: 'Estirada', hx_han: 'Blocaje', hx_kic: 'Saque', hx_ref: 'Reflejos', hx_spd: 'Velocidad', hx_pos: 'Colocación',
    sa_pace: 'Velocidad', sa_top_speed: 'Velocidad punta', sa_sprints90: 'Sprints por 90', sa_finishing: 'Definición', sa_shot_power: 'Potencia de tiro',
    sa_positioning: 'Colocación', sa_shots90: 'Tiros por 90', sa_xg90: 'xG por 90', sa_passing: 'Pase', sa_vision: 'Visión',
    sa_pass_acc: 'Precisión de pase', sa_kp90: 'Pases clave por 90', sa_prog90: 'Acciones progresivas por 90', sa_dribbling: 'Regate',
    sa_composure: 'Compostura', sa_drb90: 'Regates por 90', sa_tackling: 'Entradas', sa_aerial: 'Juego aéreo', sa_def90: 'Acciones defensivas por 90',
    sa_stamina: 'Resistencia', sa_dist90: 'Distancia por 90', sa_availability: 'Disponibilidad', sa_keeping: 'Portería', sa_saves90: 'Paradas por 90',
    sa_clean_sheets: 'Porterías a cero', sa_conceded90: 'Goles encajados por 90 (menos = más alto)', sa_save_pct: 'Porcentaje de paradas',
    st_starter: 'Titular', st_rotation: 'Rotación', st_bench: 'Suplente', st_not_playing: 'No juega', st_unknown: 'Sin datos aún',
    form_pct_hint: 'Forma en las 3 últimas jornadas, como percentil entre jugadores de su posición',
    last3_md: 'últimas 3 J', price: 'Precio', p_points: 'Puntos', p_avg: 'Media', p_last3: 'Media últimos 3', p_home: 'Media en casa', p_away: 'Media fuera',
    p_proj: 'Previsión', p_apps: '{m} partidos · {s} de titular · {min} minutos', role: 'Posición habitual', by_md: 'Puntos por jornada',
    last5: 'Últimos 5 partidos', next5: 'Próximos 5 partidos', season_stats: 'Estadísticas de la temporada', did_not_play: 'no jugó', sub_on: 'suplente',
    s_goals: 'Goles', s_assists: 'Asistencias', s_def: 'Acciones defensivas', s_saves: 'Paradas', s_cards: 'Amarillas / rojas',
    foot_left: 'zurdo', foot_right: 'diestro', foot_both: 'ambidiestro',
  },
};
const CAUSE = { en: { goal: 'goal', card: 'card', shot: 'shot' }, es: { goal: 'gol', card: 'tarjeta', shot: 'tiro' } };

// ------------------------------------------------------------------ state
const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
const S = {
  ws: null, meta: null, state: null, series: [], players: {}, keyEvents: [], passes: [], timeline: new Map(),
  mode: params.get('mode') || 'broadcast', paused: false, done: false, sort: { key: 'rating', dir: -1 },
  passSide: 'home', clubs: [], catalogue: [], narr: new Map(), recaps: {}, newsroom: null,
  fx: { md: null, players: {}, live: {}, quotes: null, calls: null, advice: null, meta: null },
};
let viewerId = 'v-' + Math.random().toString(36).slice(2, 12);
try { viewerId = localStorage.getItem('matchlens.viewer') || viewerId; localStorage.setItem('matchlens.viewer', viewerId); } catch (e) { /* storage unavailable */ }
const PREFS_KEY = 'matchlens.prefs';
let prefs = { lang: params.get('lang') || 'en', favClub: null, favPlayer: null };
try { prefs = { ...prefs, ...JSON.parse(localStorage.getItem(PREFS_KEY) || '{}') }; } catch (e) { /* storage unavailable */ }
if (params.get('lang')) prefs.lang = params.get('lang');

function t(key, vars = {}) {
  const s = (I18N[prefs.lang] || I18N.en)[key] ?? I18N.en[key] ?? key;
  return s.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? '');
}
const pct = v => Math.round(100 * v);
const sideOf = teamId => S.meta && (S.meta.home.team_id === teamId ? 'home' : S.meta.away.team_id === teamId ? 'away' : null);
const abbr = side => S.meta ? S.meta[side]?.abbr || '' : '';
const isFavPlayer = pid => pid && pid === prefs.favPlayer;
const favSide = () => sideOf(prefs.favClub);

function applyI18n() {
  document.documentElement.lang = prefs.lang;
  document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
  $('pause').textContent = S.paused ? t('resume') : t('pause');
}

// ------------------------------------------------------------------ pitch drawing
const NS = 'http://www.w3.org/2000/svg';
function pitchMarkup(stripes = true) {
  let s = '';
  if (stripes) for (let i = 0; i < 14; i++) s += `<rect x="${i * 7.5}" y="0" width="7.5" height="68" fill="${i % 2 ? 'var(--pitch)' : 'var(--pitch-2)'}"/>`;
  else s += `<rect x="0" y="0" width="105" height="68" fill="#EEF2EC"/>`;
  const c = stripes ? 'rgba(255,255,255,.85)' : '#AEB8AE';
  s += `<g fill="none" stroke="${c}" stroke-width=".35">
    <rect x="0" y="0" width="105" height="68"/><line x1="52.5" y1="0" x2="52.5" y2="68"/>
    <circle cx="52.5" cy="34" r="9.15"/><rect x="0" y="13.84" width="16.5" height="40.32"/><rect x="88.5" y="13.84" width="16.5" height="40.32"/>
    <rect x="0" y="24.84" width="5.5" height="18.32"/><rect x="99.5" y="24.84" width="5.5" height="18.32"/>
    <path d="M16.5 26.7 A9.15 9.15 0 0 1 16.5 41.3"/><path d="M88.5 26.7 A9.15 9.15 0 0 0 88.5 41.3"/>
    <rect x="-1.6" y="30.34" width="1.6" height="7.32"/><rect x="105" y="30.34" width="1.6" height="7.32"/></g>
    <g fill="${c}"><circle cx="11" cy="34" r=".35"/><circle cx="94" cy="34" r=".35"/><circle cx="52.5" cy="34" r=".35"/></g>`;
  return s;
}
function initPitches() {
  $('pitch').innerHTML = pitchMarkup(true) + '<g id="trails"></g><circle id="ball" class="ball" cx="52.5" cy="34" r=".9" fill="#fff" stroke="#14213D" stroke-width=".25"/>';
  $('shotmap').innerHTML = pitchMarkup(false) + '<g id="shots"></g>';
  $('passmap').innerHTML = pitchMarkup(false) + '<g id="passlines"></g>';
}
const pctX = x => ((x + 2) / 109) * 100;
const pctY = y => ((y + 2) / 72) * 100;

// ------------------------------------------------------------------ connection
async function loadCatalogue() {
  S.catalogue = await (await fetch('/api/matches')).json();
  const clubs = new Map();
  S.catalogue.forEach(m => { clubs.set(m.home.team_id, m.home); clubs.set(m.away.team_id, m.away); });
  S.clubs = [...clubs.values()].sort((a, b) => a.name.localeCompare(b.name));
  $('match').innerHTML = S.catalogue.map(m =>
    `<option value="${m.match_id}">${m.source === 'demo' ? 'Demo · ' : 'Matchday ' + (m.competition.matchday || '') + ' · '}${m.home.name} v ${m.away.name}</option>`).join('');
  const want = params.get('match');
  if (want && S.catalogue.some(m => m.match_id === want)) $('match').value = want;
  else if (prefs.favClub) {
    const fm = S.catalogue.find(m => m.home.team_id === prefs.favClub || m.away.team_id === prefs.favClub);
    if (fm) $('match').value = fm.match_id;
  }
  // URL values that are not in the drop-downs are added, so any speed / start minute can be linked to
  for (const [key, el, label] of [['speed', 'speed', v => `${v}×`], ['from', 'from', v => `From ${v}'`]]) {
    const v = params.get(key);
    if (v == null || isNaN(+v)) continue;
    if (![...$(el).options].some(o => o.value === v)) $(el).add(new Option(label(v), v));
    $(el).value = v;
  }
}

function connect(restart = false) {
  if (S.ws) { S.ws.onclose = null; S.ws.close(); }
  resetView();
  const id = $('match').value, proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const url = `${proto}://${location.host}/ws/${id}?speed=${+$('speed').value || 60}&from_minute=${+$('from').value || 0}&restart=${restart ? 1 : 0}&lang=${prefs.lang}&viewer=${encodeURIComponent(viewerId)}`;
  $('conn').textContent = t('connecting');
  const ws = new WebSocket(url);
  S.ws = ws;
  ws.onmessage = e => handle(JSON.parse(e.data));
  ws.onclose = () => { if (S.ws === ws) $('conn').textContent = t('disconnected'); };
}

function resetView() {
  S.meta = null; S.state = null; S.series = []; S.players = {}; S.keyEvents = []; S.passes = []; S.timeline = new Map(); S.done = false;
  S.narr = new Map(); S.recaps = {}; if ($('notes')) $('notes').innerHTML = '';
  ['feedB', 'liveEvents', 'timeline'].forEach(id => { $(id).innerHTML = ''; });
  $('tags').innerHTML = ''; document.getElementById('trails')?.replaceChildren();
}

function handle(m) {
  switch (m.type) {
    case 'hello': onHello(m.payload); break;
    case 'state': S.state = m.payload; renderState(); break;
    case 'event': onEvent(m.payload, m); break;
    case 'alert': onAlert(m); break;
    case 'win_prob_swing': onSwing(m); break;
    case 'minute': S.series.push(m.payload); if (S.mode === 'analyst') renderCharts(); break;
    case 'players': S.players = m.payload.players; if (S.mode === 'analyst') renderPlayers(); if (S.mode === 'fan') renderFocus(); break;
    case 'session': onSession(m.payload); break;
    case 'narrative': onNarrative(m.payload); break;
    case 'recap': onRecap(m.payload); break;
    case 'fantasy': S.fx.live = m.payload.points || {}; S.fx.quotes = m.payload.quotes; if (S.mode === 'fantasy') renderFantasy(); break;
    case 'calls': S.fx.calls = m.payload; if (S.mode === 'fantasy') renderCalls(); break;
    case 'error': if (S.mode === 'fantasy') { $('fxCalls').insertAdjacentHTML('afterbegin', `<li class="lost">${esc(m.payload.message)}</li>`); } else $('conn').textContent = m.payload.message; break;
  }
}

function onHello(p) {
  resetView();
  S.meta = p; S.state = p.state; S.series = p.series || []; S.players = p.players || {};
  S.keyEvents = p.key_events || []; S.passes = p.recent_passes || [];
  const h = p.home.colors, a = p.away.colors;
  const awayCol = a.primary.toLowerCase() === h.primary.toLowerCase() ? a.secondary : a.primary;
  document.documentElement.style.setProperty('--home', h.primary);
  document.documentElement.style.setProperty('--away', awayCol);
  $('bugH').textContent = p.home.abbr; $('bugA').textContent = p.away.abbr;
  ['wsH', 'tugH'].forEach(id => { $(id).style.background = 'var(--home)'; });
  ['wsA', 'tugA'].forEach(id => { $(id).style.background = 'var(--away)'; });
  $('crH').style.background = 'var(--home)'; $('crH').textContent = p.home.abbr;
  $('crA').style.background = 'var(--away)'; $('crA').textContent = p.away.abbr;
  $('fnH').textContent = p.home.name + (prefs.favClub === p.home.team_id ? ' ★' : '');
  $('fnA').textContent = p.away.name + (prefs.favClub === p.away.team_id ? ' ★' : '');
  const segs = $('passTeam').querySelectorAll('button');
  segs[0].textContent = p.home.abbr; segs[1].textContent = p.away.abbr;
  (p.recent_alerts || []).forEach(env => (env.type === 'alert' ? onAlert(env, true) : onSwing(env, true)));
  fillPrefsPlayers();
  S.newsroom = p.newsroom || null; renderAiBadge();
  (p.narratives || []).forEach(n => (n.kind === 'half_time' || n.kind === 'full_time') ? onRecap(n, true) : onNarrative(n, true));
  const sess = p.state.session || {};
  onSession({ speed: sess.speed, paused: sess.paused, done: sess.done });
  onFantasyHello(p.fantasy);
  renderState(); renderAll();
}

function onSession(p) {
  S.paused = p.paused; S.done = p.done;
  $('pause').textContent = S.paused ? t('resume') : t('pause');
  $('conn').textContent = p.done ? t('full_time') : p.paused ? t('paused') : `${t('live')} · ${p.speed}×`;
}

// ------------------------------------------------------------------ events → broadcast stage
const TAGGED = new Set(['pass', 'shot', 'sprint', 'tackle', 'dribble', 'interception', 'goalkeeper', 'clearance']);
let lastTagAt = 0;
function onEvent(ev, env) {
  if (!S.meta) return;
  if (['shot', 'goal', 'card', 'substitution'].includes(ev.type)) S.keyEvents.push(ev);
  if (ev.type === 'pass' && ev.outcome === 'complete') { S.passes.push(ev); if (S.passes.length > 400) S.passes.shift(); }
  if (S.mode === 'analyst' && (ev.type === 'shot' || ev.type === 'goal')) renderShotMap();
  if (S.mode !== 'broadcast') return;
  const loc = ev.location_abs, end = ev.end_location_abs || loc;
  if (end && ev.type !== 'sprint') moveBall(end);
  if (ev.type === 'pass' && loc && end) drawTrail(loc, end, ev.outcome === 'complete' ? 'rgba(255,255,255,.75)' : 'rgba(242,183,5,.9)');
  if (ev.type === 'shot' && loc) drawTrail(loc, end, '#F2B705', true);
  if (loc && TAGGED.has(ev.type) && ev.player_name) {
    const now = performance.now();
    const fav = isFavPlayer(ev.player_id);
    let extra = '';
    if (ev.type === 'sprint') { if (ev.details.top_speed_kmh < 31 && !fav) return; extra = `${ev.details.top_speed_kmh.toFixed(1)} km/h`; }
    if (ev.type === 'shot') extra = `xG ${ev.details.xg.toFixed(2)} · ${Math.round(ev.details.shot_speed_kmh)} km/h`;
    if (ev.type === 'pass' && ev.derived?.pass_difficulty >= 70 && ev.outcome === 'complete') extra = `${t('t_diff').split(' ')[0]} ${ev.derived.pass_difficulty}`;
    if (!extra && !fav && now - lastTagAt < 450) return;     // keep the picture readable at high speed
    lastTagAt = now;
    showTag(loc, ev, extra, fav);
  }
  if (['shot', 'goal', 'card', 'substitution', 'dribble', 'tackle'].includes(ev.type) || isFavPlayer(ev.player_id)) addLiveEvent(ev, env);
}
function moveBall([x, y]) { const b = $('ball'); b.setAttribute('cx', x); b.setAttribute('cy', y); }
function drawTrail([x1, y1], [x2, y2], color, thick) {
  const g = $('trails'), l = document.createElementNS(NS, 'line');
  l.setAttribute('x1', x1); l.setAttribute('y1', y1); l.setAttribute('x2', x2); l.setAttribute('y2', y2);
  l.setAttribute('stroke', color); l.setAttribute('stroke-width', thick ? '.6' : '.3'); l.setAttribute('stroke-linecap', 'round');
  l.style.transition = 'opacity 1.4s'; g.appendChild(l);
  while (g.childNodes.length > 6) g.removeChild(g.firstChild);
  setTimeout(() => { l.style.opacity = '0'; }, 900);
}
function showTag([x, y], ev, extra, fav) {
  const el = document.createElement('div');
  el.className = 'tag' + (fav ? ' fav' : '');
  el.style.left = pctX(x) + '%'; el.style.top = pctY(y) + '%';
  el.style.setProperty('--team', `var(--${ev.team_side})`);
  el.innerHTML = `${fav ? '★ ' : ''}${ev.shirt ?? ''} ${ev.player_name}${extra ? `<span class="spd">${extra}</span>` : ''}`;
  const box = $('tags'); box.appendChild(el);
  while (box.childNodes.length > 4) box.removeChild(box.firstChild);
  setTimeout(() => el.classList.add('fade'), extra ? 2200 : 1300);
  setTimeout(() => el.remove(), extra ? 2800 : 1900);
}
function addLiveEvent(ev, env) {
  const li = document.createElement('li');
  if (isFavPlayer(ev.player_id)) li.className = 'fav';
  const d = ev.details || {};
  let txt = `${ev.player_name || ''} (${abbr(ev.team_side)}) · ${ev.type.replace('_', ' ')}`;
  if (ev.type === 'shot') txt += ` · ${ev.outcome.replace('_', ' ')} · xG ${d.xg.toFixed(2)}`;
  if (ev.type === 'pass' && ev.derived) txt += ` → ${d.recipient_name || ''} · ${d.length_m} m · ${ev.derived.pass_difficulty}`;
  li.innerHTML = `<span class="m">${env.display_minute}</span><span class="x">${txt}</span>`;
  const ul = $('liveEvents'); ul.prepend(li);
  while (ul.childNodes.length > 40) ul.removeChild(ul.lastChild);
}

// ------------------------------------------------------------------ alerts → lower thirds, feeds, fan timeline
const lowerQueue = [];
let lowerBusy = false;
function onAlert(env, replay = false) {
  const p = env.payload, d = p.data || {}, side = p.side;
  const team = S.meta ? S.meta[side]?.short_name || abbr(side) : '';
  const v = { player: p.player_name, team, kmh: Math.round(d.top_speed_kmh || d.shot_speed_kmh || 0),
              d: d.difficulty, to: d.recipient, m: Math.round(d.length_m || 0), km: d.km, on: d.on, off: d.off,
              xg: (d.xg ?? 0).toFixed(2), pct: pct(d.xg ?? 0) };
  const fav = isFavPlayer(p.player_id);
  let title = null, sub = '', key = null, timeline = false, why = '';
  switch (p.alert) {
    case 'goal': title = t('goal', v); key = t('goal_k'); timeline = true;
      why = (d.assist ? t('assist', { name: d.assist }) + ' ' : '') + t('goal_why', v); sub = why; break;
    case 'card': title = t('card_' + d.card, v); key = t('card_k'); timeline = true; break;
    case 'substitution': title = t('sub', v); key = t('sub_k'); timeline = true; break;
    case 'big_chance_missed': title = t('big_chance', v); why = t('big_chance_why', v); sub = why; key = 'xG'; timeline = true; break;
    case 'rocket_shot': title = t('rocket', v); key = t('rocket_k'); timeline = fav; break;
    case 'speed': title = t('speed', v); sub = d.match_record ? t('speed_record') : ''; key = t('speed_k'); timeline = fav || d.match_record; break;
    case 'hard_pass': title = t('hard_pass', v); sub = (d.reasons || []).join(', '); key = t('hard_pass_k'); timeline = fav; break;
    case 'long_pass': title = t('long_pass', v); timeline = fav; break;
    case 'distance': title = t('distance', v); timeline = fav; break;
  }
  if (!title) return;
  const item = { id: p.event_id || `${p.alert}-${env.seq}`, minute: env.display_minute, title, why, kind: p.alert, fav, side };
  if (['goal', 'card', 'substitution', 'big_chance_missed'].includes(p.alert) || fav) addFeed('feedB', item);
  if (timeline) addTimeline(item);
  const lowerWorthy = ['goal', 'card', 'substitution', 'big_chance_missed', 'rocket_shot'].includes(p.alert)
    || (p.alert === 'speed' && d.match_record) || (p.alert === 'hard_pass' && (fav || d.difficulty >= 85)) || fav;
  if (!replay && lowerWorthy && key) queueLower({ key, title, sub, side, goal: p.alert === 'goal' });
}
function onSwing(env, replay = false) {
  const p = env.payload;
  if (!S.meta) return;
  const lead = p.swing_pts.home >= p.swing_pts.away ? 'home' : 'away';
  const txt = t('swing', { team: S.meta[lead].short_name, b: pct(p.before[lead]), a: pct(p.after[lead]) });
  const existing = S.timeline.get(p.cause_event_id);
  if (existing) { existing.why = (existing.why ? existing.why + ' ' : '') + txt; renderTimeline(); }
  else if (p.cause !== 'shot' || Math.max(...Object.values(p.swing_pts).map(Math.abs)) >= 8) {
    addTimeline({ id: p.cause_event_id + '-s', minute: env.display_minute, title: t('swing_title', { cause: CAUSE[prefs.lang]?.[p.cause] || p.cause }), why: txt, kind: 'swing', side: lead });
  }
  if (!replay && p.cause !== 'goal' && Math.max(...Object.values(p.swing_pts).map(Math.abs)) >= 10)
    queueLower({ key: t('swing_k'), title: t('swing_title', { cause: CAUSE[prefs.lang]?.[p.cause] || p.cause }), sub: txt, side: lead });
}
function addFeed(id, item) {
  const li = document.createElement('li');
  li.dataset.id = item.id;
  li.className = (item.kind === 'goal' ? 'goal ' : '') + (item.fav ? 'fav' : '');
  li.innerHTML = `<span class="m">${item.minute}</span><span class="x">${item.title}</span>`;
  $(id).prepend(li);
}
function addTimeline(item) { S.timeline.set(item.id, item); renderTimeline(); }
function renderTimeline() {
  const items = [...S.timeline.values()].reverse();
  $('timeline').innerHTML = items.map(i => {
    const n = S.narr.get(i.id), tx = n && nt(n);
    const title = (i.kind === 'read' && tx) ? tx.caption : i.title;
    const why = tx ? esc(tx.fan) : i.why;
    return `<li class="${i.kind === 'goal' ? 'goal' : ''} ${i.fav ? 'fav' : ''}">
    <span class="m">${i.minute}</span><div><div class="what">${esc(title)}${n ? srcBadge(n) : ''}</div>${why ? `<div class="why">${why}</div>` : ''}</div></li>`;
  }).join('');
}
function queueLower(item) { lowerQueue.push(item); if (lowerQueue.length > 4) lowerQueue.splice(0, lowerQueue.length - 4); if (!lowerBusy) nextLower(); }
function nextLower() {
  const item = lowerQueue.shift();
  const el = $('lower');
  if (!item) { lowerBusy = false; return; }
  lowerBusy = true;
  el.classList.toggle('goal', !!item.goal);
  el.style.setProperty('--team', `var(--${item.side || 'home'})`);
  $('lowK').textContent = item.key; $('lowT').textContent = item.title; $('lowS').textContent = item.sub || '';
  el.classList.add('show');
  setTimeout(() => { el.classList.remove('show'); setTimeout(nextLower, 500); }, item.goal ? 5000 : 3400);
}

// ------------------------------------------------------------------ newsroom narratives
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const nt = n => (n.texts && (n.texts[prefs.lang] || n.texts.en)) || {};
function srcBadge(n) {
  if (n.status !== 'final' || n.source === 'templates') return `<span class="src auto">${t('auto_badge')}</span>`;
  if (n.fallback) return `<span class="src fb">${t('fallback_badge')}</span>`;
  return `<span class="src" title="${esc(n.source)}${n.model ? ' · ' + esc(n.model) : ''}">${t('ai_badge')}</span>`;
}
function traceHtml(n) {
  if (!n.trace || !n.trace.length) return '';
  const steps = n.trace.map(s => {
    const base = s.step.startsWith('localiser_') ? `${t('st_localiser')} (${s.step.slice(10)})` : t('st_' + s.step);
    let extra = '';
    if (s.tool_calls && s.tool_calls.length) extra += ` · ${t('tools')}: ${s.tool_calls.join(', ')}`;
    if (s.attempt > 1) extra += ` · ${t('retry')} ${s.attempt - 1}`;
    if (s.issues && s.issues.length) extra += ` · <span class="bad">${esc(s.issues[0])}</span>`;
    if (s.ms) extra += ` · ${(s.ms / 1000).toFixed(1)} ${t('secs')}`;
    return `<li>${s.ok ? '✓' : '✗'} ${esc(base)}${extra}</li>`;
  }).join('');
  return `<details class="trace"><summary>${t('how_made')} · ${esc(n.source)}${n.model ? ' · ' + esc(n.model) : ''} · ${(n.latency_ms / 1000).toFixed(1)} ${t('secs')}</summary><ol>${steps}</ol></details>`;
}
function renderAiBadge() {
  const nr = S.newsroom;
  $('aiBadge').textContent = nr && nr.enabled ? t('ai_on', { src: nr.source + (nr.model ? ' · ' + nr.model : '') }) : t('ai_off');
}
function onNarrative(n, replay = false) {
  const first = !S.narr.has(n.moment_id);
  S.narr.set(n.moment_id, n);
  const tx = nt(n);
  // fan story: AI explanation replaces the template "why"; a state-of-play read becomes its own entry
  if (n.kind === 'state_of_play' && !S.timeline.has(n.moment_id))
    S.timeline.set(n.moment_id, { id: n.moment_id, minute: n.display_minute, title: tx.caption, kind: 'read' });
  renderTimeline();
  // broadcast key moments: commentary under the matching moment
  let li = $('feedB').querySelector(`li[data-id="${CSS.escape(n.moment_id)}"]`);
  if (!li && n.kind === 'state_of_play') {
    addFeed('feedB', { id: n.moment_id, minute: n.display_minute, title: tx.caption, kind: 'read' });
    li = $('feedB').querySelector(`li[data-id="${CSS.escape(n.moment_id)}"]`);
  }
  if (li) {
    let ai = li.querySelector('.ai');
    if (!ai) { ai = document.createElement('div'); ai.className = 'ai'; li.appendChild(ai); }
    ai.innerHTML = esc(tx.commentary) + srcBadge(n);
  }
  // analyst notes
  renderNotes();
  // on-screen graphic for a state-of-play read (the first, instant version)
  if (!replay && first && n.kind === 'state_of_play')
    queueLower({ key: t('sop_k'), title: tx.caption, sub: tx.fan, side: (S.state && S.state.momentum < 0) ? 'away' : 'home' });
}
function renderNotes() {
  const items = [...S.narr.values()].reverse();
  $('notes').innerHTML = items.map(n => { const tx = nt(n);
    return `<li><span class="m">${esc(n.display_minute)}</span><span class="cap">${esc(tx.caption)}</span>${srcBadge(n)}
      <p>${esc(tx.analyst)}</p>${n.status === 'final' ? traceHtml(n) : ''}</li>`; }).join('');
}
function onRecap(n, replay = false) {
  const first = !S.recaps[n.kind];
  S.recaps[n.kind] = n;
  renderRecap();
  const tx = nt(n);
  if (!replay && first) queueLower({ key: t(n.kind === 'full_time' ? 'ft_k' : 'ht_k'), title: tx.headline, sub: (tx.player_of_the_match || {}).name ? `${t(n.kind === 'full_time' ? 'potm' : 'standout')}: ${tx.player_of_the_match.name}` : '', side: 'home' });
}
function renderRecap() {
  const n = S.recaps.full_time || S.recaps.half_time;
  if (!n) return;
  const tx = nt(n), potm = tx.player_of_the_match || {};
  const html = `<div class="recap"><h3>${esc(tx.headline)}${srcBadge(n)}</h3>
    <p><strong>${t('script')}.</strong> ${esc(tx.studio_script)}</p>
    ${potm.name ? `<div class="potm"><strong>${t(n.kind === 'full_time' ? 'potm' : 'standout')}: ${esc(potm.name)}</strong> – ${esc(potm.reason)}</div>` : ''}
    ${tx.article && tx.article !== tx.studio_script ? `<p><strong>${t('article')}.</strong> ${esc(tx.article)}</p>` : ''}
    <p class="social">${esc(tx.social)}</p>${n.status === 'final' ? traceHtml(n) : ''}</div>`;
  $('recapA').innerHTML = html; $('recapF').innerHTML = html; $('recapFCard').hidden = false;
}

// ------------------------------------------------------------------ state rendering
function renderState() {
  const s = S.state;
  if (!s || !S.meta) return;
  const sc = `${s.score.home}–${s.score.away}`;
  $('bugSc').textContent = sc; $('bugClk').textContent = s.finished ? 'FT' : s.display_minute;
  if (s.win_prob) {
    const w = s.win_prob;
    $('wsH').style.flexGrow = Math.max(w.home, .001); $('wsD').style.flexGrow = Math.max(w.draw, .001); $('wsA').style.flexGrow = Math.max(w.away, .001);
    $('wplabel').textContent = `${abbr('home')} ${pct(w.home)}%  ·  ${t('draw')} ${pct(w.draw)}%  ·  ${abbr('away')} ${pct(w.away)}%`;
  }
  const mo = s.momentum / 100;
  $('momoBar').style.left = mo >= 0 ? '50%' : `${50 + 50 * mo}%`; $('momoBar').style.width = `${50 * Math.abs(mo)}%`;
  $('momoBar').style.background = mo >= 0 ? 'var(--home)' : 'var(--away)';
  $('momoTxt').textContent = `${t('momentum')}: ${Math.abs(s.momentum) < 15 ? t('level') : t('on_top', { team: abbr(mo >= 0 ? 'home' : 'away') })}`;
  const statsHtml = statRows(s);
  $('statsB').innerHTML = statsHtml; $('statsA').innerHTML = statsHtml;
  renderFan();
}
function statRows(s) {
  const H = s.teams.home, A = s.teams.away, f = (v, d = 0) => (v ?? 0).toFixed(d);
  const rows = [
    [f(H.xg, 2), t('s_xg'), f(A.xg, 2)],
    [`${f(H.shots)} (${f(H.shots_on_target)})`, t('s_shots'), `${f(A.shots)} (${f(A.shots_on_target)})`],
    [`${Math.round(s.possession.total[0])}%`, t('s_poss'), `${Math.round(s.possession.total[1])}%`],
    [`${Math.round(s.possession.last5[0])}%`, t('s_poss5'), `${Math.round(s.possession.last5[1])}%`],
    [`${Math.round(s.field_tilt.last10[0])}%`, t('s_tilt'), `${Math.round(s.field_tilt.last10[1])}%`],
    [H.pass_accuracy_pct != null ? `${Math.round(H.pass_accuracy_pct)}%` : '–', t('s_pass'), A.pass_accuracy_pct != null ? `${Math.round(A.pass_accuracy_pct)}%` : '–'],
    [s.ppda.home, t('s_ppda'), s.ppda.away],
    [f(H.corners), t('s_corners'), f(A.corners)],
    [`${f(H.fouls)} / ${f(H.yellow)}`, t('s_fouls'), `${f(A.fouls)} / ${f(A.yellow)}`],
    [f(H.distance_km, 1), t('s_dist'), f(A.distance_km, 1)],
  ];
  return rows.map(r => `<tr><td>${r[0]}</td><td class="l">${r[1]}</td><td>${r[2]}</td></tr>`).join('');
}

// ------------------------------------------------------------------ fan view
function renderFan() {
  const s = S.state;
  if (!s || !S.meta) return;
  $('fScore').textContent = `${s.score.home} – ${s.score.away}`;
  $('fMin').textContent = s.finished ? t('full_time') : `${s.display_minute} · ${s.period === 1 ? t('first_half') : t('second_half')}`;
  $('fHeadline').textContent = headline(s);
  if (s.win_prob) {
    const w = s.win_prob;
    $('tugH').style.flexGrow = Math.max(w.home, .001); $('tugD').style.flexGrow = Math.max(w.draw, .001); $('tugA').style.flexGrow = Math.max(w.away, .001);
    $('tugLH').textContent = `${S.meta.home.short_name} ${pct(w.home)}%`; $('tugLD').textContent = `${t('draw')} ${pct(w.draw)}%`;
    $('tugLA').textContent = `${S.meta.away.short_name} ${pct(w.away)}%`;
  }
  renderFocus();
}
function headline(s) {
  const name = side => S.meta[side].short_name;
  const score = `${s.score.home}–${s.score.away}`;
  if (s.finished) {
    if (s.score.home === s.score.away) return t('h_ft_draw', { score });
    return t('h_ft_win', { team: name(s.score.home > s.score.away ? 'home' : 'away'), score: s.score.home > s.score.away ? score : `${s.score.away}–${s.score.home}` });
  }
  if (!s.win_prob) return t('h_pre');
  const parts = [];
  if (Math.abs(s.momentum) >= 30) {
    const side = s.momentum > 0 ? 'home' : 'away';
    parts.push(t('h_on_top', { team: name(side), poss: Math.round(s.possession.last5[side === 'home' ? 0 : 1]) }));
  } else parts.push(t('h_even'));
  if (s.chaos >= 55) parts.push(t('h_chaos'));
  const w = s.win_prob, fav = favSide();
  const best = Object.entries(w).sort((a, b) => b[1] - a[1])[0];
  if (fav && best[0] !== fav && best[0] !== 'draw') parts.push(t('h_fav', { team: name(fav), p: pct(w[fav]) }));
  else if (best[0] === 'draw') parts.push(t('h_draw', { p: pct(best[1]) }));
  else parts.push(t('h_fav', { team: name(best[0]), p: pct(best[1]) }));
  return parts.join(' ');
}
function renderFocus() {
  const card = $('focusCard');
  if (!S.meta) return;
  const pid = prefs.favPlayer;
  const all = [...S.meta.home.starting_xi.map(p => ({ ...p, side: 'home' })), ...S.meta.home.bench.map(p => ({ ...p, side: 'home', bench: true })),
               ...S.meta.away.starting_xi.map(p => ({ ...p, side: 'away' })), ...S.meta.away.bench.map(p => ({ ...p, side: 'away', bench: true }))];
  const who = all.find(p => p.player_id === pid);
  if (!who) {
    card.innerHTML = `<p style="margin:0 0 10px">${t('follow_prompt')}</p><button class="seg" style="padding:6px 12px;cursor:pointer" onclick="openPrefs()">${t('follow_btn')}</button>`;
    return;
  }
  const P = S.players[pid];
  const status = !P ? (who.bench ? t('on_bench') : '') : P.on_pitch === false ? t('subbed_off') : '';
  const v = P || {};
  const f = (x, d = 0) => (x ?? 0).toFixed(d);
  card.innerHTML = `<div class="focus"><div class="shirt" style="background:var(--${who.side})">${who.shirt}</div>
    <div><h2 style="margin:0">★ ${who.name}</h2><div class="hint">${who.position} · ${S.meta[who.side].name}${status ? ' · ' + status : ''}</div></div></div>
    <dl><div><dt>${t('f_rating')}</dt><dd>${P ? f(v.rating, 1) : '–'}</dd></div>
    <div><dt>${t('f_passes')}</dt><dd>${f(v.passes_complete)}/${f(v.passes)}</dd></div>
    <div><dt>${t('f_xg')}</dt><dd>${f(v.xg, 2)}</dd></div><div><dt>${t('f_shots')}</dt><dd>${f(v.shots)}</dd></div>
    <div><dt>${t('f_kp')}</dt><dd>${f(v.key_passes)}</dd></div><div><dt>${t('f_tk')}</dt><dd>${f(v.tackles_won)}</dd></div>
    <div><dt>${t('f_dist')}</dt><dd>${f((v.distance_m || 0) / 1000, 1)} km</dd></div><div><dt>${t('f_top')}</dt><dd>${f(v.top_speed_kmh, 1)}</dd></div></dl>`;
}

// ------------------------------------------------------------------ analyst view
function axisX(x0, x1, w, pad) { return m => pad.l + (m - x0) / (x1 - x0) * (w - pad.l - pad.r); }
function goalsMarks(sx, h, pad) {
  return S.keyEvents.filter(e => e.type === 'goal').map(e => {
    const x = sx(e.match_time_s / 60);
    return `<line x1="${x}" y1="${pad.t}" x2="${x}" y2="${h - pad.b}" stroke="#14213D" stroke-dasharray="2 3" stroke-width="1"/>
            <text x="${x + 3}" y="${pad.t + 10}">${e.player_name}</text>`;
  }).join('');
}
function xTicks(sx, h, pad, maxM) {
  let s = '';
  for (let m = 0; m <= maxM; m += 15) s += `<text x="${sx(m)}" y="${h - 6}" text-anchor="middle">${m}'</text>`;
  return s;
}
function renderCharts() {
  const pts = S.series.filter(p => p.win_prob);
  const maxM = Math.max(95, ...S.series.map(p => p.t_min || 0));
  // win probability (stacked area)
  { const w = 640, h = 200, pad = { l: 34, r: 8, t: 8, b: 22 }, sx = axisX(0, maxM, w, pad), sy = v => pad.t + (1 - v) * (h - pad.t - pad.b);
    let svg = '';
    if (pts.length > 1) {
      const xs = pts.map(p => sx(p.t_min));
      const top = (k) => pts.map((p, i) => `${xs[i]},${sy(k(p))}`).join(' ');
      const homeLine = top(p => p.win_prob.home), drawLine = top(p => p.win_prob.home + p.win_prob.draw);
      const base = `${xs[xs.length - 1]},${sy(0)} ${xs[0]},${sy(0)}`, roof = `${xs[0]},${sy(1)} ${xs[xs.length - 1]},${sy(1)}`;
      svg += `<polygon points="${roof} ${drawLine.split(' ').reverse().join(' ')}" fill="var(--away)" opacity=".85"/>`;
      svg += `<polygon points="${drawLine} ${homeLine.split(' ').reverse().join(' ')}" fill="#B9C0C9"/>`;
      svg += `<polygon points="${homeLine} ${base}" fill="var(--home)" opacity=".9"/>`;
    }
    for (const v of [0, .5, 1]) svg += `<text x="${pad.l - 6}" y="${sy(v) + 4}" text-anchor="end">${v * 100}%</text>`;
    $('cWP').innerHTML = svg + goalsMarks(sx, h, pad) + xTicks(sx, h, pad, maxM);
    $('lWP').innerHTML = `<span><i style="background:var(--home)"></i>${abbr('home')} ${t('win')}</span><span><i style="background:#B9C0C9"></i>${t('draw')}</span><span><i style="background:var(--away)"></i>${abbr('away')} ${t('win')}</span>`;
  }
  // xG race
  { const w = 560, h = 200, pad = { l: 34, r: 8, t: 8, b: 22 }, sx = axisX(0, maxM, w, pad);
    const maxXg = Math.max(1.5, ...S.series.map(p => Math.max(p.xg[0], p.xg[1]))) * 1.1;
    const sy = v => pad.t + (1 - v / maxXg) * (h - pad.t - pad.b);
    const step = i => S.series.map((p, j) => (j ? `L${sx(p.t_min)},${sy(S.series[j - 1].xg[i])} L${sx(p.t_min)},${sy(p.xg[i])}` : `M${sx(p.t_min)},${sy(p.xg[i])}`)).join(' ');
    let svg = '';
    for (let v = 0; v <= maxXg; v += 0.5) svg += `<line x1="${pad.l}" x2="${w - pad.r}" y1="${sy(v)}" y2="${sy(v)}" stroke="#E4E8E2"/><text x="${pad.l - 6}" y="${sy(v) + 4}" text-anchor="end">${v.toFixed(1)}</text>`;
    if (S.series.length > 1) svg += `<path d="${step(0)}" fill="none" stroke="var(--home)" stroke-width="2.5"/><path d="${step(1)}" fill="none" stroke="var(--away)" stroke-width="2.5"/>`;
    $('cXG').innerHTML = svg + goalsMarks(sx, h, pad) + xTicks(sx, h, pad, maxM);
    const last = S.series[S.series.length - 1];
    $('lXG').innerHTML = `<span><i style="background:var(--home)"></i>${abbr('home')} ${last ? last.xg[0].toFixed(2) : '0.00'}</span><span><i style="background:var(--away)"></i>${abbr('away')} ${last ? last.xg[1].toFixed(2) : '0.00'}</span>`;
  }
  // momentum + chaos
  { const w = 640, h = 200, pad = { l: 34, r: 8, t: 8, b: 22 }, sx = axisX(0, maxM, w, pad);
    const sy = v => pad.t + (1 - (v + 100) / 200) * (h - pad.t - pad.b);
    let svg = `<line x1="${pad.l}" x2="${w - pad.r}" y1="${sy(0)}" y2="${sy(0)}" stroke="#B9C0C9"/>`;
    if (S.series.length > 1) {
      const xs = S.series.map(p => sx(p.t_min));
      const chaos = S.series.map((p, i) => `${xs[i]},${sy(p.chaos)}`).join(' ');
      svg += `<polygon points="${xs[0]},${sy(0)} ${chaos} ${xs[xs.length - 1]},${sy(0)}" fill="#A371F7" opacity=".22"/>`;
      const pos = S.series.map((p, i) => `${xs[i]},${sy(Math.max(0, p.momentum))}`).join(' ');
      const neg = S.series.map((p, i) => `${xs[i]},${sy(Math.min(0, p.momentum))}`).join(' ');
      svg += `<polygon points="${xs[0]},${sy(0)} ${pos} ${xs[xs.length - 1]},${sy(0)}" fill="var(--home)" opacity=".85"/>`;
      svg += `<polygon points="${xs[0]},${sy(0)} ${neg} ${xs[xs.length - 1]},${sy(0)}" fill="var(--away)" opacity=".85"/>`;
    }
    svg += `<text x="${pad.l - 6}" y="${sy(80) + 4}" text-anchor="end">${abbr('home')}</text><text x="${pad.l - 6}" y="${sy(-80) + 4}" text-anchor="end">${abbr('away')}</text>`;
    $('cMO').innerHTML = svg + goalsMarks(sx, h, pad) + xTicks(sx, h, pad, maxM);
    $('lMO').innerHTML = `<span><i style="background:var(--home)"></i>${t('momentum')} ${abbr('home')}</span><span><i style="background:var(--away)"></i>${t('momentum')} ${abbr('away')}</span><span><i style="background:#A371F7;opacity:.5"></i>${t('chaos')}</span>`;
  }
}
function renderShotMap() {
  const g = document.getElementById('shots');
  if (!g) return;
  const goalIds = new Set(S.keyEvents.filter(e => e.type === 'goal').map(e => e.details.shot_event_id));
  g.innerHTML = S.keyEvents.filter(e => e.type === 'shot' && e.location_abs).map(e => {
    const r = 0.9 + 5.5 * Math.sqrt(e.details.xg), goal = e.outcome === 'goal' || goalIds.has(e.event_id);
    const [x, y] = e.location_abs;
    return `<circle cx="${x}" cy="${y}" r="${r}" fill="var(--${e.team_side})" fill-opacity="${goal ? .95 : .12}" stroke="var(--${e.team_side})" stroke-width=".45">
      <title>${e.display_minute} ${e.player_name} · xG ${e.details.xg.toFixed(2)} · ${e.outcome}</title></circle>`;
  }).join('');
}
function renderPassMap() {
  const g = document.getElementById('passlines');
  if (!g) return;
  const cut = (S.series.at(-1)?.t_min ?? 0) * 60 - 600;
  const col = d => d == null ? '#8A94A6' : d < 35 ? '#2E7A4F' : d < 65 ? '#E0A800' : '#C0392B';
  g.innerHTML = S.passes.filter(p => p.team_side === S.passSide && (p.match_time_s ?? 0) >= cut).map(p => {
    const [x1, y1] = p.location_abs, [x2, y2] = p.end_location_abs, d = p.derived?.pass_difficulty;
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${col(d)}" stroke-width="${d >= 65 ? .55 : .35}" stroke-linecap="round" opacity=".85"><title>${p.player_name} → ${p.details.recipient_name} · ${d ?? ''}</title></line>
            <circle cx="${x2}" cy="${y2}" r=".55" fill="${col(d)}"/>`;
  }).join('');
}
const COLS = [
  ['name', 't_player'], ['rating', 't_rating'], ['passes', 't_passes'], ['pass_accuracy_pct', 't_acc'], ['avg_pass_difficulty', 't_diff'],
  ['xg', 't_xg'], ['xa', 't_xa'], ['shots', 't_shots'], ['key_passes', 't_kp'], ['tackles_won', 't_tk'], ['distance_m', 't_dist'], ['top_speed_kmh', 't_top'],
];
function ratingColor(r) { return r >= 8 ? '#14213D' : r >= 7 ? '#2E7A4F' : r >= 6.3 ? '#5E8C70' : '#8A94A6'; }
function renderPlayers() {
  const rows = Object.values(S.players);
  const { key, dir } = S.sort;
  rows.sort((a, b) => {
    const va = a[key] ?? -1, vb = b[key] ?? -1;
    return typeof va === 'string' ? dir * va.localeCompare(vb) : dir * (va - vb);
  });
  const fmt = (k, v) => v == null ? '–' : k === 'distance_m' ? (v / 1000).toFixed(1) : ['xg', 'xa'].includes(k) ? v.toFixed(2)
    : ['pass_accuracy_pct', 'avg_pass_difficulty', 'top_speed_kmh'].includes(k) ? (+v).toFixed(k === 'top_speed_kmh' ? 1 : 0) : Math.round(v);
  const head = '<tr>' + COLS.map(([k, l]) => `<th data-k="${k}" ${k === key ? `aria-sort="${dir > 0 ? 'ascending' : 'descending'}"` : ''}>${t(l)}${k === key ? (dir > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('') + '</tr>';
  const body = rows.map(p => `<tr class="${p.on_pitch ? '' : 'off'} ${isFavPlayer(p.player_id) ? 'fav' : ''}">` + COLS.map(([k]) => {
    if (k === 'name') return `<td><span class="sw" style="background:var(--${p.side})"></span>${p.shirt} ${p.name} <span class="hint">${p.position}</span></td>`;
    if (k === 'rating') return `<td><span class="rating" style="background:${ratingColor(p.rating)}">${p.rating.toFixed(1)}</span></td>`;
    return `<td>${fmt(k, p[k])}</td>`;
  }).join('') + '</tr>').join('');
  $('ptable').innerHTML = `<thead>${head}</thead><tbody>${body}</tbody>`;
}
$('ptable').addEventListener('click', e => {
  const th = e.target.closest('th'); if (!th) return;
  const k = th.dataset.k; S.sort = { key: k, dir: S.sort.key === k ? -S.sort.dir : (k === 'name' ? 1 : -1) }; renderPlayers();
});
$('passTeam').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  S.passSide = b.dataset.side;
  $('passTeam').querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  renderPassMap();
});
setInterval(() => { if (S.mode === 'analyst' && S.meta) renderPassMap(); }, 2000);

function renderAll() {
  if (!S.meta) return;
  renderState(); renderTimeline(); renderNotes(); renderRecap(); renderAiBadge();
  if (S.mode === 'analyst') { renderCharts(); renderShotMap(); renderPassMap(); renderPlayers(); }
  if (S.mode === 'fan') renderFan();
  if (S.mode === 'fantasy') renderFantasy();
}

// ------------------------------------------------------------------ fantasy
const FX_KEY = 'matchlens.fantasy';
const POS_ORDER = ['GK', 'DEF', 'MID', 'FWD'];
let fx = { squad: [], captain: null, md: null, xi: [] };
try { fx = { ...fx, ...JSON.parse(localStorage.getItem(FX_KEY) || '{}') }; } catch (e) { /* storage unavailable */ }
const saveFx = () => { try { localStorage.setItem(FX_KEY, JSON.stringify(fx)); } catch (e) { /* storage unavailable */ } };
const money = v => (+v).toFixed(1);

async function onFantasyHello(f) {
  S.fx.live = (f && f.points) || {}; S.fx.quotes = f && f.quotes;
  const md = f && f.season ? f.matchday : null;
  $('fxNote').hidden = !!md; $('fxNote').textContent = md ? '' : t('fx_unavailable');
  if (!md) { S.fx.md = null; renderFantasy(); return; }
  try {
    if (!S.fx.meta) S.fx.meta = await (await fetch('/api/fantasy/meta')).json();
    if (S.fx.md !== md) {
      const rows = await (await fetch(`/api/fantasy/players?matchday=${md}`)).json();
      S.fx.players = Object.fromEntries(rows.map(r => [r.player_id, r]));
      S.fx.fix = await (await fetch(`/api/fantasy/fixtures?matchday=${md}`)).json();
      S.fx.md = md; S.fx.advice = null;
    }
    // keep the manager's squad across matchdays; build the suggested one the first time
    if (!fx.squad.length || fx.squad.some(p => !S.fx.players[p])) await resetSquad();
  } catch (e) { $('fxNote').hidden = false; $('fxNote').textContent = t('fx_unavailable'); }
  renderFantasy();
}

async function resetSquad() {
  const r = await (await fetch(`/api/fantasy/squad?matchday=${S.fx.md}&match_id=${encodeURIComponent($('match').value)}`)).json();
  fx = { squad: r.squad, captain: null, md: S.fx.md, xi: [] };
  fx.xi = autoXI(fx.squad);
  const live = r.squad.filter(p => S.meta && inMatch(p)).sort((a, b) => S.fx.players[b].projected - S.fx.players[a].projected);
  fx.captain = live[0] || r.squad[0];
  saveFx(); S.fx.advice = null;
}
$('fxReset').onclick = async () => { if (S.fx.md) { await resetSquad(); renderFantasy(); } };

function inMatch(pid) {
  return S.meta && [...S.meta.home.starting_xi, ...S.meta.home.bench, ...S.meta.away.starting_xi, ...S.meta.away.bench]
    .some(p => p.player_id === pid);
}
const livePts = pid => { const r = S.fx.live[pid]; return r ? r.points * (pid === fx.captain ? 2 : 1) : 0; };

function renderFantasy() {
  if (!S.fx.md || !fx.squad.length) { $('fxSquad').innerHTML = ''; $('fxMeta').textContent = ''; $('fxTotal').textContent = '–'; renderCalls(); return; }
  const P = S.fx.players, budget = S.fx.meta ? S.fx.meta.budget : 100;
  const cost = fx.squad.reduce((a, p) => a + (P[p]?.price || 0), 0);
  $('fxMeta').textContent = t('fx_meta', { md: S.fx.md, cost: money(cost), budget: money(budget), bank: money(budget - cost) });
  if (!validXI(fx.xi)) { fx.xi = autoXI(fx.squad); saveFx(); }
  $('fxTotal').textContent = fx.xi.reduce((a, p) => a + livePts(p), 0);     // starting XI count, captain doubles
  const rows = [...fx.squad].sort((a, b) => POS_ORDER.indexOf(P[a].position) - POS_ORDER.indexOf(P[b].position)
    || (inMatch(b) - inMatch(a)) || P[b].price - P[a].price);
  $('fxSquad').innerHTML = rows.map(pid => {
    const p = P[pid], r = S.fx.live[pid], here = inMatch(pid), cap = pid === fx.captain;
    const reasons = r ? r.reasons.map(x => `<span class="chip ${x.pts < 0 ? 'neg' : ''}">${esc(t('r_' + x.code))} ${x.pts > 0 ? '+' : ''}${x.pts}</span>`).join('') : '';
    const status = here ? (r ? `${r.minutes}' ${r.provisional ? '· ' + t('provisional') : ''}` : t('in_match')) : t('not_playing');
    return `<li class="${here ? 'here' : ''}" data-pid="${pid}">
      <button class="cap ${cap ? 'on' : ''}" data-cap="${pid}" title="${t('captain')}" aria-pressed="${cap}">★</button>
      <span class="pos">${p.position}</span>
      <div class="who"><button class="pname" data-prof="${pid}">${esc(p.name)}</button>${fx.xi.includes(pid) ? '' : ` <span class="chip bench">${t('bench')}</span>`} <span class="hint">${p.club} · €${money(p.price)}m · ${t('f_form')} ${p.form}</span>
        <div class="chips">${here ? '<span class="dot"></span>' : ''}<span class="hint">${esc(status)}</span>${reasons}</div></div>
      <span class="pts num">${here && r ? livePts(pid) : '–'}</span>
      <button class="adv" data-adv="${pid}">${t('advice')}</button></li>`;
  }).join('');
  renderPitch(); renderFixtures(); renderCalls(); renderAdvice();
}
$('fxSquad').addEventListener('click', e => {
  const c = e.target.closest('[data-cap]'), a = e.target.closest('[data-adv]'), pr = e.target.closest('[data-prof]');
  if (pr) openProfile(pr.dataset.prof);
  if (c) { fx.captain = c.dataset.cap; saveFx(); renderFantasy(); }
  if (a) askAdvisor(a.dataset.adv);
});

async function askAdvisor(pid) {
  const P = S.fx.players, budget = S.fx.meta ? S.fx.meta.budget : 100;
  const bank = Math.max(0, budget - fx.squad.reduce((a, p) => a + (P[p]?.price || 0), 0));
  S.fx.advice = { loading: P[pid].name, pid };
  renderAdvice();
  try {
    const r = await fetch('/api/fantasy/advice', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ player_id: pid, squad: fx.squad, matchday: S.fx.md, bank: +bank.toFixed(1), lang: prefs.lang }) });
    S.fx.advice = await r.json();
  } catch (e) { S.fx.advice = null; }
  renderAdvice();
}
function renderAdvice() {
  const a = S.fx.advice, el = $('fxAdvice');
  if (!a) { el.innerHTML = `<p class="hint">${t('advisor_hint')}</p>`; return; }
  if (a.loading) { el.innerHTML = `<p class="hint">${t('asking', { name: esc(a.loading) })}</p>`; return; }
  const tx = (a.texts && (a.texts[prefs.lang] || a.texts.en)) || {};
  const reasons = a.sheet.reasons.map(r => {
    const w = Math.min(100, Math.abs(r.effect) * 33);
    return `<li><span class="bar"><i class="${r.effect < 0 ? 'neg' : ''}" style="width:${w}%"></i></span><span class="eff num">${r.effect > 0 ? '+' : ''}${r.effect}</span>${esc(r.text)}</li>`;
  }).join('');
  const reps = a.sheet.replacements.map(r => `<li><div><strong>${esc(r.name)}</strong> <span class="hint">${r.club} · €${money(r.price)}m · ${t('ppm', { p: r.projected_points_per_match })}</span></div>
      <button data-in="${r.player_id}" data-out="${a.player_id}">${t('transfer_in')}</button></li>`).join('');
  el.innerHTML = `<div class="verdict v-${a.verdict}">${t('v_' + a.verdict)}</div>
    <h3 class="advh">${esc(tx.headline)}${srcBadge({ ...a, status: 'final' })}</h3>
    <p>${esc(tx.explanation)}</p><p class="hint">${esc(tx.replacement_note)}</p>
    <ul class="reasons">${reasons}</ul>
    ${reps ? `<h3>${t('replacements')}</h3><ul class="reps">${reps}</ul>` : ''}${traceHtml(a)}`;
}
$('fxAdvice').addEventListener('click', e => {
  const b = e.target.closest('[data-in]'); if (!b) return;
  const out = b.dataset.out, inn = b.dataset.in;
  fx.squad = fx.squad.map(p => (p === out ? inn : p));
  if (fx.captain === out) fx.captain = inn;
  fx.xi = fx.xi.map(p => (p === out ? inn : p));
  saveFx();
  const msg = t('transferred', { out: S.fx.players[out].name, in: S.fx.players[inn].name });
  S.fx.advice = null; renderFantasy();
  $('fxAdvice').innerHTML = `<p><strong>${esc(msg)}</strong></p>`;
});

function renderCalls() {
  const q = S.fx.quotes, c = S.fx.calls;
  $('fxCallPts').textContent = c ? c.points : 0;
  $('fxCalls').innerHTML = c && c.calls.length ? [...c.calls].reverse().map(x =>
    `<li class="${x.status}"><span class="m">${esc(x.minute)}</span><span>${esc(x.label)}</span>
      <span class="st">${x.status === 'won' ? '+' + x.pays : x.status === 'lost' ? t('lost') : t('pays', { n: x.pays })}</span></li>`).join('')
    : `<li class="hint">${t('no_calls')}</li>`;
  if (!q || !S.meta) { $('fxQuotes').innerHTML = ''; return; }
  if (!q.open) { $('fxQuotes').innerHTML = `<p class="hint">${t('calls_closed')}</p>`; return; }
  const pays = p => Math.max(11, Math.min(500, Math.round(10 / Math.max(p, 1e-6))));
  const btn = (kind, target, label, p) => p >= 0.01
    ? `<button class="qb" data-kind="${kind}" data-target="${target}"><span>${esc(label)}</span><b class="num">${pct(p)}%</b><small>${t('pays', { n: pays(p) })}</small></button>` : '';
  const ng = q.next_goal;
  const name = pid => (S.players[pid] && S.players[pid].name) || (S.fx.players[pid] && S.fx.players[pid].name) || pid;
  const mine = new Set(fx.squad);
  const pick = (obj, n) => Object.entries(obj).sort((a, b) => (mine.has(b[0]) - mine.has(a[0])) || b[1] - a[1]).slice(0, n);
  $('fxQuotes').innerHTML = `<h3>${t('next_goal')}</h3><div class="qrow">${btn('next_goal', 'home', S.meta.home.short_name, ng.home)}${btn('next_goal', 'none', t('no_more'), ng.none)}${btn('next_goal', 'away', S.meta.away.short_name, ng.away)}</div>
    <h3>${t('scorer')}</h3><div class="qrow">${pick(q.scorer, 4).map(([pid, p]) => btn('scorer', pid, (mine.has(pid) ? '★ ' : '') + name(pid), p)).join('')}</div>
    <h3>${t('booked')}</h3><div class="qrow">${pick(q.booked, 4).map(([pid, p]) => btn('booked', pid, (mine.has(pid) ? '★ ' : '') + name(pid), p)).join('')}</div>`;
}
$('fxQuotes').addEventListener('click', e => {
  const b = e.target.closest('.qb'); if (!b || !S.ws || S.ws.readyState !== 1) return;
  S.ws.send(JSON.stringify({ action: 'call', kind: b.dataset.kind, target: b.dataset.target }));
});

// ------------------------------------------------------------------ fantasy: line-up on a pitch
const SHAPE = { GK: [1, 1], DEF: [3, 5], MID: [2, 5], FWD: [1, 3] };
const posOf = pid => S.fx.players[pid]?.position;
function validXI(xi) {
  if (!xi || xi.length !== 11 || xi.some(p => !fx.squad.includes(p))) return false;
  return Object.entries(SHAPE).every(([pos, [lo, hi]]) => { const n = xi.filter(p => posOf(p) === pos).length; return n >= lo && n <= hi; });
}
function autoXI(squad) {
  // best projection first, respecting 1 GK, 3-5 DEF, 2-5 MID, 1-3 FWD
  // players in the match being watched get a nudge, so the default XI shows live points
  const score = p => S.fx.players[p].projected + (inMatch(p) ? 2.5 : 0);
  const by = pos => squad.filter(p => posOf(p) === pos).sort((a, b) => score(b) - score(a));
  const xi = [by('GK')[0], ...by('DEF').slice(0, 3), ...by('MID').slice(0, 2), by('FWD')[0]];
  const rest = squad.filter(p => !xi.includes(p) && posOf(p) !== 'GK').sort((a, b) => score(b) - score(a));
  for (const p of rest) {
    if (xi.length === 11) break;
    const n = xi.filter(q => posOf(q) === posOf(p)).length;
    if (n < SHAPE[posOf(p)][1]) xi.push(p);
  }
  return xi;
}
const CLUB_COL = () => Object.fromEntries(S.clubs.map(c => [c.team_id, c.colors?.primary || '#14213D']));
const CLUB_KIT = () => Object.fromEntries(S.clubs.map(c => [c.team_id, c.colors || {}]));
// Procedural player portrait: an illustrated, made-up face (the players are fictional), deterministic per player_id.
function avatarSvg(pid, kit = {}, shirt = '', size = 96) {
  let h = 2166136261;
  for (const ch of pid) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); }
  const rnd = () => { h ^= h << 13; h ^= h >>> 17; h ^= h << 5; return ((h >>> 0) % 10000) / 10000; };
  const pick = a => a[Math.floor(rnd() * a.length)];
  const skin = pick(['#F6D3B3', '#EBC09A', '#D9A57B', '#C68B5E', '#A86E45', '#8A5534', '#6B3F25']);
  const hairC = pick(['#1E1A18', '#2B211C', '#3B2A20', '#5A3A24', '#8A5A2E', '#B98745', '#D8B26A', '#14100E']);
  const style = pick(['crop', 'buzz', 'curly', 'quiff', 'long', 'bald', 'afro', 'fade']);
  const beard = pick(['none', 'none', 'stubble', 'full', 'goatee']);
  const brow = pick([0, 1, 2]), mouth = pick([0, 1, 2]), faceW = 25 + rnd() * 4, jaw = 30 + rnd() * 4;
  const p = kit.primary || '#14213D', s2 = kit.secondary || '#FFFFFF';
  const shade = 'rgba(0,0,0,.12)';
  const hair = {
    crop: `<path d="M${50 - faceW},44 C${50 - faceW},18 ${50 + faceW},18 ${50 + faceW},44 C${50 + faceW - 4},32 ${50 - faceW + 4},32 ${50 - faceW},44Z" fill="${hairC}"/>`,
    buzz: `<path d="M${50 - faceW + 1},42 C${50 - faceW},22 ${50 + faceW},22 ${50 + faceW - 1},42 C${50 + 10},34 ${50 - 10},34 ${50 - faceW + 1},42Z" fill="${hairC}" opacity=".75"/>`,
    curly: [...Array(9)].map((_, i) => `<circle cx="${50 - faceW + 3 + i * (2 * faceW - 6) / 8}" cy="${26 + (i % 2) * 3}" r="7.5" fill="${hairC}"/>`).join('') + `<rect x="${50 - faceW}" y="26" width="${2 * faceW}" height="10" fill="${hairC}"/>`,
    quiff: `<path d="M${50 - faceW},44 C${50 - faceW - 2},20 ${50 + 4},10 ${50 + faceW + 2},24 C${50 + faceW + 2},30 ${50 + faceW},36 ${50 + faceW},44 C${50 + 10},30 ${50 - 14},34 ${50 - faceW},44Z" fill="${hairC}"/>`,
    long: `<path d="M${50 - faceW - 3},66 C${50 - faceW - 6},14 ${50 + faceW + 6},14 ${50 + faceW + 3},66 L${50 + faceW - 2},66 C${50 + faceW},36 ${50 - faceW},36 ${50 - faceW + 2},66Z" fill="${hairC}"/>`,
    bald: '',
    afro: `<ellipse cx="50" cy="30" rx="${faceW + 9}" ry="19" fill="${hairC}"/>`,
    fade: `<path d="M${50 - faceW + 2},40 C${50 - faceW + 2},18 ${50 + faceW - 2},18 ${50 + faceW - 2},40 L${50 + faceW - 6},31 L${50 - faceW + 6},31Z" fill="${hairC}"/><rect x="${50 - faceW}" y="31" width="${2 * faceW}" height="9" fill="${hairC}" opacity=".35"/>`,
  }[style];
  const beards = {
    none: '', stubble: `<path d="M${50 - faceW + 3},56 Q50,${62 + jaw - 30} ${50 + faceW - 3},56 Q50,${84} ${50 - faceW + 3},56Z" fill="${hairC}" opacity=".22"/>`,
    full: `<path d="M${50 - faceW + 1},52 Q50,${66} ${50 + faceW - 1},52 Q${50 + faceW - 4},80 50,${82} Q${50 - faceW + 4},80 ${50 - faceW + 1},52Z" fill="${hairC}" opacity=".9"/>`,
    goatee: `<path d="M44,70 Q50,74 56,70 Q55,80 50,81 Q45,80 44,70Z" fill="${hairC}" opacity=".85"/>`,
  }[beard];
  const brows = [`<path d="M38,45 L45,44 M55,44 L62,45" stroke="${hairC}" stroke-width="2.2" stroke-linecap="round"/>`,
    `<path d="M38,46 Q41.5,43 45,45 M55,45 Q58.5,43 62,46" stroke="${hairC}" stroke-width="2" fill="none" stroke-linecap="round"/>`,
    `<path d="M38,44 L45,45.5 M55,45.5 L62,44" stroke="${hairC}" stroke-width="2.4" stroke-linecap="round"/>`][brow];
  const mouths = ['<path d="M45,67 Q50,70 55,67" stroke="#6B3A2E" stroke-width="1.6" fill="none" stroke-linecap="round"/>',
    '<path d="M45.5,67.5 L54.5,67.5" stroke="#6B3A2E" stroke-width="1.6" stroke-linecap="round"/>',
    '<path d="M44.5,66.5 Q50,72 55.5,66.5 Q50,69 44.5,66.5Z" fill="#fff" stroke="#6B3A2E" stroke-width="1.2"/>'][mouth];
  const gid = 'g' + pid.replace(/\W/g, '');
  return `<svg class="avatar" width="${size}" height="${size}" viewBox="0 0 100 100" role="img" aria-label="illustrated portrait">
    <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${p}" stop-opacity=".25"/><stop offset="1" stop-color="${p}" stop-opacity=".7"/></linearGradient>
      <clipPath id="c${gid}"><rect width="100" height="100" rx="14"/></clipPath></defs>
    <g clip-path="url(#c${gid})"><rect width="100" height="100" fill="url(#${gid})"/>
    <path d="M8,100 C10,84 26,78 40,76 L60,76 C74,78 90,84 92,100Z" fill="${p}"/>
    <path d="M40,76 L50,88 L60,76" fill="none" stroke="${s2}" stroke-width="3"/>
    <text x="73" y="95" text-anchor="middle" font-family="Barlow Condensed, sans-serif" font-weight="700" font-size="14" fill="${s2}" stroke="rgba(0,0,0,.25)" stroke-width=".4">${shirt}</text>
    <rect x="43" y="64" width="14" height="14" rx="4" fill="${skin}"/><rect x="43" y="70" width="14" height="5" fill="${shade}"/>
    <g transform="translate(50 46) scale(0.86 1.02) translate(-50 -50)">${style === 'long' ? hair : ''}
    <ellipse cx="${50 - faceW}" cy="52" rx="3.5" ry="5.5" fill="${skin}"/><ellipse cx="${50 + faceW}" cy="52" rx="3.5" ry="5.5" fill="${skin}"/>
    <path d="M${50 - faceW},44 C${50 - faceW},26 ${50 + faceW},26 ${50 + faceW},44 L${50 + faceW - 2},58 Q50,${jaw + 44} ${50 - faceW + 2},58Z" fill="${skin}"/>
    ${beards}${style === 'long' ? '' : hair}${brows}
    <ellipse cx="41.5" cy="50" rx="2.3" ry="2.6" fill="#fff"/><ellipse cx="58.5" cy="50" rx="2.3" ry="2.6" fill="#fff"/>
    <circle cx="41.8" cy="50.4" r="1.5" fill="#2A1E18"/><circle cx="58.8" cy="50.4" r="1.5" fill="#2A1E18"/>
    <path d="M50,52 L48,60 Q50,61.5 52,60" stroke="${shade}" stroke-width="1.6" fill="none" stroke-linecap="round"/>${mouths}</g></g></svg>`;
}
const FDR = ['', '#2E7A4F', '#8CC79B', '#D9DED6', '#EBA184', '#B3261E'];
const fdrText = d => (d === 1 || d === 5 ? '#fff' : 'var(--ink)');

function shirtHtml(pid, cols, opts = {}) {
  const p = S.fx.players[pid], r = S.fx.live[pid], here = inMatch(pid), cap = pid === fx.captain;
  const nxt = (S.fx.fix?.[p.club_id] || [])[0];
  const sub = here && r ? `<b class="num">${livePts(pid)}</b>` : here ? `<span>${t('in_match')}</span>`
    : nxt ? `<span>${nxt.opponent} (${nxt.home ? 'H' : 'A'})</span>` : '';
  return `<button class="shirt ${here ? 'here' : ''} ${opts.target ? 'target' : ''} ${S.fx.swap === pid ? 'sel' : ''}" data-shirt="${pid}">
    <span class="jersey" style="background:${cols[p.club_id] || '#14213D'}">${esc(p.club)}${cap ? '<i class="c">C</i>' : ''}${here ? '<i class="live"></i>' : ''}</span>
    <span class="nm">${esc(p.name)}</span><span class="sub">${sub}</span></button>`;
}
function renderPitch() {
  const el = $('fxPitch');
  if (!S.fx.md || !fx.squad.length) { el.innerHTML = ''; return; }
  const cols = CLUB_COL(), sw = S.fx.swap;
  const canSwap = q => { if (!sw) return false; const xi = fx.xi.map(p => (p === q ? sw : p)); return validXI(xi); };
  const row = pos => `<div class="prow">${fx.xi.filter(p => posOf(p) === pos).map(p => shirtHtml(p, cols, { target: canSwap(p) })).join('')}</div>`;
  const bench = fx.squad.filter(p => !fx.xi.includes(p)).sort((a, b) => POS_ORDER.indexOf(posOf(a)) - POS_ORDER.indexOf(posOf(b)));
  const shape = ['DEF', 'MID', 'FWD'].map(pos => fx.xi.filter(p => posOf(p) === pos).length).join('-');
  el.innerHTML = `<div class="pfield"><span class="shape num">${shape}</span>${row('FWD')}${row('MID')}${row('DEF')}${row('GK')}</div>
    <div class="pbench"><span class="lbl">${t('bench')}</span>${bench.map(p => `<div class="bslot">${shirtHtml(p, cols)}<button class="swapb" data-swap="${p}" aria-pressed="${sw === p}" title="${t('swap')}">⇄</button></div>`).join('')}</div>`;
  $('fxHint').textContent = sw ? t('swap_hint', { name: S.fx.players[sw].name }) : t('squad_hint');
}
$('fxPitch').addEventListener('click', e => {
  const sb = e.target.closest('[data-swap]'), sh = e.target.closest('[data-shirt]');
  if (sb) { S.fx.swap = S.fx.swap === sb.dataset.swap ? null : sb.dataset.swap; renderPitch(); return; }
  if (!sh) return;
  const pid = sh.dataset.shirt;
  if (S.fx.swap && fx.xi.includes(pid)) {
    const xi = fx.xi.map(p => (p === pid ? S.fx.swap : p));
    if (validXI(xi)) { fx.xi = xi; if (fx.captain === pid) fx.captain = S.fx.swap; saveFx(); }
    S.fx.swap = null; renderFantasy(); return;
  }
  S.fx.swap = null; openProfile(pid);
});
$('fxView').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  $('fxView').querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  $('fxPitch').hidden = b.dataset.v !== 'pitch'; $('fxSquad').hidden = b.dataset.v !== 'list';
});

// ------------------------------------------------------------------ fantasy: fixtures grid
function renderFixtures() {
  const el = $('fxFix');
  if (!S.fx.fix || !fx.squad.length) { el.innerHTML = ''; return; }
  const mds = [...new Set(Object.values(S.fx.fix).flat().map(f => f.md))].sort((a, b) => a - b).slice(0, 5);
  const rows = [...fx.squad].sort((a, b) => POS_ORDER.indexOf(posOf(a)) - POS_ORDER.indexOf(posOf(b)));
  el.innerHTML = `<thead><tr><th></th>${mds.map(m => `<th>${t('md_short')}${m}</th>`).join('')}<th>Ø</th></tr></thead><tbody>` + rows.map(pid => {
    const p = S.fx.players[pid], fxs = S.fx.fix[p.club_id] || [];
    const avg = fxs.length ? (fxs.reduce((a, f) => a + f.difficulty, 0) / fxs.length).toFixed(1) : '–';
    return `<tr><td><button class="pname" data-prof="${pid}">${esc(p.name)}</button> <span class="hint">${p.position}</span></td>${mds.map(m => {
      const f = fxs.find(x => x.md === m);
      return f ? `<td><span class="fdr" style="background:${FDR[f.difficulty]};color:${fdrText(f.difficulty)}">${f.opponent} ${f.home ? 'H' : 'A'}</span></td>` : '<td>–</td>';
    }).join('')}<td class="num">${avg}</td></tr>`;
  }).join('') + '</tbody>';
}
$('fxFix').addEventListener('click', e => { const b = e.target.closest('[data-prof]'); if (b) openProfile(b.dataset.prof); });

// ------------------------------------------------------------------ fantasy: player profile
const ROLE_XY = { GK: [50, 92], CB: [50, 76], LCB: [36, 76], RCB: [64, 76], LB: [15, 70], RB: [85, 70], LWB: [12, 58], RWB: [88, 58],
  DM: [50, 61], LDM: [38, 61], RDM: [62, 61], LCM: [35, 48], RCM: [65, 48], CM: [50, 48], LM: [12, 45], RM: [88, 45],
  CAM: [50, 34], LAM: [36, 33], RAM: [64, 33], LW: [15, 22], RW: [85, 22], ST: [50, 13], LST: [40, 14], RST: [60, 14] };
function hexSvg(hx, color) {
  // Football Manager-style analysis shape: club colour = attribute ratings, dashed gold = this season (percentile)
  const cats = hx.categories, n = cats.length, cx = 150, cy = 128, R = 100;
  const pt = (i, v) => { const a = -Math.PI / 2 + i * 2 * Math.PI / n; return [cx + R * v * Math.cos(a), cy + R * v * Math.sin(a)]; };
  const scale = v => Math.max(0, (v - 20) / 79);                       // 20 at the centre, 99 at the edge
  let s = '';
  [1, 0.75, 0.5, 0.25].forEach((v, k) => { s += `<polygon points="${cats.map((_, i) => pt(i, v).join(',')).join(' ')}" fill="${k % 2 ? '#FFFFFF' : '#F1F5EF'}" stroke="#D9DED6"/>`; });
  cats.forEach((_, i) => { const [x, y] = pt(i, 1); s += `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="#D9DED6"/>`; });
  s += `<polygon points="${cats.map((c, i) => pt(i, scale(c.rating ?? 20)).join(',')).join(' ')}" fill="${color}" fill-opacity=".32" stroke="${color}" stroke-width="2.2" stroke-linejoin="round"/>`;
  if (hx.has_season) s += `<polygon points="${cats.map((c, i) => pt(i, scale(c.season ?? 20)).join(',')).join(' ')}" fill="none" stroke="var(--flag)" stroke-width="2.2" stroke-dasharray="5 3" stroke-linejoin="round"/>`;
  cats.forEach((c, i) => {
    const [x, y] = pt(i, 1.17), anchor = Math.abs(x - cx) < 5 ? 'middle' : x > cx ? 'start' : 'end';
    const cls = hx.strengths.includes(c.key) ? 'good' : hx.weaknesses.includes(c.key) ? 'bad' : '';
    s += `<text x="${x}" y="${y - 2}" text-anchor="${anchor}" class="ax ${cls}">${esc(t('hx_' + c.key))}</text>
          <text x="${x}" y="${y + 13}" text-anchor="${anchor}" class="axv">${c.rating ?? '–'}${c.season != null ? ` <tspan class="axs">· ${c.season}</tspan>` : ''}</text>`;
  });
  return `<svg class="radar" viewBox="-74 -8 448 282" role="img" aria-label="${t('hexagon')}">${s}</svg>
    <div class="legend"><span><i style="background:${color}"></i>${t('hx_rating')}</span>${hx.has_season ? `<span><i style="background:var(--flag)"></i>${t('hx_season')}</span>` : ''}</div>`;
}
const attrCol = v => v == null ? '#B9C0C9' : v >= 85 ? '#1F7A45' : v >= 75 ? '#4C9A2A' : v >= 65 ? '#B98900' : v >= 50 ? '#D2691E' : '#B3261E';
function attrCard(hx) {
  // EA FC-style attribute breakdown: each category with its sub-attributes; ◉ = measured in this season's matches
  return `<div class="attrs">${hx.categories.map(c => `<div class="acat">
      <div class="ahead"><span class="num" style="color:${attrCol(c.rating)}">${c.rating ?? '–'}</span><strong>${esc(t('hx_' + c.key))}</strong></div>
      <ul>${c.subs.map(r => `<li class="${r.kind}"><span>${r.kind === 'stat' ? '<i title="' + esc(t('measured')) + '">◉</i> ' : ''}${esc(t('sa_' + r.key))}</span>
        <span class="aval num" style="color:${attrCol(r.value)}">${r.value ?? '–'}</span><span class="abar"><b style="width:${r.value ?? 0}%;background:${attrCol(r.value)}"></b></span></li>`).join('')}</ul>
    </div>`).join('')}</div><p class="hint">${t('attrs_hint', { m: hx.min_minutes })}</p>`;
}
function pointsChart(rows) {
  if (!rows.length) return `<p class="hint">–</p>`;
  const w = 560, h = 170, pad = { l: 26, r: 34, t: 10, b: 22 }, bw = (w - pad.l - pad.r) / rows.length;
  const maxP = Math.max(10, ...rows.map(r => r.points)), minP = Math.min(0, ...rows.map(r => r.points));
  const sy = v => pad.t + (maxP - v) / (maxP - minP) * (h - pad.t - pad.b);
  const prices = rows.map(r => r.price), pLo = Math.min(...prices) - 0.3, pHi = Math.max(...prices) + 0.3;
  const py = v => pad.t + (pHi - v) / (pHi - pLo) * (h - pad.t - pad.b);
  let s = `<line x1="${pad.l}" x2="${w - pad.r}" y1="${sy(0)}" y2="${sy(0)}" stroke="#B9C0C9"/>`;
  rows.forEach((r, i) => {
    const x = pad.l + i * bw + bw * 0.15, top = sy(Math.max(0, r.points)), bot = sy(Math.min(0, r.points));
    const col = r.minutes === 0 ? '#D9DED6' : r.points >= 8 ? '#14213D' : r.points >= 4 ? '#2E7A4F' : r.points >= 0 ? '#8CC79B' : '#B3261E';
    s += `<rect x="${x}" y="${top}" width="${bw * 0.7}" height="${Math.max(1, bot - top)}" fill="${col}" rx="2"><title>${t('md_short')}${r.md} · ${r.opponent} (${r.home ? 'H' : 'A'}) ${r.score || ''} · ${r.minutes}' · ${r.points} ${t('f_pts')}</title></rect>
      <text x="${x + bw * 0.35}" y="${h - 6}" text-anchor="middle">${r.md}</text>${r.minutes ? `<text x="${x + bw * 0.35}" y="${top - 3}" text-anchor="middle" class="pv">${r.points}</text>` : ''}`;
  });
  s += `<polyline points="${rows.map((r, i) => `${pad.l + i * bw + bw / 2},${py(r.price)}`).join(' ')}" fill="none" stroke="var(--flag)" stroke-width="2"/>`;
  return `<svg class="chart" viewBox="0 0 ${w} ${h}">${s}</svg><div class="legend"><span><i style="background:#2E7A4F"></i>${t('f_pts')}</span><span><i style="background:var(--flag)"></i>${t('price')}</span></div>`;
}
let profPid = null;
async function openProfile(pid) {
  if (!S.fx.md) return;
  profPid = pid;
  $('profBody').innerHTML = `<p class="hint">…</p>`;
  if (!$('profDlg').open) $('profDlg').showModal();
  const p = await (await fetch(`/api/fantasy/player/${pid}?matchday=${S.fx.md}`)).json();
  if (profPid !== pid) return;
  const col = CLUB_COL()[p.club_id] || '#14213D', T = p.totals, hx = p.hexagon;
  const trend = p.price_change_3 > 0 ? `<span class="up">▲ ${money(p.price_change_3)}</span>` : p.price_change_3 < 0 ? `<span class="down">▼ ${money(-p.price_change_3)}</span>` : '<span class="hint">=</span>';
  const tile = (k, v) => `<div><dt>${t(k)}</dt><dd class="num">${v ?? '–'}</dd></div>`;
  const [rx, ry] = ROLE_XY[p.role] || ROLE_XY[{ GK: 'GK', DEF: 'CB', MID: 'CM', FWD: 'ST' }[p.position]];
  const fxRow = f => `<li><span class="fdr" style="background:${FDR[f.difficulty]};color:${fdrText(f.difficulty)}">${f.difficulty}</span><span>${t('md_short')}${f.md}</span><span>${f.opponent} (${f.home ? 'H' : 'A'})</span></li>`;
  const lastRow = r => `<li><span class="pts num ${r.points >= 6 ? 'hi' : ''}">${r.minutes ? r.points : '–'}</span><span>${t('md_short')}${r.md}</span><span>${r.opponent} (${r.home ? 'H' : 'A'}) ${r.score}</span><span class="hint">${r.minutes ? r.minutes + "'" : t('did_not_play')}${r.started ? '' : r.minutes ? ' · ' + t('sub_on') : ''}</span></li>`;
  const stats = [['s_goals', T.goals], ['s_assists', T.assists], ['t_xg', T.xg], ['t_xa', T.xa], ['t_shots', T.shots], ['t_kp', T.key_passes],
    ['t_acc', T.pass_accuracy != null ? T.pass_accuracy + '%' : null], ['s_def', T.def_actions], ...(p.position === 'GK' ? [['s_saves', T.saves]] : []),
    ['s_cards', `${T.yellow} / ${T.red}`], ['t_top', T.top_speed]];
  $('profBody').innerHTML = `
    <div class="phead"><div class="ovr"><span class="num">${hx.overall}</span><small>${p.position}</small></div>${avatarSvg(p.player_id, CLUB_KIT()[p.club_id], p.shirt ?? '', 104)}
      <div class="pid"><h2 id="prName">${esc(p.name)}${p.player_id === fx.captain ? ' <span class="chip">C</span>' : ''}</h2>
        <div class="hint">${esc(p.full_name)} · ${esc(p.club_name)} · ${p.position} (${p.role || ''}) · ${p.age ?? ''} · ${p.nationality ?? ''} · ${t('foot_' + p.foot)} · ${p.height_cm ?? ''} cm</div>
        <div class="pills"><span class="pill st-${p.status}">${t('st_' + p.status)}</span>
          <span class="formbar" title="${t('form_pct_hint')}"><span>${t('f_form')}</span><span class="track"><b style="width:${p.form_pct ?? 0}%"></b></span><em class="num">${p.form_pct ?? '–'}%</em></span></div></div>
      <div class="pprice"><span class="num">€${money(p.price)}m</span><small>${trend} ${t('last3_md')}</small></div></div>
    <div class="pgrid">
      <div><h3>${t('hexagon')}</h3>${hexSvg(hx, col)}
        <div class="chips">${hx.strengths.map(k => `<span class="chip">▲ ${esc(t('hx_' + k))}</span>`).join('')}${hx.weaknesses.map(k => `<span class="chip neg">▼ ${esc(t('hx_' + k))}</span>`).join('')}</div>
        ${hx.has_season ? '' : `<p class="hint">${t('radar_few', { m: hx.min_minutes })}</p>`}</div>
      <div><h3>${t('scorecard')}</h3><dl class="tiles">${tile('p_points', p.points)}${tile('p_avg', p.avg_points)}${tile('p_last3', p.avg_last3)}${tile('p_home', p.avg_home)}${tile('p_away', p.avg_away)}${tile('p_proj', p.projected)}</dl>
        <p class="hint">${t('p_apps', { m: p.matches, s: p.starts, min: p.minutes })}</p>
        <div class="rolemap"><svg viewBox="0 0 100 100" preserveAspectRatio="none"><rect width="100" height="100" fill="#2E7A4F"/><g fill="none" stroke="rgba(255,255,255,.7)" stroke-width=".8">
          <rect x="2" y="2" width="96" height="96"/><line x1="2" y1="50" x2="98" y2="50"/><circle cx="50" cy="50" r="10"/><rect x="25" y="2" width="50" height="15"/><rect x="25" y="83" width="50" height="15"/></g>
          <circle cx="${rx}" cy="${ry}" r="5" fill="var(--flag)" stroke="#fff" stroke-width="1"/></svg><span class="hint">${t('role')}: ${p.role || p.position}</span></div></div>
    </div>
    <h3>${t('attributes')}</h3>${attrCard(hx)}
    <h3>${t('by_md')}</h3>${pointsChart(p.by_matchday)}
    <div class="pgrid"><div><h3>${t('last5')}</h3><ul class="plist">${p.last5.map(lastRow).join('') || '<li class="hint">–</li>'}</ul></div>
      <div><h3>${t('next5')}</h3><ul class="plist">${p.next5.map(fxRow).join('') || '<li class="hint">–</li>'}</ul></div></div>
    <h3>${t('season_stats')}</h3><dl class="tiles sm">${stats.map(([k, v]) => tile(k, v)).join('')}</dl>`;
  $('prCap').hidden = !fx.squad.includes(pid) || !fx.xi.includes(pid); $('prAdv').hidden = !fx.squad.includes(pid);
}
$('prClose').onclick = () => $('profDlg').close();
$('prCap').onclick = () => { fx.captain = profPid; saveFx(); $('profDlg').close(); renderFantasy(); };
$('prAdv').onclick = () => { $('profDlg').close(); askAdvisor(profPid); };
$('profDlg').addEventListener('click', e => { if (e.target === $('profDlg')) $('profDlg').close(); });

// ------------------------------------------------------------------ preferences
function fillPrefsClubs() {
  $('pClub').innerHTML = `<option value="">${t('none')}</option>` + S.clubs.map(c => `<option value="${c.team_id}">${c.name}</option>`).join('');
  $('pClub').value = prefs.favClub || '';
}
function fillPrefsPlayers() {
  if (!S.meta) { $('pPlayer').innerHTML = `<option value="">${t('none')}</option>`; return; }
  const opt = (side) => [...S.meta[side].starting_xi, ...S.meta[side].bench]
    .map(p => `<option value="${p.player_id}">${p.shirt} ${p.name} · ${p.position}</option>`).join('');
  $('pPlayer').innerHTML = `<option value="">${t('none')}</option><optgroup label="${S.meta.home.name}">${opt('home')}</optgroup><optgroup label="${S.meta.away.name}">${opt('away')}</optgroup>`;
  $('pPlayer').value = prefs.favPlayer || '';
}
function openPrefs() { fillPrefsClubs(); fillPrefsPlayers(); $('pLang').value = prefs.lang; $('prefsDlg').showModal(); }
window.openPrefs = openPrefs;
$('prefs').onclick = openPrefs;
$('pCancel').onclick = () => $('prefsDlg').close();
$('pSave').onclick = () => {
  prefs = { lang: $('pLang').value, favClub: $('pClub').value || null, favPlayer: $('pPlayer').value || null };
  try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)); } catch (e) { /* storage unavailable */ }
  if (S.ws && S.ws.readyState === 1) S.ws.send(JSON.stringify({ action: 'lang', lang: prefs.lang }));
  $('prefsDlg').close();
  applyI18n();
  if (S.meta) { $('fnH').textContent = S.meta.home.name + (prefs.favClub === S.meta.home.team_id ? ' ★' : '');
    $('fnA').textContent = S.meta.away.name + (prefs.favClub === S.meta.away.team_id ? ' ★' : ''); }
  renderAll();
};

// ------------------------------------------------------------------ modes & controls
function setMode(mode) {
  S.mode = mode; document.body.dataset.mode = mode;
  document.querySelectorAll('.modes button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === mode)));
  const u = new URL(location.href); u.searchParams.set('mode', mode); history.replaceState(null, '', u);
  renderAll();
}
document.querySelectorAll('.modes button').forEach(b => { b.onclick = () => setMode(b.dataset.mode); });
$('watch').onclick = () => connect(true);
$('pause').onclick = () => S.ws && S.ws.readyState === 1 && S.ws.send(JSON.stringify({ action: S.paused ? 'resume' : 'pause' }));
$('speed').onchange = () => S.ws && S.ws.readyState === 1 && S.ws.send(JSON.stringify({ action: 'speed', speed: +$('speed').value }));

// ------------------------------------------------------------------ boot
(async function boot() {
  if (params.get('view') === 'overlay') document.body.classList.add('overlay');
  initPitches(); applyI18n(); setMode(S.mode);
  await loadCatalogue();
  connect(false);
})();
