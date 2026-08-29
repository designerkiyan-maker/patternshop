/* Service Worker پنل ادمین فروشگاه الگو - فقط برای دریافت اعلان Push و باز کردن
   پنل با کلیک روی اعلان. هیچ کش/آفلاینی پیاده نمی‌شود (پس نیازی به
   به‌روزرسانی لیست فایل‌های کش هم نیست). */

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: 'پنل فروشگاه الگو', body: event.data ? event.data.text() : '' };
  }
  const title = data.title || 'پنل فروشگاه الگو';
  const options = {
    body: data.body || '',
    tag: data.tag || undefined,
    renotify: !!data.tag,
    data: { url: data.url || '/' },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientsArr) => {
      const existing = clientsArr.find((c) => c.url.indexOf(self.registration.scope) === 0);
      if (existing) {
        existing.focus();
        return;
      }
      return self.clients.openWindow(targetUrl);
    })
  );
});
