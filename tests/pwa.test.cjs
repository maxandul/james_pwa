const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const store = require('../james/static/offline-store.js');

function storage() {
  const entries = new Map();
  return { getItem: key => entries.get(key) || null, setItem: (key, value) => entries.set(key, value), clear: () => entries.clear() };
}
test('switching accounts discards the previous household snapshot', () => {
  const s = storage();
  const a = store.claim(s, 'alice');
  assert.equal(store.save(s, 'alice', a, { owner: 'alice', items: ['Coffee'] }), true);
  store.claim(s, 'bob');
  assert.equal(store.read(s), null);
  assert.equal(store.save(s, 'alice', a, { owner: 'alice' }), false);
});
test('logout prevents a delayed response from restoring private data', () => {
  const s = storage();
  const generation = store.claim(s, 'alice');
  store.clear(s);
  assert.equal(store.save(s, 'alice', generation, { owner: 'alice' }), false);
  assert.equal(store.read(s), null);
});
test('clearing browser storage then signing in again invalidates old responses', () => {
  const s = storage();
  const generation = store.claim(s, 'alice');
  s.clear(); store.claim(s, 'alice');
  assert.equal(store.save(s, 'alice', generation, { owner: 'alice' }), false);
});
test('a stale tab cannot clear the new account or save a foreign response', () => {
  const s = storage();
  const generation = store.claim(s, 'bob');
  store.save(s, 'bob', generation, { owner: 'bob', items: [] });
  store.clear(s, 'alice');
  assert.equal(store.read(s).owner, 'bob');
  assert.equal(store.save(s, 'bob', generation, { owner: 'alice' }), false);
});
test('a slower tab cannot replace a newer snapshot with an older one', () => {
  const s = storage(); const generation = store.claim(s, 'alice');
  store.save(s, 'alice', generation, { owner: 'alice', saved_at: '2026-11-01T12:00:02.000000Z', items: [] });
  assert.equal(store.save(s, 'alice', generation, { owner: 'alice', saved_at: '2026-11-01T12:00:01.000000Z', items: ['old'] }), false);
  assert.deepEqual(store.read(s).items, []);
});

function worker() {
  const listeners = {};
  const saved = [];
  const matched = [];
  const deleted = [];
  const context = vm.createContext({ URL, Request, Set, Promise,
    self: { location: { origin: 'https://james.test' }, clients: { claim: async () => {} },
      addEventListener: (name, callback) => { listeners[name] = callback; } },
    fetch: async () => { throw new Error('offline'); },
    caches: { open: async () => ({ addAll: async paths => {
      assert.ok(paths.every(request => request.credentials === 'omit'));
      saved.push(...paths.map(request => new URL(request.url).pathname + new URL(request.url).search));
    } }),
      match: async path => { matched.push(path); return 'cached shell'; },
      keys: async () => ['james-shell-v1', 'james-shell-v2', 'other-app'],
      delete: async key => deleted.push(key) },
  });
  vm.runInContext(fs.readFileSync('james/static/sw.js', 'utf8'), context);
  return { listeners, saved, matched, deleted };
}
test('precache contains only public assets and the anonymous offline shell', async () => {
  const w = worker(); let done;
  w.listeners.install({ waitUntil: promise => { done = promise; } }); await done;
  assert.ok(w.saved.includes('/offline'));
  assert.ok(w.saved.every(path => path === '/offline' || path.startsWith('/static/') || path === '/manifest.webmanifest'));
});
test('private APIs, account pages and all writes bypass the worker cache', () => {
  const w = worker(); let intercepted = 0;
  for (const [path, method, mode] of [['/api/offline-list', 'GET', 'cors'], ['/login', 'GET', 'navigate'],
    ['/join?token=private', 'GET', 'navigate'], ['/items/1/action', 'POST', 'navigate'], ['/logout', 'POST', 'navigate']]) {
    w.listeners.fetch({ request: { url: 'https://james.test' + path, method, mode }, respondWith: () => { intercepted++; } });
  }
  assert.equal(intercepted, 0);
});
test('offline list navigation falls back only to the anonymous shell', async () => {
  const w = worker(); let response;
  w.listeners.fetch({ request: { url: 'https://james.test/shopping?source=Coop', method: 'GET', mode: 'navigate' },
    respondWith: promise => { response = promise; } });
  assert.equal(await response, 'cached shell');
  assert.deepEqual(w.matched, ['/offline']);
});
test('worker upgrades clean only obsolete James shell caches', async () => {
  const w = worker(); let done;
  w.listeners.activate({ waitUntil: promise => { done = promise; } }); await done;
  assert.deepEqual(w.deleted, ['james-shell-v1']);
});

