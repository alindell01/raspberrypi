const $ = (id) => document.getElementById(id);

const state = {
  league: 'nhl',
  gameId: null,
  pollHandle: null,
  celebrateHandle: null,
  lastHomeScore: null,
  lastAwayScore: null,
  lastGoalText: null,
  lastStats: {},
  leaders: null,
  leaderIdx: 0,
  leaderRotateHandle: null,
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
    return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

// Always-en-US mm/dd/yyyy. Used for full ISO timestamps (with time
// component) where we want browser-local-zone formatting.
function fmtDateUS(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: '2-digit', day: '2-digit', year: 'numeric',
    });
  } catch {
    return '';
  }
}

// For bare yyyy-mm-dd dates we rearrange the parts directly; passing
// them through Date() would interpret as UTC midnight and shift a day
// in negative-offset zones.
function isoDateToUS(iso) {
  const m = (iso || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return iso || '';
  return `${m[2]}/${m[3]}/${m[1]}`;
}

function todayLocal() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function todayUS() {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${m}/${day}/${d.getFullYear()}`;
}

// "05/17/2026" → "2026-05-17"; returns '' if input isn't a complete date.
function usToIso(us) {
  if (!us) return '';
  const m = us.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (!m) return '';
  return `${m[3]}-${m[1].padStart(2, '0')}-${m[2].padStart(2, '0')}`;
}

// As the user types digits, insert slashes so the field reads as mm/dd/yyyy.
function autoFormatDate(input) {
  const cursorAtEnd = input.selectionStart === input.value.length;
  const digits = input.value.replace(/\D/g, '').slice(0, 8);
  let out = digits.slice(0, 2);
  if (digits.length >= 3) out += '/' + digits.slice(2, 4);
  if (digits.length >= 5) out += '/' + digits.slice(4, 8);
  if (input.value !== out) {
    input.value = out;
    if (cursorAtEnd) input.setSelectionRange(out.length, out.length);
  }
}

/* ---------- Click-to-pick calendar popup ---------- */

const cal = { year: 0, month: 0 };
const MONTH_NAMES = [
  'January','February','March','April','May','June',
  'July','August','September','October','November','December',
];

function openDatePopup() {
  const input = $('date');
  const iso = usToIso(input.value);
  const seed = iso ? new Date(iso + 'T12:00:00') : new Date();
  cal.year  = seed.getFullYear();
  cal.month = seed.getMonth();
  renderCalendar();
  $('date-popup').hidden = false;
}

function closeDatePopup() { $('date-popup').hidden = true; }

function renderCalendar() {
  $('cal-month-label').textContent = `${MONTH_NAMES[cal.month]} ${cal.year}`;

  const firstWeekday  = new Date(cal.year, cal.month, 1).getDay();   // 0=Sun
  const daysInMonth   = new Date(cal.year, cal.month + 1, 0).getDate();
  const daysInPrev    = new Date(cal.year, cal.month,     0).getDate();
  const todayIso      = todayLocal();
  const selectedIso   = usToIso($('date').value);

  let html = '';
  ['Su','Mo','Tu','We','Th','Fr','Sa']
    .forEach(d => { html += `<div class="cal-dow">${d}</div>`; });

  // Trailing days from previous month
  for (let i = firstWeekday - 1; i >= 0; i--) {
    html += `<button type="button" class="cal-day other-month" tabindex="-1">${daysInPrev - i}</button>`;
  }

  // Current month
  for (let day = 1; day <= daysInMonth; day++) {
    const mm = String(cal.month + 1).padStart(2, '0');
    const dd = String(day).padStart(2, '0');
    const iso = `${cal.year}-${mm}-${dd}`;
    const cls = ['cal-day'];
    if (iso === todayIso)    cls.push('today');
    if (iso === selectedIso) cls.push('selected');
    html += `<button type="button" class="${cls.join(' ')}" data-iso="${iso}">${day}</button>`;
  }

  // Always render a 6-week (42-cell) grid so popup height doesn't jump
  // when navigating between months.
  const pad = 42 - firstWeekday - daysInMonth;
  for (let day = 1; day <= pad; day++) {
    html += `<button type="button" class="cal-day other-month" tabindex="-1">${day}</button>`;
  }

  $('cal-grid').innerHTML = html;
}

function shiftMonth(delta) {
  cal.month += delta;
  while (cal.month < 0)  { cal.month += 12; cal.year--; }
  while (cal.month > 11) { cal.month -= 12; cal.year++; }
  renderCalendar();
}

function setupDatePicker() {
  const popup = $('date-popup');

  $('date-pick').addEventListener('click', (e) => {
    e.stopPropagation();
    popup.hidden ? openDatePopup() : closeDatePopup();
  });

  $('cal-prev').addEventListener('click', (e) => { e.stopPropagation(); shiftMonth(-1); });
  $('cal-next').addEventListener('click', (e) => { e.stopPropagation(); shiftMonth( 1); });

  $('cal-today').addEventListener('click', (e) => {
    e.stopPropagation();
    $('date').value = todayUS();
    closeDatePopup();
    loadGames();
  });

  $('cal-grid').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-iso]');
    if (!btn) return;
    e.stopPropagation();
    $('date').value = isoDateToUS(btn.dataset.iso);
    closeDatePopup();
    loadGames();
  });

  // Click outside the popup closes it
  document.addEventListener('click', (e) => {
    if (popup.hidden) return;
    if (popup.contains(e.target)) return;
    if (e.target === $('date-pick') || $('date-pick').contains(e.target)) return;
    closeDatePopup();
  });

  // Esc closes the popup (and stops the existing scoreboard-back handler
  // from also firing, since we're still on the picker view here).
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !popup.hidden) {
      closeDatePopup();
      e.stopPropagation();
    }
  });
}

async function loadGames() {
  const league = $('league').value;
  const dateInput = $('date').value.trim();
  const date = usToIso(dateInput);
  const sel = $('game');
  sel.innerHTML = '<option>Loading...</option>';

  // Incomplete date field — don't fetch yet.
  if (dateInput && !date) {
    sel.innerHTML = '<option value="">Enter a full mm/dd/yyyy date</option>';
    return;
  }

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
      const whenIso = date || todayLocal();
      const when = isoDateToUS(whenIso);
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
        ? fmtDateUS(g.start_time) + ' '
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

function renderArena(g) {
  const banner = $('arena-banner');
  const img    = $('arena-img');
  const name   = $('arena-name');
  if (!g.venue) {
    banner.hidden = true;
    return;
  }
  banner.hidden = false;

  // KeyBank Center gets the signature treatment: "KeyBank [key] Center"
  // with the inline key SVG between the words. Other venues just show
  // the name as-is.
  if (/^keybank\s+center$/i.test(g.venue.trim())) {
    name.innerHTML =
      `<span>KeyBank</span>` +
      `<svg class="kb-key" viewBox="0 0 80 30" aria-hidden="true"><use href="#kb-key"/></svg>` +
      `<span>Center</span>`;
  } else {
    name.textContent = g.venue;
  }

  if (g.venue_image && img.src !== g.venue_image) {
    img.src = g.venue_image;
    img.style.opacity = 1;
  } else if (!g.venue_image) {
    img.removeAttribute('src');
    img.style.opacity = 0;
  }
  const badge = $('series-badge');
  if (g.series && g.series.label) {
    badge.textContent = g.series.label;
    badge.hidden = false;
  } else {
    badge.hidden = true;
  }
}

/* ---------- Rotating stat-leader panel ---------- */

const LEADER_CATEGORIES = [
  ['goals',   'GOALS'],
  ['assists', 'ASSISTS'],
  ['points',  'POINTS'],
  ['shots',   'SHOTS'],
  ['hits',    'HITS'],
  ['blocks',  'BLOCKS'],
];
const LEADER_ROTATE_MS = 5000;

function leaderCategoriesPresent() {
  const ld = state.leaders;
  if (!ld) return [];
  return LEADER_CATEGORIES.filter(([key]) =>
    (ld.away && ld.away[key]) || (ld.home && ld.home[key])
  );
}

function paintLeaders() {
  const cats = leaderCategoriesPresent();
  if (!cats.length) return;
  if (state.leaderIdx >= cats.length) state.leaderIdx = 0;
  const [key, label] = cats[state.leaderIdx];
  for (const side of ['home', 'away']) {
    const node = $(`${side}-leader`);
    const lead = state.leaders[side] && state.leaders[side][key];
    if (!lead || !lead.name) {
      node.innerHTML =
        `<span class="lead-label">${label} LEADER</span>` +
        `<span class="lead-player">—</span>` +
        `<span class="lead-value">0</span>`;
    } else {
      const num = lead.number != null ? ` #${lead.number}` : '';
      node.innerHTML =
        `<span class="lead-label">${label} LEADER</span>` +
        `<span class="lead-player">${lead.name}${num}</span>` +
        `<span class="lead-value">${lead.value}</span>`;
    }
    node.classList.remove('lead-flip');
    void node.offsetWidth;
    node.classList.add('lead-flip');
  }
}

