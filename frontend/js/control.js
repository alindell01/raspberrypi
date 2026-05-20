const $ = (id) => document.getElementById(id);

const state = {
  knownVersion: -1,
  loadingGames: false,
};

function todayYMD() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function setHint(msg, kind) {
  const el = $('hint');
  el.textContent = msg || '';
  el.classList.remove('error', 'ok');
  if (kind) el.classList.add(kind);
}

async function loadGames() {
  const league = $('league').value;
  const date   = $('date').value || todayYMD();
  const sel    = $('game');
  state.loadingGames = true;
  sel.innerHTML = '<option>Loading…</option>';
  sel.disabled = true;
  try {
    const r = await fetch(`/api/games?league=${league}&date=${date}`);
    if (!r.ok) throw new Error(r.statusText);
    const games = await r.json();
    if (!games.length) {
      sel.innerHTML = '<option value="">No games on this date</option>';
      $('show').disabled = true;
    } else {
      sel.innerHTML = games.map(g => {
        const label = g.label || `${g.away?.abbrev || ''} @ ${g.home?.abbrev || ''}`;
        return `<option value="${g.id}">${label}</option>`;
      }).join('');
      $('show').disabled = false;
    }
    sel.disabled = false;
  } catch (err) {
    sel.innerHTML = '<option value="">Couldn\'t load games</option>';
    setHint(`Couldn't load games: ${err.message}`, 'error');
  } finally {
    state.loadingGames = false;
  }
}

async function postConfig(updates) {
  try {
    const r = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    if (!r.ok) throw new Error(r.statusText);
    const data = await r.json();
    state.knownVersion = data.version;
    return data;
  } catch (err) {
    setHint(`Save failed: ${err.message}`, 'error');
    throw err;
  }
}

async function pullConfig() {
  try {
    const r = await fetch('/api/config');
    if (!r.ok) return;
    const data = await r.json();
    if (data.version === state.knownVersion) return;
    state.knownVersion = data.version;
    applyConfigToUI(data.config);
  } catch {
    // ignore — next poll will retry
  }
}

function applyConfigToUI(cfg) {
  if (cfg.league) $('league').value = cfg.league;
  if (cfg.date)   $('date').value   = cfg.date;
  if (cfg.theme)  $('theme').value  = cfg.theme;
  if (cfg.delay_seconds != null) $('delay').value = String(cfg.delay_seconds);
  updateNowLabel(cfg);
}

function updateNowLabel(cfg) {
  const now = $('now');
  if (!cfg.running) {
    now.textContent = 'TV is on the picker';
    return;
  }
  const gid = cfg.game_id ? ` · game ${cfg.game_id}` : '';
  now.textContent = `TV is showing ${cfg.league?.toUpperCase() || ''}${gid}`;
}

async function onShow() {
  const gameId = $('game').value;
  if (!gameId) { setHint('Pick a game first', 'error'); return; }
  setHint('Sending…');
  try {
    await postConfig({
      league:        $('league').value,
      date:          $('date').value || todayYMD(),
      game_id:       gameId,
      theme:         $('theme').value,
      delay_seconds: parseInt($('delay').value, 10) || 0,
      running:       true,
    });
    setHint('Now showing on TV.', 'ok');
  } catch {}
}

async function onStop() {
  setHint('Sending…');
  try {
    await postConfig({ running: false });
    setHint('TV returned to picker.', 'ok');
  } catch {}
}

document.addEventListener('DOMContentLoaded', async () => {
  $('date').value = todayYMD();

  // Pull current config first so UI matches whatever the TV is showing.
  await pullConfig();
  await loadGames();

  $('league').addEventListener('change', loadGames);
  $('date').addEventListener('change', loadGames);

  $('theme').addEventListener('change', () => {
    postConfig({ theme: $('theme').value }).catch(() => {});
  });
  $('delay').addEventListener('change', () => {
    postConfig({ delay_seconds: parseInt($('delay').value, 10) || 0 }).catch(() => {});
  });

  $('show').addEventListener('click', onShow);
  $('stop').addEventListener('click', onStop);

  // Light-touch poll so the "now showing" header stays accurate when the
  // TV is also driven locally or from another device.
  setInterval(pullConfig, 2000);
});
