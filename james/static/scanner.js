'use strict';

(() => {
  const form = document.querySelector('#scan-form');
  if (!form) return;
  const input = document.querySelector('#barcode-input');
  const video = document.querySelector('#barcode-video');
  const preview = document.querySelector('#camera-preview');
  const start = document.querySelector('#camera-start');
  const stop = document.querySelector('#camera-stop');
  const status = document.querySelector('#camera-status');
  let stream = null;
  let timer = null;
  let generation = 0;
  let starting = false;

  function stopCamera(message) {
    generation += 1;
    window.clearTimeout(timer);
    timer = null;
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null;
    video.pause();
    video.srcObject = null;
    preview.hidden = true;
    start.disabled = false;
    stop.hidden = true;
    starting = false;
    if (message) status.textContent = message;
  }

  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !('BarcodeDetector' in window)) {
    start.hidden = true;
    status.textContent = 'Dein Browser unterstützt den Kamerascan hier nicht. Bitte die Nummer eingeben. Auf dem Handy wird HTTPS benötigt.';
    return;
  }

  start.addEventListener('click', async () => {
    if (starting || stream) return;
    starting = true;
    start.disabled = true;
    stop.hidden = false;
    const session = ++generation;
    status.textContent = 'Kamera wird vorbereitet. Bitte den Zugriff im Browser erlauben.';
    try {
      const supported = await BarcodeDetector.getSupportedFormats();
      const formats = ['ean_13', 'ean_8', 'upc_a', 'itf'].filter(format => supported.includes(format));
      if (session !== generation) return;
      if (!formats.length) throw new Error('unsupported');
      const detector = new BarcodeDetector({ formats });
      const camera = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
      if (session !== generation) { camera.getTracks().forEach(track => track.stop()); return; }
      stream = camera;
      video.srcObject = stream;
      preview.hidden = false;
      await video.play();
      if (session !== generation) return;
      starting = false;
      status.textContent = 'Halte den Barcode ruhig in die Kamera. Die Artikelsuche startet nach dem Erkennen automatisch.';
      const detect = async () => {
        if (session !== generation || !stream) return;
        try {
          const found = await detector.detect(video);
          if (session !== generation) return;
          const result = found.find(value => /^[0-9]{8}$|^[0-9]{12,14}$/.test(value.rawValue)
            && (value.format !== 'itf' || value.rawValue.length === 14));
          if (result) {
            input.value = result.rawValue;
            stopCamera('Barcode erkannt. Artikel wird gesucht.');
            form.requestSubmit();
            return;
          }
        } catch {
          stopCamera('Der Barcode konnte nicht gelesen werden. Bitte erneut starten oder die Nummer eingeben.');
          return;
        }
        if (session === generation) timer = window.setTimeout(detect, 200);
      };
      detect();
    } catch (error) {
      if (session !== generation) return;
      const denied = error.name === 'NotAllowedError';
      stopCamera(denied ? 'Der Kamerazugriff wurde nicht erlaubt. Du kannst die Nummer eingeben oder die Kamera später erneut starten.' : 'Die Kamera ist hier gerade nicht verfügbar. Bitte die Nummer eingeben.');
    }
  });
  stop.addEventListener('click', () => stopCamera('Kamera gestoppt. Du kannst die Nummer auch eingeben.'));
  form.addEventListener('submit', () => stopCamera());
  window.addEventListener('pagehide', () => stopCamera());
  window.addEventListener('offline', () => stopCamera('Keine Verbindung. Bitte später erneut versuchen.'));
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') stopCamera('Kamera pausiert. Zum Weiterscannen erneut starten.');
  });
})();
