'use strict';
(() => {
  const store = window.JamesOffline;
  const owner = document.body.dataset.offlineOwner || '';
  const offlinePage = document.body.dataset.offlinePage === 'true';
  const notice = document.querySelector('#offline-save-status');
  let generation;
  let fetching = false;
  let blocked = false;
  const canUseWorker = 'serviceWorker' in navigator && window.isSecureContext;
  let offlineState = canUseWorker ? 'preparing' : 'unavailable';
  const say = text => { if (notice) notice.textContent = text; };
  function savedMessage(snapshot) {
    const time = new Date(snapshot.saved_at).toLocaleString('de-CH');
    say(offlineState === 'ready' ? 'Offline-Liste auf diesem Geraet bereit: ' + time + '.' :
      offlineState === 'preparing' ? 'Liste gespeichert. Offline-Start wird noch vorbereitet.' :
        'Liste gespeichert, aber Offline-Start ist hier derzeit nicht verfuegbar. Bitte spaeter online erneut oeffnen.');
  }
  const clear = () => {
    blocked = true;
    try { store.clear(localStorage, owner || undefined); } catch { /* Storage may be disabled. */ }
  };
  try {
    if (owner) generation = store.claim(localStorage, owner);
    else if (!offlinePage) store.clear(localStorage);
  } catch { say('Offline-Speicherung ist in diesem Browser nicht verfuegbar.'); }

  document.querySelectorAll('form[action="/logout"]').forEach(form => {
    form.addEventListener('submit', clear, { capture: true });
  });

  async function sync() {
    if (!owner || blocked || fetching || generation === undefined || !navigator.onLine) return;
    fetching = true;
    try {
      const response = await fetch('/api/offline-list', { cache: 'no-store', credentials: 'same-origin' });
      if (response.status === 401 || response.status === 403) {
        clear(); say('Bitte online neu anmelden, um die Einkaufsliste zu speichern.'); return;
      }
      if (!response.ok) throw new Error('snapshot');
      const snapshot = await response.json();
      if (snapshot.owner !== owner) { clear(); return; }
      if (!blocked && store.save(localStorage, owner, generation, snapshot)) {
        savedMessage(snapshot);
      }
    } catch { say('Offline-Stand konnte nicht aktualisiert werden. Ein vorhandener Stand bleibt erhalten.'); }
    finally { fetching = false; }
  }

  function showSnapshot() {
    const list = document.querySelector('#offline-items');
    if (!list) return;
    list.replaceChildren();
    let snapshot;
    try { snapshot = store.read(localStorage); } catch { /* Show empty state. */ }
    const valid = snapshot && Array.isArray(snapshot.items) && !Number.isNaN(Date.parse(snapshot.saved_at));
    document.querySelector('#offline-empty').hidden = !!valid;
    document.querySelector('#offline-clear').hidden = !valid;
    document.querySelector('#offline-heading').textContent = valid ? snapshot.household : 'Einkaufsliste offline';
    document.querySelector('#offline-time').textContent = valid ? 'Gespeicherter Stand: ' +
      new Date(snapshot.saved_at).toLocaleString('de-CH') + '. Seitdem kann sich die Liste geaendert haben.' : '';
    if (!valid) return;
    if (!snapshot.items.length) {
      const empty = document.createElement('li');
      empty.textContent = 'Zum gespeicherten Zeitpunkt war nichts auf der Einkaufsliste.';
      list.appendChild(empty);
    }
    for (const item of snapshot.items) {
      const row = document.createElement('li');
      row.className = 'shopping-row';
      const name = document.createElement('strong');
      name.textContent = item.name;
      const details = document.createElement('p');
      details.className = 'small muted';
      details.textContent = `${item.quantity} ${item.unit} · ${item.category} · ${item.source}`;
      const content = document.createElement('div');
      content.append(name, details); row.appendChild(content); list.appendChild(row);
    }
  }
  document.querySelector('#offline-clear')?.addEventListener('click', () => { clear(); showSnapshot(); });
  if (offlinePage) {
    showSnapshot();
    window.addEventListener('storage', showSnapshot);
  } else {
    sync();
    window.addEventListener('online', sync);
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') sync(); });
    window.addEventListener('pageshow', event => { if (event.persisted) sync(); });
  }
  if (canUseWorker) {
    navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' })
      .then(() => navigator.serviceWorker.ready).then(() => {
        offlineState = 'ready';
        if (owner && !blocked) {
          try { const snapshot = store.read(localStorage); if (snapshot?.owner === owner) savedMessage(snapshot); }
          catch { /* Snapshot storage can be unavailable. */ }
        }
      }).catch(() => {
      offlineState = 'unavailable';
      say('Offline-Start ist noch nicht verfuegbar. Bitte spaeter online erneut oeffnen.');
    });
  }
  const button = document.querySelector('#install-app');
  let installEvent;
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault(); installEvent = event;
    if (button && !window.matchMedia('(display-mode: standalone)').matches) button.hidden = false;
  });
  button?.addEventListener('click', async () => {
    if (!installEvent) return;
    await installEvent.prompt();
    await installEvent.userChoice;
    installEvent = null; button.hidden = true;
  });
  window.addEventListener('appinstalled', () => { if (button) button.hidden = true; });
})();
