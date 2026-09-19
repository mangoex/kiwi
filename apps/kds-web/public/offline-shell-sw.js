const CACHE_NAME = 'restaurantos-kds-shell-v2';
const SHELL = ['/kds/', '/kds/index.html'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('message', (event) => {
  if (event.data?.type !== 'PRECACHE_ASSETS' || !Array.isArray(event.data.urls)) return;
  const assets = event.data.urls.filter((value) => {
    try {
      const url = new URL(value, self.location.origin);
      return url.origin === self.location.origin && url.pathname.startsWith('/kds/assets/') && !url.search && !url.hash;
    } catch { return false; }
  });
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(assets)));
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  const isStaticAsset = request.mode === 'navigate'
    || ['script', 'style', 'image', 'font'].includes(request.destination);
  if (
    request.method !== 'GET'
    || url.origin !== self.location.origin
    || url.pathname.includes('/api/')
    || request.headers.has('Authorization')
    || !isStaticAsset
  ) return;

  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    if (request.mode === 'navigate') {
      if (!url.pathname.startsWith('/kds/')) return fetch(request);
      try {
        const response = await fetch(request);
        if (response.ok) await cache.put('/kds/index.html', response.clone());
        return response;
      } catch {
        const shell = await cache.match('/kds/index.html', { ignoreVary: true });
        if (shell) return shell;
        throw new Error('offline_shell_unavailable');
      }
    }
    const cached = await cache.match(request, { ignoreVary: true });
    if (cached) return cached;
    const response = await fetch(request);
    if (response.ok) {
      await cache.put(request, response.clone());
    }
    return response;
  })());
});
