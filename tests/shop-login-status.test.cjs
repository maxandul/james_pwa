const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const source = readFileSync(require('node:path').join(__dirname, '../james/static/shop-login-status.js'), 'utf8');
function setup() {
  const timers = [], listeners = {};
  let reloads = 0, reads = 0;
  const window = {setTimeout: f => timers.push(f), location: {reload: () => reloads++}};
  const document = {hidden: false,
    querySelector: () => ({dataset: {statusUrl: '/shop-login/1/status', state: 'accepted', progress: 'email_submitted'}}),
    addEventListener: (name, f) => {listeners[name] = f;}};
  let next = {state: 'pending', progress: 'manual_fields'};
  const fetch = async () => {reads++; return {ok: true, redirected: false, json: async () => next};};
  vm.runInNewContext(source, {window, document, navigator: {onLine: true}, fetch});
  return {timers, listeners, document, counts: () => ({reloads, reads}), setNext: v => {next = v;}};
}
test('new manual step automatically appears', async () => {
  const s = setup(); await s.timers.shift()();
  assert.deepEqual(s.counts(), {reloads: 1, reads: 1});
});
test('never reload over typed data or a submitted form', async () => {
  for (const event of ['input', 'change', 'submit']) {
    const s = setup(); s.listeners[event](); await s.timers.shift()();
    assert.deepEqual(s.counts(), {reloads: 0, reads: 0});
  }
});
test('unchanged status schedules another read; hidden page does not fetch', async () => {
  const s = setup(); s.setNext({state: 'accepted', progress: 'email_submitted'});
  await s.timers.shift()(); assert.equal(s.timers.length, 1);
  s.document.hidden = true; await s.timers.shift()();
  assert.deepEqual(s.counts(), {reloads: 0, reads: 1});
});
