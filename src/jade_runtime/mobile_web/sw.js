/* Network-only PWA installation worker. No caches of Jade's identity,
 * tokens, conversations, audio, Live2D SDK or model resources. */
"use strict";
self.addEventListener("install", () => { self.skipWaiting(); });
self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});
// The fetch handler supports installability checks without offline caching.
// All authorization checks and model allowlists remain in the Python server.
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  event.respondWith(fetch(event.request, {cache: "no-store"}));
});
