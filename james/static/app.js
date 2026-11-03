'use strict';

const invitation = document.querySelector('#invitation-token');
if (invitation && window.location.hash) {
  const token = window.location.hash.slice(1);
  if (/^[A-Za-z0-9_-]{32,100}$/.test(token)) invitation.value = token;
  window.history.replaceState(null, '', window.location.pathname);
}
const copyButton = document.querySelector('#copy-invite');
if (copyButton) copyButton.addEventListener('click', async () => {
  const field = document.querySelector('#invite-link');
  try {
    await navigator.clipboard.writeText(field.value);
    document.querySelector('#copy-feedback').textContent = 'Link kopiert.';
  } catch {
    field.select();
    document.querySelector('#copy-feedback').textContent = 'Bitte den markierten Link manuell kopieren.';
  }
});

(() => {
  const owner = document.body.dataset.offlineOwner;
  const feedback = document.querySelector('#action-feedback');
  const dirtyForms = new Set();
  let edited = false, submitting = false, refreshing = false, generation = 0;
  const listPage = () => document.querySelector('main[data-list-page]');
  const rowOf = element => element?.closest('[data-item-id]');
  const rows = () => [...document.querySelectorAll('main [data-item-id]')];
  const isPost = form => form.method.toLowerCase() === 'post';
  const actionForm = form => !!listPage() && isPost(form) &&
    /^\/(items\/\d+\/action|activity\/\d+\/undo)$/.test(new URL(form.action).pathname);

  function onlineState() {
    const offline = !navigator.onLine;
    const banner = document.querySelector('#offline-banner');
    if (banner) banner.hidden = !offline;
    document.querySelectorAll('form[method="post"] button[type="submit"]').forEach(button => {
      if (!button.closest('.jayjay')) button.disabled = offline || submitting;
    });
  }
  const markEdited = event => {
    if (event.target.closest('.jayjay')) return;
    const row = rowOf(event.target);
    if (row && event.target.form) dirtyForms.add(event.target.form);
    else edited = true;
  };
  document.addEventListener('input', markEdited);
  document.addEventListener('change', markEdited);
  window.addEventListener('online', onlineState);
  window.addEventListener('offline', onlineState);
  window.addEventListener('james:content-updated', onlineState);

  function anchor(excluded) {
    const visible = rows().filter(row => row.dataset.itemId !== excluded && row.getBoundingClientRect().bottom > 0);
    // Prefer the first visible row. If the submitted row disappears, its neighbour anchors the viewport.
    const row = visible[0] || rows().find(row => row.dataset.itemId === excluded);
    return row ? {id: row.dataset.itemId, top: row.getBoundingClientRect().top, y: window.scrollY,
      candidates: visible.slice(0, 12).map(node => ({id: node.dataset.itemId, top: node.getBoundingClientRect().top}))} : {y: window.scrollY};
  }
  function restoreAnchor(saved) {
    const match = (saved.candidates || [saved]).map(candidate => ({candidate,
      row: candidate.id && document.querySelector(`[data-item-id="${CSS.escape(candidate.id)}"]`)})).find(entry => entry.row);
    window.scrollTo({top: match ? window.scrollY + match.row.getBoundingClientRect().top - match.candidate.top : saved.y, behavior: 'instant'});
  }
  function positionKey() {
    const url = new URL(window.location.href);
    url.searchParams.delete('undo');
    url.searchParams.sort();
    return `james-position:${owner}:${url.pathname}${url.search}`;
  }
  function rememberPosition() {
    if (!listPage()) return;
    try { sessionStorage.setItem(positionKey(), JSON.stringify(anchor())); } catch { /* optional */ }
  }
  function recallPosition() {
    if (!listPage()) return;
    try {
      const saved = JSON.parse(sessionStorage.getItem(positionKey()));
      if (saved) restoreAnchor(saved);
    } catch { /* optional */ }
  }
  window.addEventListener('pagehide', rememberPosition);
  document.addEventListener('click', event => {
    if (event.target.closest('a[href]')) rememberPosition();
    const menu = document.querySelector('.nav-more[open]');
    if (menu && !menu.contains(event.target)) menu.open = false;
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') document.querySelector('.nav-more[open]')?.removeAttribute('open');
  });

  function showFeedback(page, message) {
    if (!feedback) return;
    const label = document.createElement('span');
    label.textContent = message || page.querySelector('.notice:not(#offline-banner)')?.textContent || 'Gespeichert.';
    feedback.replaceChildren(label);
    const undo = page.querySelector('.undo form');
    if (undo) feedback.append(undo.cloneNode(true));
    const close = document.createElement('button');
    close.type = 'button'; close.className = 'feedback-close';
    close.textContent = '×'; close.setAttribute('aria-label', 'Hinweis schliessen');
    close.addEventListener('click', () => { feedback.hidden = true; });
    feedback.append(close); feedback.hidden = false;
  }

  function applyPage(page, {submittedRow, submittedForm, notify = false} = {}) {
    const current = listPage();
    const next = page.querySelector('main[data-list-page]');
    if (!current || !next || current.dataset.listPage !== next.dataset.listPage ||
        page.body.dataset.offlineOwner !== owner) return false;
    const saved = anchor(submittedRow);
    const focus = document.activeElement;
    const focusedRow = rowOf(focus)?.dataset.itemId;
    const focusedName = focus?.getAttribute('name');
    const focusedId = focus?.id;
    const focusedAction = focus?.closest('form')?.querySelector('[name="action"]')?.value;
    // Validate all draft destinations before moving any DOM node. Preserve the original
    // version/request identifiers, so a concurrent write still produces a conflict.
    const preserved = [];
    for (const oldForm of dirtyForms) {
      if (oldForm === submittedForm || !oldForm.isConnected) continue;
      const id = rowOf(oldForm)?.dataset.itemId;
      const newRow = id && next.querySelector(`[data-item-id="${CSS.escape(id)}"]`);
      const action = oldForm.querySelector('[name="action"]')?.value;
      const newForm = [...(newRow?.querySelectorAll('form') || [])].find(candidate =>
        candidate.getAttribute('action') === oldForm.getAttribute('action') &&
        candidate.querySelector('[name="action"]')?.value === action);
      if (!newForm) return false;
      preserved.push([newForm, oldForm]);
    }
    for (const [newForm, oldForm] of preserved) newForm.replaceWith(oldForm);
    const opened = [...current.querySelectorAll('details[id][open]')].map(detail => detail.id);
    for (const old of current.querySelectorAll('[data-preserve]')) {
      next.querySelector(`[data-preserve="${CSS.escape(old.dataset.preserve)}"]`)?.replaceWith(old);
    }
    if (notify) {
      showFeedback(page);
      next.querySelector('.undo')?.remove();
      next.querySelectorAll('.notice:not(#offline-banner)').forEach(node => node.remove());
    }
    current.replaceChildren(...next.childNodes);
    for (const id of opened) {
      const detail = document.getElementById(id);
      if (detail?.tagName === 'DETAILS') detail.open = true;
    }
    if (submittedForm) dirtyForms.delete(submittedForm);
    // Preserve keyboard focus without moving the viewport; fall forward if a purchased row disappeared.
    if (focus && document.activeElement !== focus && focusedRow) {
      const target = document.querySelector(`[data-item-id="${CSS.escape(focusedRow)}"]`);
      const control = (focusedId && document.getElementById(focusedId)) ||
        (focusedName && target?.querySelector(`[name="${CSS.escape(focusedName)}"]`)) ||
        (focusedAction && target?.querySelector(`input[name="action"][value="${CSS.escape(focusedAction)}"]`)?.form?.querySelector('button')) ||
        target?.querySelector('button,a,input') ||
        (saved.id && document.querySelector(`[data-item-id="${CSS.escape(saved.id)}"] button`));
      control?.focus({preventScroll: true});
    }
    restoreAnchor(saved);
    window.dispatchEvent(new Event('james:content-updated'));
    return true;
  }

  const canRefresh = () => !!listPage() && !edited && !submitting && dirtyForms.size === 0 &&
    !(document.activeElement?.closest('main') && document.activeElement.matches('input,select,textarea')) &&
    !document.querySelector('main details[open]');
  async function refresh() {
    if (!canRefresh() || refreshing || !navigator.onLine) return false;
    refreshing = true;
    const ticket = generation;
    try {
      const response = await fetch(window.location.href, {cache: 'no-store', credentials: 'same-origin'});
      if (!response.ok || response.redirected || ticket !== generation || !canRefresh()) return false;
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (ticket !== generation || !canRefresh()) return false;
      return applyPage(page);
    } catch { return false; }
    finally { refreshing = false; }
  }
  window.JamesPage = {canRefresh, refresh};

  document.addEventListener('submit', async event => {
    const form = event.target;
    if (!isPost(form) || form.closest('.jayjay')) return;
    if (!navigator.onLine || submitting) { event.preventDefault(); return; }
    if (!actionForm(form)) {
      rememberPosition(); submitting = true; generation++;
      // Disabled submitters do not contribute their name/value to native form submission.
      if (event.submitter?.name) {
        const field = document.createElement('input');
        field.type = 'hidden'; field.name = event.submitter.name; field.value = event.submitter.value;
        form.append(field);
      }
      form.querySelectorAll('button[type="submit"]').forEach(button => { button.disabled = true; });
      return;
    }
    event.preventDefault();
    const data = new FormData(form);
    if (event.submitter?.name) data.set(event.submitter.name, event.submitter.value);
    const row = rowOf(form);
    const submittedRow = row?.dataset.itemId;
    const currentError = form.parentElement.querySelector('.inline-feedback');
    currentError?.remove();
    submitting = true; generation++;
    const controls = [...form.querySelectorAll('input,select,textarea')].map(control => [control, control.disabled]);
    controls.forEach(([control]) => { control.disabled = true; });
    form.setAttribute('aria-busy', 'true'); onlineState();
    let message;
    try {
      const response = await fetch(form.action, {method: 'POST', body: data, credentials: 'same-origin', cache: 'no-store'});
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (!response.ok) {
        message = page.querySelector('.notice--error, main p')?.textContent || 'Speichern nicht möglich. Bitte die Ansicht aktualisieren.';
      } else if (!applyPage(page, {submittedRow, submittedForm: form, notify: true})) {
        message = 'Bitte aktualisiere die Ansicht und prüfe den gespeicherten Stand. Deine Eingaben bleiben erhalten.';
      } else {
        const url = new URL(response.url);
        url.searchParams.delete('undo');
        window.history.replaceState(null, '', url.pathname + url.search);
        rememberPosition();
        window.dispatchEvent(new Event('james:household-changed'));
      }
    } catch {
      // The POST may have reached the server. Never replay it automatically.
      message = 'Die Bestätigung fehlt. Bitte aktualisiere die Ansicht und prüfe, ob die Änderung gespeichert wurde.';
    } finally {
      submitting = false;
      controls.forEach(([control, disabled]) => { control.disabled = disabled; });
      form.removeAttribute('aria-busy'); onlineState();
    }
    if (message) {
      const error = document.createElement('div');
      error.className = 'inline-feedback'; error.setAttribute('role', 'alert');
      error.textContent = message;
      const reload = document.createElement('a');
      reload.href = window.location.href; reload.className = 'button button--outline';
      reload.textContent = 'Ansicht aktualisieren'; error.append(reload);
      if (form.isConnected) form.after(error); else showFeedback(document, message);
    }
  });

  const barcodeTarget = document.querySelector('#barcode-target');
  if (barcodeTarget) {
    const newFields = document.querySelector('#new-item-fields');
    const updateTarget = () => { const existing = barcodeTarget.value !== 'new'; newFields.hidden = existing; newFields.disabled = existing; };
    barcodeTarget.addEventListener('change', updateTarget); updateTarget();
  }
  window.addEventListener('pageshow', () => { submitting = false; onlineState(); recallPosition(); });
  if (listPage()) {
    const backgroundRefresh = () => {
      if (document.visibilityState === 'visible' && !document.querySelector('#jayjay-dialog[open]') && !window.JamesChat?.hasPendingInput()) refresh();
    };
    window.setInterval(backgroundRefresh, 45000);
    document.addEventListener('visibilitychange', backgroundRefresh);
  }
  onlineState();
})();
