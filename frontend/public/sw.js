// Dev stub — @ducanh2912/next-pwa disables SW generation in development,
// but browsers may still request /sw.js from a prior production install.
// Production builds overwrite this file with the real Workbox service worker.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});
