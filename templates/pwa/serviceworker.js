/**
 * Service Worker para IESETyFP - Proyecto Zunin (PWA)
 * Soporta funcionamiento de app instalable, caché de assets y resiliencia offline.
 */

const CACHE_NAME = 'zunin-pwa-v1';
const STATIC_ASSETS = [
  '/',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon.svg',
  'https://cdn.tailwindcss.com',
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap'
];

// Instalación del Service Worker y precaching de assets esenciales
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('[PWA ServiceWorker] Fallo al precachear algunos assets:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// Activación y limpieza de cachés anteriores
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            return caches.delete(cache);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Estrategia Network-First con fallback a Caché para navegación y contenido dinámico
self.addEventListener('fetch', (event) => {
  const request = event.request;

  // Solo interceptar peticiones GET
  if (request.method !== 'GET') {
    return;
  }

  // Ignorar llamadas a admin o APIs no idempotentes si aplica
  if (request.url.includes('/admin/')) {
    return;
  }

  event.respondWith(
    fetch(request)
      .then((networkResponse) => {
        // Si la respuesta es válida, clonar en caché
        if (networkResponse && networkResponse.status === 200) {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, responseToCache);
          });
        }
        return networkResponse;
      })
      .catch(() => {
        // Si no hay red, recuperar desde caché
        return caches.match(request).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }
          // Si es una navegación HTML y no hay red ni caché
          if (request.headers.get('accept') && request.headers.get('accept').includes('text/html')) {
            return caches.match('/');
          }
        });
      })
  );
});
