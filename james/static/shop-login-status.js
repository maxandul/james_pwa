// Read-only status polling. Never reload over user input or replay a POST.
(() => {
  const watch = document.querySelector('#shop-login-watch');
  if (!watch) return;
  let edited = false;
  document.addEventListener('input', () => { edited = true; }, {once: true});
  document.addEventListener('change', () => { edited = true; }, {once: true});
  document.addEventListener('submit', () => { edited = true; }, {once: true});
  async function poll() {
    if (edited) return;
    if (!document.hidden && navigator.onLine) {
      try {
        const response = await fetch(watch.dataset.statusUrl, {cache: 'no-store', credentials: 'same-origin'});
        if (!response.ok || response.redirected) return;
        const status = await response.json();
        if (edited) return;
        if (status.state !== watch.dataset.state || status.progress !== watch.dataset.progress) {
          window.location.reload();
          return;
        }
      } catch { /* A transient read failure is retried; writes never are. */ }
    }
    window.setTimeout(poll, 3000);
  }
  window.setTimeout(poll, 3000);
})();
