import { logoutCloud } from '@/lib/api'

/** A local sign-out still applies if the desktop broker was unreachable. */
export const CLOUD_SIGNED_OUT_KEY = 'szyg.cloud.signed-out'
export const CLOUD_LOGOUT_EVENT = 'szyg:cloud-logout'

export function finishCloudLogout() {
  localStorage.setItem(CLOUD_SIGNED_OUT_KEY, '1')
  localStorage.removeItem('szyg.cloud.keep-login')
  window.dispatchEvent(new Event(CLOUD_LOGOUT_EVENT))
}

export async function logoutCloudSession() {
  try {
    await logoutCloud()
  } finally {
    finishCloudLogout()
  }
}
