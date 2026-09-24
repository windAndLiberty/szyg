import { logoutCloud } from '@/lib/api'

/** Browser-side state which controls whether the local desktop session may run offline. */
export const CLOUD_KEEP_LOGIN_KEY = 'szyg.cloud.keep-login'
export const CLOUD_LOGOUT_EVENT = 'szyg:cloud-logout'

/**
 * Remove the browser's offline-login marker and tell the authentication gate to
 * return to the sign-in screen immediately. The backend logout endpoint clears
 * the encrypted refresh token separately.
 */
export function finishCloudLogout() {
  localStorage.removeItem(CLOUD_KEEP_LOGIN_KEY)
  window.dispatchEvent(new Event(CLOUD_LOGOUT_EVENT))
}

/**
 * End the local desktop session even if the network request cannot complete.
 * The backend clears its encrypted refresh token before returning success; the
 * finally block makes the visible app return to the sign-in page immediately.
 */
export async function logoutCloudSession() {
  try {
    await logoutCloud()
  } finally {
    finishCloudLogout()
  }
}