function page(storage, offline, fetch, serviceWorker) {
  const elements = new Map();
  const element = () => ({ children: [], listeners: {}, textContent: '', hidden: false,
    append(...nodes) { this.children.push(...nodes); }, appendChild(node) { this.children.push(node); },
    replaceChildren() { this.children = []; }, addEventListener(name, callback) { this.listeners[name] = callback; } });
  for (const name of ['#offline-items', '#offline-empty', '#offline-clear', '#offline-heading', '#offline-time', '#offline-save-status', '#install-app', 'logout']) elements.set(name, element());
  const document = { body: { dataset: offline ? { offlinePage: 'true' } : { offlineOwner: 'alice' } },
    querySelector: name => elements.get(name) || null,
    querySelectorAll: () => [elements.get('logout')], createElement: element, addEventListener() {} };
  const navigator = { onLine: true };
  if (serviceWorker) navigator.serviceWorker = serviceWorker;
  const context = vm.createContext({ window: { JamesOffline: store, isSecureContext: !!serviceWorker, addEventListener() {} },
    document, navigator, localStorage: storage, fetch, Date });
  vm.runInContext(fs.readFileSync('james/static/pwa.js', 'utf8'), context);
  return elements;
}
test('offline UI renders names as plain text and clears the visible snapshot', () => {
  const s = storage(); const generation = store.claim(s, 'alice');
  store.save(s, 'alice', generation, { owner: 'alice', household: 'Test household', saved_at: '2026-11-01T12:00:00Z',
    items: [{ name: '<img src=x onerror=alert(1)>', quantity: 2, unit: 'Packung', category: 'Vorrat', source: 'Laden' }] });
  const elements = page(s, true);
  assert.equal(elements.get('#offline-items').children[0].children[0].children[0].textContent, '<img src=x onerror=alert(1)>');
  elements.get('#offline-clear').listeners.click();
  assert.equal(store.read(s), null);
  assert.equal(elements.get('#offline-items').children.length, 0);
  assert.equal(elements.get('#offline-empty').hidden, false);
});
test('logout while a snapshot fetch is pending cannot restore the list', async () => {
  const s = storage(); let resolve;
  const pending = new Promise(done => { resolve = done; });
  const elements = page(s, false, () => pending);
  elements.get('logout').listeners.submit();
  resolve({ ok: true, status: 200, json: async () => ({ owner: 'alice', saved_at: '2026-11-01T12:00:00Z', items: [] }) });
  await new Promise(done => setImmediate(done));
  assert.equal(store.read(s), null);
});
test('offline ready is announced only after shell installation completes', async () => {
  const s = storage(); let ready;
  const worker = { register: async () => ({}), ready: new Promise(done => { ready = done; }) };
  const elements = page(s, false, async () => ({ ok: true, status: 200,
    json: async () => ({ owner: 'alice', saved_at: '2026-11-01T12:00:00.000000Z', items: [] }) }), worker);
  await new Promise(done => setImmediate(done));
  assert.match(elements.get('#offline-save-status').textContent, /noch vorbereitet/);
  ready({}); await new Promise(done => setImmediate(done));
  assert.match(elements.get('#offline-save-status').textContent, /Offline-Liste auf diesem Geraet bereit/);
});
