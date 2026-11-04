/**
 * Service Worker para IESETyFP - Proyecto Zunin (PWA)
 * Soporta funcionamiento de app instalable, caché de assets estáticos y resiliencia.
 */

const CACHE_NAME = 'zunin-pwa-v1';
const STATIC_ASSETS = [
  '/manifest.json',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon.svg',
  'https://cdn.tailwindcss.com',
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap'
];

// Instalación del Service Worker y precaching exclusivo de assets estáticos
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('[PWA ServiceWorker] Fallo al precachear algunos assets estáticos:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// Activación y limpieza profunda de cachés obsoletas y respuestas dinámicas previas
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      // Eliminar explícitamente cualquier entrada previa de '/' para evitar secuestro de navegación
      return cache.delete('/').then(() => {
        return caches.keys().then((cacheNames) => {
          return Promise.all(
            cacheNames.map((cacheName) => {
              if (cacheName !== CACHE_NAME) {
                return caches.delete(cacheName);
              }
            })
          );
        });
      });
    }).then(() => self.clients.claim())
  );
});

// Estrategia de Fetch:
// Las rutas dinámicas de Django, búsquedas, filtros y navegación HTML van DIRECTO a la red (Bypass / Network Only).
// Solo los archivos estáticos (imágenes, CSS, fuentes, manifiesto) son gestionados por la caché.
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Solo interceptar peticiones GET
  if (request.method !== 'GET') {
    return;
  }

  // 1. Si es navegación HTML, petición con parámetros de consulta (?q=, ?fecha=),
  // o cualquier ruta de vista dinámica de Django: NO interceptar.
  // Dejar que el navegador realice la petición de red normal.
  const isNavigation = request.mode === 'navigate';
  const isHTML = request.headers.get('accept') && request.headers.get('accept').includes('text/html');
  const isDjangoView = (
    url.pathname.startsWith('/personal') ||
    url.pathname.startsWith('/asistencia') ||
    url.pathname.startsWith('/licencias') ||
    url.pathname.startsWith('/admin') ||
    url.pathname.startsWith('/accounts') ||
    url.pathname.startsWith('/api') ||
    url.pathname === '/' ||
    url.pathname === '/dashboard' ||
    url.pathname === '/dashboard/'
  );

  if (isNavigation || isHTML || isDjangoView || url.search) {
    return;
  }

  // 2. Para recursos estáticos puros (/static/, iconos, Tailwind, Google Fonts):
  // Estrategia Cache-First con actualización en caché
  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, responseToCache);
          });
        }
        return networkResponse;
      }).catch((err) => {
        console.warn('[PWA ServiceWorker] Error de red al solicitar recurso estático:', err);
      });
    })
  );
});
