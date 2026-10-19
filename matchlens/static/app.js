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
  },
};
const CAUSE = { en: { goal: 'goal', card: 'card', shot: 'shot' }, es: { goal: 'gol', card: 'tarjeta', shot: 'tiro' } };

// ------------------------------------------------------------------ state
const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
const S = {
  ws: null, meta: null, state: null, series: [], players: {}, keyEvents: [], passes: [], timeline: new Map(),
  mode: params.get('mode') || 'broadcast', paused: false, done: false, sort: { key: 'rating', dir: -1 },
  passSide: 'home', clubs: [], catalogue: [],
};
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
  const url = `${proto}://${location.host}/ws/${id}?speed=${+$('speed').value || 60}&from_minute=${+$('from').value || 0}&restart=${restart ? 1 : 0}`;
  $('conn').textContent = t('connecting');
  const ws = new WebSocket(url);
  S.ws = ws;
  ws.onmessage = e => handle(JSON.parse(e.data));
  ws.onclose = () => { if (S.ws === ws) $('conn').textContent = t('disconnected'); };
}

function resetView() {
  S.meta = null; S.state = null; S.series = []; S.players = {}; S.keyEvents = []; S.passes = []; S.timeline = new Map(); S.done = false;
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
    case 'error': $('conn').textContent = m.payload.message; break;
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
  const sess = p.state.session || {};
  onSession({ speed: sess.speed, paused: sess.paused, done: sess.done });
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
  li.className = (item.kind === 'goal' ? 'goal ' : '') + (item.fav ? 'fav' : '');
  li.innerHTML = `<span class="m">${item.minute}</span><span class="x">${item.title}</span>`;
  $(id).prepend(li);
}
function addTimeline(item) { S.timeline.set(item.id, item); renderTimeline(); }
function renderTimeline() {
  const items = [...S.timeline.values()].reverse();
  $('timeline').innerHTML = items.map(i => `<li class="${i.kind === 'goal' ? 'goal' : ''} ${i.fav ? 'fav' : ''}">
    <span class="m">${i.minute}</span><div><div class="what">${i.title}</div>${i.why ? `<div class="why">${i.why}</div>` : ''}</div></li>`).join('');
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
  renderState(); renderTimeline();
  if (S.mode === 'analyst') { renderCharts(); renderShotMap(); renderPassMap(); renderPlayers(); }
  if (S.mode === 'fan') renderFan();
}

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
