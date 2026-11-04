'use strict';
(() => {
  const launcher = document.querySelector('#jayjay-launcher');
  const dialog = document.querySelector('#jayjay-dialog');
  const standalone = dialog?.tagName === 'SECTION';
  if (!dialog || (!standalone && (!launcher || typeof dialog.showModal !== 'function'))) return;
  const content = document.querySelector('#jayjay-content');
  const status = document.querySelector('#jayjay-status');
  const reload = document.querySelector('#jayjay-reload');
  const refresh = document.querySelector('#jayjay-refresh');
  const owner = document.body.dataset.offlineOwner;
  const stateKey = 'james-jayjay-open:' + owner;
  const conversationKey = 'james-jayjay-conversation:' + owner;
  let loaded = standalone, busy = false, blocked = false, uncertain = false;
  let controller, activeUrl = '/jayjay?panel=1';
  const drafts = new Map();
  const field = () => content.querySelector('textarea[name="message"]');
  const identifier = () => content.querySelector('[name="conversation_id"]')?.value || '';
  const draftKey = () => content.querySelector('[data-jayjay-form]')?.dataset.saved === 'false' ? 'new' : identifier();
  const remember = open => { try { sessionStorage.setItem(stateKey, open ? '1' : '0'); } catch { /* optional */ } };
  const say = message => { status.textContent = message; };
  window.JamesChat = {hasPendingInput: () => busy || uncertain || !!field()?.value.trim()};
  try {
    const last = sessionStorage.getItem(conversationKey);
    if (!standalone && last === 'new') activeUrl += '&new=1';
    if (!standalone && /^[0-9a-f-]{36}$/.test(last || '')) activeUrl += '&conversation=' + last;
  } catch { /* optional */ }

  function clearPrivateChat() {
    blocked = true; controller?.abort(); drafts.clear(); content.replaceChildren(); remember(false);
    try { sessionStorage.removeItem(conversationKey); } catch { /* optional */ }
    if (!standalone && dialog.open) dialog.close();
  }
  function rememberConversation(value) {
    if (typeof value !== 'string' || !/^[0-9a-f-]{36}$/.test(value)) return;
    activeUrl = '/jayjay?panel=1&conversation=' + encodeURIComponent(value);
    try { sessionStorage.setItem(conversationKey, value); } catch { /* optional */ }
  }
  function setBusy(value) {
    busy = value;
    content.setAttribute('aria-busy', String(value));
    if (field()) field().readOnly = value;
    content.querySelectorAll?.('[data-jayjay-form] button[type="submit"]').forEach(button => {button.disabled = value || uncertain || !navigator.onLine;});
  }
  function scrollToLatest() {
    const thread = content.querySelector('[data-jayjay-thread]');
    if (thread) thread.scrollTop = thread.scrollHeight;
  }
  async function refreshPage() {
    window.dispatchEvent(new Event('james:household-changed'));
    if (!['/', '/shopping'].includes(window.location.pathname) || !window.JamesPage?.canRefresh()) {
      refresh.hidden = false; return;
    }
    try { refresh.hidden = await window.JamesPage.refresh(); }
    catch { refresh.hidden = false; }
  }
  async function request(form, url = activeUrl) {
    if (busy || blocked) return;
    if (!navigator.onLine) { say('JayJay braucht eine Internetverbindung. Deine Eingabe bleibt erhalten.'); return; }
    const writing = !!form?.matches('[data-jayjay-form]');
    if (writing && uncertain) { say('Bitte zuerst den Verlauf neu laden und den letzten Auftrag prüfen.'); return; }
    const oldId = draftKey();
    if (field()) drafts.set(oldId, field().value);
    setBusy(true);
    controller = new AbortController();
    say(writing ? 'JayJay kümmert sich darum … Du kannst den Chat schliessen.' : 'Gespräch wird geladen …');
    reload.hidden = true;
    try {
      const response = await fetch(url, {method: form ? 'POST' : 'GET', body: form ? new FormData(form) : undefined,
        credentials: 'same-origin', cache: 'no-store', signal: controller.signal});
      if (response.status === 404 && !form) activeUrl = '/jayjay?panel=1';
      if (response.redirected || !response.headers.get('content-type')?.includes('application/json')) throw new Error('session');
      const data = await response.json();
      if (blocked) return;
      if (data.owner !== owner) { clearPrivateChat(); return; }
      if (response.status === 404 && !form) {
        // The conversation may have been deleted in another tab. Never retry a write.
        activeUrl = '/jayjay?panel=1';
        throw new Error('missing');
      }
      if (typeof data.html !== 'string') throw new Error('invalid');
      content.innerHTML = data.html;
      loaded = true; uncertain = false;
      if (data.saved) rememberConversation(data.conversation_id);
      else { try { sessionStorage.setItem(conversationKey, 'new'); } catch { /* optional */ } }
      if (data.active_url) activeUrl = data.active_url;
      if (writing && response.ok) drafts.delete(oldId);
      if (form?.matches('[data-jayjay-delete]') && response.ok) drafts.delete(oldId);
      const draft = drafts.get(draftKey());
      if (field() && draft !== undefined && !(writing && response.ok)) field().value = draft;
      if (!response.ok && writing) uncertain = true;
      say(response.ok ? '' : 'Bitte prüfe den Hinweis im Chat.');
      if (!new URL(url, window.location.href).searchParams.has('page')) scrollToLatest();
      if (data.changed) await refreshPage();
      if (writing && (standalone || dialog.open)) field()?.focus({preventScroll: true});
    } catch {
      if (!blocked) {
        if (form) uncertain = true;
        say(form ? 'Die Bestätigung fehlt. Bitte lade zuerst den Verlauf neu und prüfe gespeicherte Änderungen. Dein Auftrag wird nicht automatisch wiederholt.' : 'Der Chat ist gerade nicht erreichbar. Bitte prüfe die Verbindung oder melde dich neu an.');
        reload.hidden = false;
      }
    } finally { setBusy(false); }
  }
  function open() {
    if (blocked) { window.location.reload(); return; }
    if (!dialog.open) dialog.showModal();
    launcher.setAttribute('aria-expanded', 'true'); remember(true);
    if (!loaded) request();
  }
  if (launcher) {
    launcher.setAttribute('aria-expanded', 'false');
    launcher.addEventListener('click', event => { event.preventDefault(); open(); });
    document.querySelector('#jayjay-close')?.addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => { remember(false); launcher.setAttribute('aria-expanded', 'false'); launcher.focus(); });
  }
  document.querySelector('#jayjay-expand')?.addEventListener('click', event => {
    const expanded = dialog.classList.toggle('jayjay--expanded');
    event.currentTarget.setAttribute('aria-pressed', String(expanded));
    event.currentTarget.setAttribute('aria-label', expanded ? 'Chat verkleinern' : 'Chat vergrössern');
  });
  content.addEventListener('submit', event => {
    const form = event.target;
    if (form.matches('[data-jayjay-search]')) {
      event.preventDefault();
      const url = new URL('/jayjay?panel=1&history=1', window.location.href);
      url.searchParams.set('q', new FormData(form).get('q') || '');
      if (draftKey() !== 'new' && identifier()) url.searchParams.set('conversation', identifier());
      else url.searchParams.set('new', '1');
      request(null, url.pathname + url.search); return;
    }
    if (!form.matches('[data-jayjay-form], [data-jayjay-manage]')) return;
    event.preventDefault();
    if (form.matches('[data-jayjay-delete]') && !window.confirm('Diesen Chat löschen? Gespeicherte Haushaltsänderungen bleiben bestehen.')) return;
    request(form, '/jayjay?panel=1');
  });
  content.addEventListener('click', event => {
    const historyButton = event.target.closest('[data-jayjay-history]');
    if (historyButton) {
      event.preventDefault();
      const history = content.querySelector('#jayjay-history');
      history.hidden = !history.hidden;
      historyButton.setAttribute('aria-expanded', String(!history.hidden)); return;
    }
    const suggestion = event.target.closest('[data-jayjay-prompt]');
    if (suggestion && !busy && field()) {field().value = suggestion.dataset.jayjayPrompt; field().focus(); return;}
    const link = event.target.closest('a[data-jayjay-nav]');
    if (link && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
      event.preventDefault();
      const url = new URL(link.href, window.location.href);
      if (url.origin !== new URL(window.location.href).origin || url.pathname !== '/jayjay') return;
      url.searchParams.set('panel', '1');
      request(null, url.pathname + url.search); return;
    }
    if (event.target.closest('a')) remember(false);
  });
  content.addEventListener('keydown', event => {
    if (event.target === field() && event.key === 'Enter' && !event.shiftKey && !event.isComposing && !event.ctrlKey && !event.metaKey && !event.altKey) {
      // Touch keyboards retain their normal newline behaviour.
      if (window.matchMedia?.('(pointer: fine)').matches) {event.preventDefault(); if (!busy && !uncertain) event.target.form.requestSubmit();}
    }
  });
  reload.addEventListener('click', () => request());
  refresh.addEventListener('click', () => {
    if (window.JamesPage?.canRefresh()) { refreshPage(); return; }
    if (window.confirm('Die App-Ansicht neu laden? Ungespeicherte Eingaben auf dieser Seite gehen dabei verloren.')) window.location.reload();
  });
  document.querySelectorAll('form[action="/logout"]').forEach(form => form.addEventListener('submit', clearPrivateChat, {capture: true}));
  window.addEventListener('storage', event => {
    if (event.key !== null && event.key !== 'james-offline-v1') return;
    try { if (!event.newValue || JSON.parse(event.newValue).owner !== owner) clearPrivateChat(); }
    catch { clearPrivateChat(); }
  });
  window.addEventListener('pageshow', event => {
    if (event.persisted) {content.replaceChildren(); drafts.clear(); loaded = false; if (standalone || dialog.open) request();}
  });
  window.addEventListener('online', () => setBusy(busy));
  window.addEventListener('offline', () => setBusy(busy));
  if (standalone) {if (draftKey() !== 'new') rememberConversation(identifier()); else activeUrl = '/jayjay?panel=1&new=1'; scrollToLatest();}
  else {try {if (sessionStorage.getItem(stateKey) === '1') open();} catch { /* optional */ }}
})();
