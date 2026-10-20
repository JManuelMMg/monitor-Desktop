/* Service worker: convierte el panel en una app instalable y muestra una
   pantalla propia cuando la Raspberry Pi no responde.

   - Navegación: red primero; si falla, la página /offline guardada.
   - /static: red primero con copia en caché (para la pantalla offline).
   - API, WebSocket y /healthz: nunca se interceptan ni se guardan. */
"use strict";

const CACHE = "monitor-v1";
const PRECACHE = [
    "/offline",
    "/static/css/app.css",
    "/static/js/common.js",
    "/static/js/netlink.js",
    "/static/js/offline.js",
    "/static/favicon.svg",
    "/static/icons/icon-192.png",
];

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys()
            .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
            .then(() => self.clients.claim()),
    );
});

self.addEventListener("fetch", (event) => {
    const request = event.request;
    if (request.method !== "GET") return;
    const url = new URL(request.url);
    if (url.origin !== self.location.origin) return;
    if (url.pathname.startsWith("/api/") || url.pathname === "/healthz" || url.pathname === "/ws") return;

    if (request.mode === "navigate") {
        event.respondWith(
            fetch(request).catch(async () => (await caches.match("/offline")) || Response.error()),
        );
        return;
    }

    if (url.pathname.startsWith("/static/")) {
        event.respondWith(
            fetch(request)
                .then((response) => {
                    if (response.ok) {
                        const copy = response.clone();
                        caches.open(CACHE).then(cache => cache.put(request, copy));
                    }
                    return response;
                })
                .catch(async () => (await caches.match(request)) || Response.error()),
        );
    }
});
