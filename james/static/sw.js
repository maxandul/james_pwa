'use strict';
const CACHE = 'james-shell-v9';
const FILES = ['/offline', '/static/app.css?v=13', '/static/css/tokens.css?v=13','/static/css/base.css?v=13','/static/css/layout.css?v=13','/static/css/components.css?v=13','/static/css/pages.css?v=13','/static/css/jayjay.css?v=13', '/static/css/settings.css?v=13', '/static/offline-store.js?v=1',
  '/static/pwa.js?v=4', '/static/icon-192.png', '/static/icon-512.png', '/manifest.webmanifest'];
const STATIC = new Set(FILES.filter(path => path !== '/offline'));

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(FILES.map(path =>
    new Request(new URL(path, self.location.origin), { credentials: 'omit' })))));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key =>
    key.startsWith('james-shell-') && key !== CACHE).map(key => caches.delete(key))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  const path = url.pathname + url.search;
  if (STATIC.has(path)) {
    event.respondWith(caches.match(path).then(cached => cached || fetch(request)));
  } else if (request.mode === 'navigate' && ['/', '/shopping', '/offline'].includes(url.pathname)) {
    // Never cache a live authenticated page, API response or write request.
    event.respondWith(fetch(request).catch(() => caches.match('/offline')));
  }
});
