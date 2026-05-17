const $ = (id) => document.getElementById(id);

const state = {
  league: 'nhl',
  gameId: null,
  pollHandle: null,
  celebrateHandle: null,
  lastHomeScore: null,
  lastAwayScore: null,
  lastGoalText: null,
};

const POLL_MS = 10000;

const THEMES = {
  sabres:  '/styles/theme-sabres.css',
  bills:   '/styles/theme-bills.css',
  generic: '/styles/theme-generic.css',
};

function applyTheme(name) {
  const choice = $('theme').value;
  const effective = choice === 'auto'
    ? (name === 'nfl' ? 'bills' : 'sabres')
    : choice;
  $('theme-css').href = THEMES[effective] || THEMES.sabres;
}

function showView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  $(name).classList.add('active');
}

function fmtTime(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

function todayLocal() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

async function loadGames() {
  const league = $('league').value;
  const date = $('date').value;
  const sel = $('game');
  sel.innerHTML = '<option>Loading...</option>';

  const params = new URLSearchParams({ league });
  // When the user picks today, omit the date param so the backend uses
  // NHL/ESPN "now" endpoints, which handle the league's own timezone math.
  if (date && date !== todayLocal()) params.set('date', date);

  try {
    const r = await fetch(`/api/games?${params}`);
    if (!r.ok) {
      let detail = r.statusText;
      try { detail = (await r.json()).error || detail; } catch {}
      sel.innerHTML = `<option value="">Upstream error (${detail})</option>`;
      return;
    }
    const games = await r.json();
    if (!games.length) {
      const when = date || todayLocal();
      sel.innerHTML = `<option value="">No ${league.toUpperCase()} games on ${when} — try changing the date</option>`;
      return;
    }
    const dates = new Set(games.map(g => (g.start_time || '').slice(0, 10)).filter(Boolean));
    const showDate = dates.size > 1;
    sel.innerHTML = games.map(g => {
      const time = fmtTime(g.start_time);
      let tag;
      if (g.state === 'live') tag = `LIVE ${g.period_label || ''} ${g.clock || ''}`.trim();
      else if (g.state === 'final') tag = 'FINAL';
      else tag = time;
      const score = (g.state === 'live' || g.state === 'final')
        ? `  ${g.away.score}-${g.home.score}`
        : '';
      const datePrefix = showDate && g.start_time
        ? new Date(g.start_time).toLocaleDateString([], { weekday: 'short', month: 'numeric', day: 'numeric' }) + ' '
        : '';
      return `<option value="${g.id}">${datePrefix}${g.away.abbrev} @ ${g.home.abbrev} — ${tag}${score}</option>`;
    }).join('');
  } catch (err) {
    console.error('loadGames failed', err);
    sel.innerHTML = '<option value="">Error loading games</option>';
  }
}

function renderClock(g) {
  if (g.state === 'final') return 'FINAL';
  if (g.state === 'pre') return fmtTime(g.start_time);
  if (g.in_intermission) return 'INT';
  return g.clock || '--:--';
}

function pulseIfChanged(el, prevKey, newValue) {
  const prev = state[prevKey];
  state[prevKey] = newValue;
  if (prev !== null && prev !== newValue) {
    el.classList.remove('pulse');
    void el.offsetWidth;
    el.classList.add('pulse');
    return true;
  }
  return false;
}

function fireCelebration() {
  const el = $('celebration');
  el.classList.remove('fire');
  void el.offsetWidth;
  el.classList.add('fire');
  if (state.celebrateHandle) clearTimeout(state.celebrateHandle);
  state.celebrateHandle = setTimeout(() => el.classList.remove('fire'), 1800);
}

function renderSituation(g) {
  const node = $('situation');
  if (state.league !== 'nfl' || g.state !== 'live') {
    node.hidden = true;
    return;
  }
  const sit = g.situation || {};
  const dd = sit.down_distance || '';
  if (!dd && !sit.yardline) {
    node.hidden = true;
    return;
  }
  node.hidden = false;
  $('down-distance').textContent = dd || '—';
  $('yardline').textContent = sit.yardline || '';

  const left = $('poss-arrow-left');
  const right = $('poss-arrow-right');
  left.classList.remove('active');
  right.classList.remove('active');
  const possId = String(sit.possession || '');
  // away on the left, home on the right in our layout
  if (possId && String(g.away.id || '') === possId) left.classList.add('active');
  else if (possId && String(g.home.id || '') === possId) right.classList.add('active');
  else {
    // ESPN gives team id we don't carry through; fall back to indicating "possession" exists
    if (possId) right.classList.add('active');
  }
}

async function refreshScoreboard() {
  if (!state.gameId) return;
  try {
    const r = await fetch(`/api/game/${state.league}/${state.gameId}`);
    if (!r.ok) throw new Error(r.statusText);
    const g = await r.json();

    $('home-name').textContent = g.home.name || '';
    $('away-name').textContent = g.away.name || '';

    $('home-score').textContent = g.home.score ?? 0;
    $('away-score').textContent = g.away.score ?? 0;
    const homeChanged = pulseIfChanged($('home-score'), 'lastHomeScore', g.home.score ?? 0);
    const awayChanged = pulseIfChanged($('away-score'), 'lastAwayScore', g.away.score ?? 0);
    if ((homeChanged || awayChanged) && g.state === 'live') fireCelebration();

    const homeLogo = $('home-logo');
    const awayLogo = $('away-logo');
    if (g.home.logo && homeLogo.src !== g.home.logo) homeLogo.src = g.home.logo;
    if (g.away.logo && awayLogo.src !== g.away.logo) awayLogo.src = g.away.logo;

    $('period').textContent = g.period_label || (g.state === 'pre' ? (state.league === 'nfl' ? 'KICKOFF' : 'PUCK DROP') : '');
    $('clock').textContent = renderClock(g);
    $('status').textContent = g.venue || '';

    if (state.league === 'nhl') {
      $('home-extra').textContent = `SOG ${g.home.shots ?? 0}`;
      $('away-extra').textContent = `SOG ${g.away.shots ?? 0}`;
      $('last-play').textContent = g.last_penalty || '';
      $('situation').hidden = true;
    } else {
      $('home-extra').textContent = g.home.record || '';
      $('away-extra').textContent = g.away.record || '';
      $('last-play').textContent = (g.situation && g.situation.last_play) || '';
      renderSituation(g);
    }

    $('ribbon-top-text').textContent =
      `${g.away.name || g.away.abbrev} at ${g.home.name || g.home.abbrev}` +
      `${g.venue ? ' · ' + g.venue : ''}` +
      `${g.period_label ? ' · ' + g.period_label : ''}` +
      `${g.clock ? ' ' + g.clock : ''}`;

    const tickerBits = [];
    tickerBits.push(`${g.away.abbrev} ${g.away.score ?? 0} - ${g.home.score ?? 0} ${g.home.abbrev}`);
    if (g.last_goal) {
      tickerBits.push(g.last_goal);
      state.lastGoalText = g.last_goal;
    }
    tickerBits.push(state.league.toUpperCase() + ' live · ' + new Date().toLocaleTimeString());
    $('ribbon-bottom-text').textContent = tickerBits.join('   ·   ');
  } catch (err) {
    console.error('refreshScoreboard failed', err);
  }
}

function startScoreboard(gameId, league) {
  state.gameId = gameId;
  state.league = league;
  state.lastHomeScore = null;
  state.lastAwayScore = null;
  state.lastGoalText = null;
  applyTheme(league);
  showView('scoreboard');
  refreshScoreboard();
  if (state.pollHandle) clearInterval(state.pollHandle);
  state.pollHandle = setInterval(refreshScoreboard, POLL_MS);
}

function stopScoreboard() {
  if (state.pollHandle) {
    clearInterval(state.pollHandle);
    state.pollHandle = null;
  }
  state.gameId = null;
  showView('picker');
  loadGames();
}

document.addEventListener('DOMContentLoaded', () => {
  $('date').value = todayLocal();
  $('league').addEventListener('change', loadGames);
  $('date').addEventListener('change', loadGames);
  $('theme').addEventListener('change', () => applyTheme($('league').value));
  $('go').addEventListener('click', () => {
    const id = $('game').value;
    const league = $('league').value;
    if (id) startScoreboard(id, league);
  });
  $('back').addEventListener('click', stopScoreboard);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' || e.key === 'b' || e.key === 'B') {
      if (state.gameId) stopScoreboard();
    }
  });
  loadGames();
});
