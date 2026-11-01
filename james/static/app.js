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

let edited = false;
let submitting = false;
document.addEventListener('input', () => { edited = true; });
function onlineState() {
  const offline = !navigator.onLine;
  document.querySelector('#offline-banner').hidden = !offline;
  document.querySelectorAll('form[method="post"] button[type="submit"]').forEach(button => {
    button.disabled = offline;
  });
}
window.addEventListener('online', onlineState);
window.addEventListener('offline', onlineState);
onlineState();
document.querySelectorAll('form[method="post"]').forEach(form => {
  form.addEventListener('submit', event => {
    if (!navigator.onLine || submitting) { event.preventDefault(); return; }
    submitting = true;
    // Disabled buttons are not successful form controls: preserve named actions.
    form.querySelectorAll('input[data-submit-value]').forEach(field => field.remove());
    if (event.submitter?.name) {
      const field = document.createElement('input');
      field.type = 'hidden';
      field.name = event.submitter.name;
      field.value = event.submitter.value;
      field.setAttribute('data-submit-value', '');
      form.appendChild(field);
    }
    form.querySelectorAll('button[type="submit"]').forEach(button => { button.disabled = true; });
  });
});

const barcodeTarget = document.querySelector('#barcode-target');
if (barcodeTarget) {
  const newFields = document.querySelector('#new-item-fields');
  const updateTarget = () => {
    const existing = barcodeTarget.value !== 'new';
    newFields.hidden = existing;
    newFields.disabled = existing;
  };
  barcodeTarget.addEventListener('change', updateTarget);
  updateTarget();
}
window.addEventListener('pageshow', event => {
  if (event.persisted) { submitting = false; onlineState(); }
});

// Never reload an invitation, a form, or a page with an unfinished quantity edit.
if (['/', '/shopping'].includes(window.location.pathname)) {
  const refresh = () => {
    if (document.visibilityState === 'visible' && navigator.onLine && !edited && !submitting && !document.querySelector('details[open]')) {
      window.location.reload();
    }
  };
  window.setInterval(refresh, 45000);
  document.addEventListener('visibilitychange', refresh);
}
