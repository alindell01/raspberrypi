const $ = (id) => document.getElementById(id);

const state = {
  league: 'nhl',
  gameId: null,
  pollHandle: null,
  lastHomeScore: null,
  lastAwayScore: null,
};

const POLL_MS = 10000;

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

async function loadGames() {
  const league = $('league').value;
  const date = $('date').value;
  const sel = $('game');
  sel.innerHTML = '<option>Loading...</option>';

  const params = new URLSearchParams({ league });
  if (date) params.set('date', date);

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
      sel.innerHTML = '<option value="">No games scheduled</option>';
      return;
    }
    sel.innerHTML = games.map(g => {
      const time = fmtTime(g.start_time);
      let tag;
      if (g.state === 'live') tag = `LIVE  ${g.period_label || ''} ${g.clock || ''}`.trim();
      else if (g.state === 'final') tag = 'FINAL';
      else tag = time;
      const score = (g.state === 'live' || g.state === 'final')
        ? `  ${g.away.score}-${g.home.score}`
        : '';
      return `<option value="${g.id}">${g.away.abbrev} @ ${g.home.abbrev} — ${tag}${score}</option>`;
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
    pulseIfChanged($('home-score'), 'lastHomeScore', g.home.score ?? 0);
    pulseIfChanged($('away-score'), 'lastAwayScore', g.away.score ?? 0);

    const homeLogo = $('home-logo');
    const awayLogo = $('away-logo');
    if (g.home.logo && homeLogo.src !== g.home.logo) homeLogo.src = g.home.logo;
    if (g.away.logo && awayLogo.src !== g.away.logo) awayLogo.src = g.away.logo;

    $('period').textContent = g.period_label || (g.state === 'pre' ? 'PUCK DROP' : '');
    $('clock').textContent = renderClock(g);
    $('status').textContent = g.venue || '';

    if (state.league === 'nhl') {
      $('home-extra').textContent = `SOG ${g.home.shots ?? 0}`;
      $('away-extra').textContent = `SOG ${g.away.shots ?? 0}`;
      $('last-play').textContent = '';
    } else {
      $('home-extra').textContent = g.home.record || '';
      $('away-extra').textContent = g.away.record || '';
      const sit = g.situation || {};
      $('last-play').textContent = [sit.down_distance, sit.yardline].filter(Boolean).join(' — ')
        || sit.last_play || '';
    }

    $('ribbon-top-text').textContent =
      `${g.away.name || g.away.abbrev} at ${g.home.name || g.home.abbrev}` +
      `${g.venue ? ' · ' + g.venue : ''}` +
      `${g.period_label ? ' · ' + g.period_label : ''}` +
      `${g.clock ? ' ' + g.clock : ''}`;

    $('ribbon-bottom-text').textContent =
      `${state.league.toUpperCase()} live · ${new Date().toLocaleTimeString()} · ` +
      `${g.away.abbrev} ${g.away.score ?? 0} - ${g.home.score ?? 0} ${g.home.abbrev}`;
  } catch (err) {
    console.error('refreshScoreboard failed', err);
  }
}

function startScoreboard(gameId, league) {
  state.gameId = gameId;
  state.league = league;
  state.lastHomeScore = null;
  state.lastAwayScore = null;
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
  $('date').value = new Date().toISOString().slice(0, 10);
  $('league').addEventListener('change', loadGames);
  $('date').addEventListener('change', loadGames);
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
