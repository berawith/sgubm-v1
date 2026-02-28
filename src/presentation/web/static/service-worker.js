const CACHE_NAME = 'sgub-pro-cache-v1';
const STATIC_ASSETS = [
    '/',
    '/static/manifest.json',
    '/static/vendor/css/inter.css',
    '/static/vendor/css/all.min.css',
    '/static/vendor/js/socket.io.min.js',
    '/static/vendor/js/chart.min.js',
    '/static/css/clients-mobile.css',
    '/static/css/payments-mobile.css',
    '/static/dist/bundle.css',
    '/static/dist/bundle.js'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[Service Worker] Caching static assets');
            return cache.addAll(STATIC_ASSETS);
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('[Service Worker] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    // Solo interceptar peticiones GET (no mutaciones a la API)
    if (event.request.method !== 'GET') return;

    // Estrategia Network First, fallback to cache
    event.respondWith(
        fetch(event.request)
            .then((networkResponse) => {
                // Si recibimos una respuesta buena, la guardamos en cache (para paginas estaticas)
                if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
                    const responseToCache = networkResponse.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseToCache);
                    });
                }
                return networkResponse;
            })
            .catch(() => {
                // En caso de que falle la red, buscamos en cache
                console.warn(`[Service Worker] Network request failed, returning cached version for: ${event.request.url}`);
                return caches.match(event.request);
            })
    );
});