function renderLeaders(g) {
  state.leaders = g.leaders || null;
  const cats = leaderCategoriesPresent();
  const haveAny = cats.length > 0;
  for (const side of ['home', 'away']) {
    $(`${side}-leader`).hidden = !haveAny;
  }
  if (!haveAny) {
    if (state.leaderRotateHandle) clearInterval(state.leaderRotateHandle);
    state.leaderRotateHandle = null;
    return;
  }
  if (!state.leaderRotateHandle) {
    state.leaderIdx = 0;
    paintLeaders();
    state.leaderRotateHandle = setInterval(() => {
      const c = leaderCategoriesPresent();
      if (!c.length) return;
      state.leaderIdx = (state.leaderIdx + 1) % c.length;
      paintLeaders();
    }, LEADER_ROTATE_MS);
  } else {
    // Already rotating — just keep the current frame in sync with new data.
    paintLeaders();
  }
}

function renderPowerPlay(g) {
  const node = $('power-play');
  const pp = g.power_play;
  if (!pp || g.state !== 'live') {
    node.hidden = true;
    return;
  }
  node.hidden = false;
  $('pp-kind').textContent = pp.kind || 'POWER PLAY';
  $('pp-team').textContent = pp.team || '';
  $('pp-time').textContent = pp.time_remaining || '';
}

