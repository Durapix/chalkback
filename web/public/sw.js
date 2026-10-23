// Chalkback service worker: shows lesson reminders sent by the server (Web Push).
self.addEventListener('push', (event) => {
  let data = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch {
    data = { body: event.data ? event.data.text() : '' }
  }
  const base = self.registration.scope
  event.waitUntil(
    self.registration.showNotification(data.title || 'Chalkback', {
      body: data.body || '',
      icon: base + 'icon-192.png',
      badge: base + 'favicon-32.png',
      data: { url: data.url || base },
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data && event.notification.data.url) || self.registration.scope
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
      for (const w of windows) {
        if (w.url === url && 'focus' in w) return w.focus()
      }
      return self.clients.openWindow(url)
    }),
  )
})
