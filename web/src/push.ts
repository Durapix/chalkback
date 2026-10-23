// Browser side of Web Push: register the service worker and (un)subscribe this device.
import { api } from './api'

export type PushState = 'unsupported' | 'needs-install' | 'blocked' | 'off' | 'on'

const supported = () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window

// iPhone and iPad only allow notifications for sites added to the home screen.
const isIos = () => /iPad|iPhone|iPod/.test(navigator.userAgent)
const isInstalled = () =>
  window.matchMedia('(display-mode: standalone)').matches ||
  (navigator as Navigator & { standalone?: boolean }).standalone === true

// Bump when public/sw.js changes. A new URL also sidesteps any copy a CDN cached earlier.
const SW_VERSION = 2

async function registration() {
  return navigator.serviceWorker.register(`${import.meta.env.BASE_URL}sw.js?v=${SW_VERSION}`, {
    scope: import.meta.env.BASE_URL,
  })
}

function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const base64 = (base64url + '='.repeat((4 - (base64url.length % 4)) % 4))
    .replace(/-/g, '+')
    .replace(/_/g, '/')
  const raw = atob(base64)
  const bytes = new Uint8Array(new ArrayBuffer(raw.length))
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)
  return bytes
}

export async function pushState(): Promise<PushState> {
  if (!supported()) return isIos() && !isInstalled() ? 'needs-install' : 'unsupported'
  if (Notification.permission === 'denied') return 'blocked'
  const reg = await navigator.serviceWorker.getRegistration(import.meta.env.BASE_URL)
  const sub = await reg?.pushManager.getSubscription()
  return sub && Notification.permission === 'granted' ? 'on' : 'off'
}

export async function enablePush(): Promise<PushState> {
  if ((await Notification.requestPermission()) !== 'granted') return pushState()
  const reg = await registration()
  await navigator.serviceWorker.ready
  const { public_key } = await api.pushKey()
  const sub =
    (await reg.pushManager.getSubscription()) ??
    (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(public_key) }))
  const json = sub.toJSON() as { endpoint: string; keys: { p256dh: string; auth: string } }
  await api.pushSubscribe({ endpoint: json.endpoint, keys: json.keys })
  return 'on'
}

export async function disablePush(): Promise<PushState> {
  const reg = await navigator.serviceWorker.getRegistration(import.meta.env.BASE_URL)
  const sub = await reg?.pushManager.getSubscription()
  if (sub) {
    await api.pushUnsubscribe(sub.endpoint)
    await sub.unsubscribe()
  }
  return 'off'
}