function renderLineScore(g) {
  const node = $('line-score');
  const ls = g.line_score;
  if (!ls || !ls.periods || !ls.periods.length) {
    node.hidden = true;
    return;
  }
  const heads = ls.periods.map(p => `<th>${p.label}</th>`).join('');
  const aRow  = ls.periods.map(p => `<td>${p.away ?? 0}</td>`).join('');
  const hRow  = ls.periods.map(p => `<td>${p.home ?? 0}</td>`).join('');
  const aTot  = (ls.totals && ls.totals.away != null) ? ls.totals.away : (g.away.score ?? 0);
  const hTot  = (ls.totals && ls.totals.home != null) ? ls.totals.home : (g.home.score ?? 0);
  node.innerHTML =
    `<thead><tr><th></th>${heads}<th>T</th></tr></thead>` +
    `<tbody>` +
    `<tr><td class="label">${g.away.abbrev || 'A'}</td>${aRow}<td class="total">${aTot}</td></tr>` +
    `<tr><td class="label">${g.home.abbrev || 'H'}</td>${hRow}<td class="total">${hTot}</td></tr>` +
    `</tbody>`;
  node.hidden = false;
}

const NHL_STAT_ORDER = [
  ['sog',    'SHOTS'],
  ['hits',   'HITS'],
  ['pp',     'POWER PLAY'],
  ['fo_pct', 'FACEOFFS'],
  ['blocks', 'BLK SHOTS'],
];
const NFL_STAT_ORDER = [
  ['total_yards', 'TOTAL YDS'],
  ['pass_yds',    'PASS YDS'],
  ['rush_yds',    'RUSH YDS'],
  ['top',         'POSSESSION'],
  ['turnovers',   'TURNOVERS'],
  ['third_down',  '3RD DOWN'],
];

function renderTeamStats(g) {
  const stats = g.team_stats;
  const order = state.league === 'nhl' ? NHL_STAT_ORDER : NFL_STAT_ORDER;
  const prev  = state.lastStats || {};
  const next  = {};

  for (const side of ['home', 'away']) {
    const node = $(`${side}-stats`);
    const s = stats && stats[side];
    if (!s || !Object.keys(s).length) { node.hidden = true; continue; }
    node.innerHTML = order
      .map(([k, lbl]) => {
        if (s[k] == null) return '';
        const key = `${side}.${k}`;
        next[key] = s[k];
        const changed = prev[key] != null && prev[key] !== s[k];
        const flash = changed ? ' flash' : '';
        return `<div class="s"><span class="l">${lbl}</span><span class="v${flash}">${s[k]}</span></div>`;
      })
      .filter(Boolean)
      .join('');
    node.hidden = !node.innerHTML;
  }
  state.lastStats = next;
}

