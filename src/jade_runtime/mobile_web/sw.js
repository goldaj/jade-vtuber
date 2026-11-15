/* Installable PWA without caching model assets, private audio or messages.
   A service worker is NOT a place to persist Jade's bearer token. */
self.addEventListener("install", () => { self.skipWaiting(); });
self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});
