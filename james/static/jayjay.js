'use strict';
(() => {
  const launcher = document.querySelector('#jayjay-launcher');
  const dialog = document.querySelector('#jayjay-dialog');
  if (!launcher || !dialog || typeof dialog.showModal !== 'function') return;
  const content = document.querySelector('#jayjay-content');
  const status = document.querySelector('#jayjay-status');
  const reload = document.querySelector('#jayjay-reload');
  const refresh = document.querySelector('#jayjay-refresh');
  const owner = document.body.dataset.offlineOwner;
  const stateKey = 'james-jayjay-open:' + owner;
  let loaded = false, busy = false, blocked = false;
  let controller;
  window.JamesChat = {hasPendingInput: () => busy || !!content.querySelector('textarea')?.value.trim()};
  const remember = open => { try { sessionStorage.setItem(stateKey, open ? '1' : '0'); } catch { /* optional */ } };
  const say = message => { status.textContent = message; };
  function clearPrivateChat() {
    blocked = true; controller?.abort(); content.replaceChildren(); remember(false);
    if (dialog.open) dialog.close();
  }

  async function refreshPage() {
    window.dispatchEvent(new Event('james:household-changed'));
    if (!['/', '/shopping'].includes(window.location.pathname) || !window.JamesPage?.canRefresh()) {
      refresh.hidden = false;
      return;
    }
    try {
      const response = await fetch(window.location.href, {cache: 'no-store', credentials: 'same-origin'});
      if (!response.ok || response.redirected) throw new Error('page');
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (blocked || page.body.dataset.offlineOwner !== owner) return;
      // An edit may have started while the updated view was in flight.
      if (!window.JamesPage.canRefresh()) { refresh.hidden = false; return; }
      document.querySelector('main').replaceChildren(...page.querySelector('main').childNodes);
      window.dispatchEvent(new Event('james:content-updated'));
      refresh.hidden = true;
    } catch { refresh.hidden = false; }
  }

  async function request(form) {
    if (busy || blocked) return;
    if (!navigator.onLine) { say('JayJay braucht eine Internetverbindung. Deine Eingabe bleibt erhalten.'); return; }
    busy = true;
    controller = new AbortController();
    content.setAttribute('aria-busy', 'true');
    const button = form?.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    say(form ? 'JayJay kuemmert sich darum …' : 'JayJay wird geholt …');
    reload.hidden = true;
    try {
      const response = await fetch('/jayjay?panel=1', {
        method: form ? 'POST' : 'GET', body: form ? new FormData(form) : undefined,
        credentials: 'same-origin', cache: 'no-store', signal: controller.signal
      });
      if (response.redirected || !response.headers.get('content-type')?.includes('application/json')) throw new Error('session');
      const data = await response.json();
      if (blocked) return;
      if (data.owner !== owner) { blocked = true; content.replaceChildren(); throw new Error('session'); }
      content.innerHTML = data.html;
      loaded = true;
      say(response.ok ? '' : 'Bitte pruefe den Hinweis im Chat.');
      content.scrollTop = content.scrollHeight;
      if (data.changed) await refreshPage();
      if (form && dialog.open) content.querySelector('textarea')?.focus({preventScroll: true});
    } catch {
      if (!blocked) {
        say(form ? 'Die Bestaetigung fehlt. Bitte lade zuerst den Verlauf neu und pruefe gespeicherte Aenderungen. Dein Auftrag wird nicht automatisch wiederholt.' : 'Der Chat ist gerade nicht erreichbar. Bitte pruefe die Verbindung oder melde dich neu an.');
        reload.hidden = false;
      }
    } finally {
      busy = false;
      content.setAttribute('aria-busy', 'false');
      if (button) button.disabled = !navigator.onLine;
    }
  }

  function open() {
    if (blocked) { window.location.reload(); return; }
    if (!dialog.open) dialog.showModal();
    launcher.setAttribute('aria-expanded', 'true');
    remember(true);
    if (!loaded) request();
  }
  launcher.setAttribute('aria-expanded', 'false');
  launcher.addEventListener('click', event => { event.preventDefault(); open(); });
  document.querySelector('#jayjay-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => { remember(false); launcher.setAttribute('aria-expanded', 'false'); launcher.focus(); });
  content.addEventListener('submit', event => {
    if (!event.target.matches('[data-jayjay-form]')) return;
    event.preventDefault();
    request(event.target);
  });
  reload.addEventListener('click', () => request());
  refresh.addEventListener('click', () => {
    if (window.JamesPage?.canRefresh()) { window.location.reload(); return; }
    if (window.confirm('Die App-Ansicht neu laden? Ungespeicherte Eingaben auf dieser Seite gehen dabei verloren.')) window.location.reload();
  });
  // Leave action links in the app, rather than loading a page inside the panel.
  content.addEventListener('click', event => {
    if (event.target.closest('a')) remember(false);
  });
  document.querySelectorAll('form[action="/logout"]').forEach(form => form.addEventListener('submit', () => {
    clearPrivateChat();
  }, {capture: true}));
  window.addEventListener('storage', event => {
    if (event.key !== null && event.key !== 'james-offline-v1') return;
    try { if (!event.newValue || JSON.parse(event.newValue).owner !== owner) clearPrivateChat(); }
    catch { clearPrivateChat(); }
  });
  window.addEventListener('pageshow', event => {
    if (event.persisted) { content.replaceChildren(); loaded = false; if (dialog.open) request(); }
  });
  try { if (sessionStorage.getItem(stateKey) === '1') open(); } catch { /* optional */ }
})();