function renderGoalies(g) {
  const goalies = g.goalies || {};
  for (const side of ['home', 'away']) {
    const node = $(`${side}-goalie`);
    const gl = goalies[side];
    if (!gl || !gl.name) { node.hidden = true; continue; }
    const num   = gl.number != null ? `#${gl.number} ` : '';
    const saves = gl.saves ? ` ${gl.saves}` : '';
    const sv    = gl.sv_pct ? ` ${gl.sv_pct}` : '';
    node.innerHTML =
      `<span class="g-tag">G</span>${num}${gl.name}${saves}${sv}`;
    node.hidden = false;
  }
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

    $('home-record').textContent = g.home.record || '';
    $('away-record').textContent = g.away.record || '';

    if (state.league === 'nhl') {
      $('last-play').textContent = g.last_penalty || '';
      $('situation').hidden = true;
    } else {
      $('last-play').textContent = (g.situation && g.situation.last_play) || '';
      renderSituation(g);
    }

    renderArena(g);
    renderPowerPlay(g);
    renderLineScore(g);
    renderTeamStats(g);
    renderGoalies(g);
    renderLeaders(g);

    $('ribbon-top-text').textContent =
      `${g.away.name || g.away.abbrev} at ${g.home.name || g.home.abbrev}` +
      `${g.venue ? ' · ' + g.venue : ''}` +
      `${g.period_label ? ' · ' + g.period_label : ''}` +
      `${g.clock ? ' ' + g.clock : ''}`;

    const tickerBits = [];
    tickerBits.push(`${g.away.abbrev} ${g.away.score ?? 0} – ${g.home.score ?? 0} ${g.home.abbrev}`);
    if (g.last_goal) {
      tickerBits.push(g.last_goal);
      state.lastGoalText = g.last_goal;
    }
    if (g.last_penalty) tickerBits.push(g.last_penalty);
    // Rotating stat callouts — these scroll past in the ribbon and give
    // that "random stats popping up" broadcast feel.
    const ts = g.team_stats || {};
    const a = ts.away || {}, h = ts.home || {};
    const cmp = (label, key) => {
      if (a[key] != null && h[key] != null) {
        tickerBits.push(`${label}: ${g.away.abbrev} ${a[key]} · ${g.home.abbrev} ${h[key]}`);
      }
    };
    cmp('SHOTS',      'sog');
    cmp('HITS',       'hits');
    cmp('FACEOFFS',   'fo_pct');
    cmp('BLOCKED',    'blocks');
    cmp('GIVEAWAYS',  'giveaways');
    cmp('TAKEAWAYS',  'takeaways');
    cmp('POWER PLAY', 'pp');
    cmp('PIM',        'pim');
    if (g.goalies) {
      for (const side of ['away', 'home']) {
        const gl = g.goalies[side];
        if (gl && gl.name) {
          tickerBits.push(`${g[side].abbrev} G: ${gl.name}${gl.saves ? ' ' + gl.saves : ''}${gl.sv_pct ? ' ' + gl.sv_pct : ''}`);
        }
      }
    }
    if (g.leaders) {
      const leadLabels = { goals: 'G', assists: 'A', points: 'PTS', shots: 'SOG', hits: 'HITS', blocks: 'BLK' };
      for (const side of ['away', 'home']) {
        const ld = g.leaders[side] || {};
        for (const [key, lbl] of Object.entries(leadLabels)) {
          if (ld[key] && ld[key].name) {
            tickerBits.push(`${g[side].abbrev} ${lbl} LDR: ${ld[key].name} (${ld[key].value})`);
          }
        }
      }
    }
    if (g.series && g.series.series_score) tickerBits.push(g.series.series_score);
    tickerBits.push(state.league.toUpperCase() + ' live · ' + new Date().toLocaleTimeString('en-US'));
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
  if (state.leaderRotateHandle) {
    clearInterval(state.leaderRotateHandle);
    state.leaderRotateHandle = null;
  }
  state.leaders = null;
  state.gameId = null;
  showView('picker');
  loadGames();
}

document.addEventListener('DOMContentLoaded', () => {
  const dateEl = $('date');
  dateEl.value = todayUS();
  $('league').addEventListener('change', loadGames);
  dateEl.addEventListener('input', () => autoFormatDate(dateEl));
  dateEl.addEventListener('change', loadGames);
  setupDatePicker();
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
