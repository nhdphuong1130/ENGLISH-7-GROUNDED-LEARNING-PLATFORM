const CACHE_NAME = 'english7-shell-v1';
const APP_SHELL = [
  '/app/',
  '/app/flutter_bootstrap.js',
  '/app/manifest.json',
  '/app/icons/Icon-192.png',
  '/app/icons/Icon-512.png',
  '/app/icons/Icon-maskable-192.png',
  '/app/icons/Icon-maskable-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys
        .filter((key) => key.startsWith('english7-shell-') && key !== CACHE_NAME)
        .map((key) => caches.delete(key)),
    )),
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/')) {
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => caches.match('/app/')),
    );
    return;
  }

  if (request.method === 'GET' && url.pathname.startsWith('/app/')) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request)),
    );
  }
});
