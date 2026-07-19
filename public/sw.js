const CACHE = "shapez2-tmam-web-runtime-v3";
const CORE = [
  "/manifest.webmanifest",
  "/icon.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll(CORE))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  // Solver and proof assets keep stable public URLs, so always revalidate them.
  // The cached response is only an offline fallback, never the preferred copy.
  if (url.pathname === "/solver.worker.js" || url.pathname.startsWith("/data/")) {
    event.respondWith(
      fetch(event.request, { cache: "no-store" })
        .then((response) => {
          if (response.ok) void caches.open(CACHE).then((cache) => cache.put(event.request, response.clone()));
          return response;
        })
        .catch(() => caches.match(event.request).then((response) => response || Response.error())),
    );
    return;
  }

  // Never serve stale application HTML. A cached old index can reference chunks
  // from another release and leave the entire frontend broken.
  if (event.request.mode === "navigate" || event.request.destination === "document") {
    event.respondWith(
      fetch(event.request, { cache: "no-store" })
        .catch(() => caches.match("/"))
        .then((response) => response || Response.error()),
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        if (response.ok) {
          void caches.open(CACHE).then((cache) => cache.put(event.request, response.clone()));
        }
        return response;
      });
    }),
  );
});
