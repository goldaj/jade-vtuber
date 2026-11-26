/* Jade PWA worker: network-only for private app data.
 * Push events are OS-driven. No persistent microphone, LLM loop or credentials.
 * Payload contains only an opaque reminder ID, not the reminder's private text.
 */
"use strict";
self.addEventListener("install", () => { self.skipWaiting(); });
self.addEventListener("activate", event => {
  event.waitUntil(self.clients.claim());
});
self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  event.respondWith(fetch(event.request, {cache:"no-store"}));
});
self.addEventListener("push", event => {
  let payload = {};
  try { payload = event.data ? event.data.json() : {}; } catch (_) { /* generic fallback */ }
  const id = typeof payload.id === "string" && /^[0-9a-f]{24}$/.test(payload.id)
    ? payload.id : null;
  event.waitUntil(self.registration.showNotification("Jade · Rappel", {
    body:"Jade a un rappel pour toi.",
    icon:"/icon-192.png",
    badge:"/icon-192.png",
    tag:id ? "jade-reminder-" + id : "jade-reminder",
    renotify:false,
    data:{id},
  }));
});
self.addEventListener("notificationclick", event => {
  event.notification.close();
  const id = event.notification.data && event.notification.data.id;
  const valid = typeof id === "string" && /^[0-9a-f]{24}$/.test(id);
  const target = valid ? "/#reminder-" + id : "/";
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({type:"window", includeUncontrolled:true});
    const existing = windows.find(client => client.url.startsWith(self.registration.scope));
    if (existing) {
      await existing.focus();
      if (valid) existing.postMessage({type:"jade-open-reminder", id});
      return;
    }
    await self.clients.openWindow(target);
  })());
});
