/* KPI-MS service worker — پوسته رابط کاربری را کش می‌کند تا سامانه پس از
   قطع شبکه هم باز شود؛ داده‌ها همیشه از سرور (API) خوانده می‌شوند و هرگز
   از کش پاسخ داده نمی‌شوند. */
const CACHE = "kpi-shell-v1.1.0";
const SHELL = [
  "/",
  "/static/app.js",
  "/static/styles.css",
  "/vendor/react.js",
  "/vendor/react-dom.js",
  "/vendor/htm.js",
  "/vendor/chart.umd.js",
  "/manifest.webmanifest",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png"
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  // API و مستندات: شبکه‌محور، هرگز کش نشود
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/docs") ||
      url.pathname.startsWith("/openapi")) return;
  // ناوبری SPA: ابتدا شبکه، در صورت قطعی از کش
  if (req.mode === "navigate") {
    e.respondWith(fetch(req).catch(() => caches.match("/")));
    return;
  }
  e.respondWith(
    caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
      return res;
    }))
  );
});
