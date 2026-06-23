// Minimal service worker. Its only job is to make the page installable as a
// PWA (a prerequisite for the Android "share target"). It does not cache or
// intercept anything -- the share POST goes straight to the /share route on
// the server.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
