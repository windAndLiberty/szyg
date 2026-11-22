import { translateCurrent } from './i18n'

/**
 * 工作现场完成的导航提示(绿点)。
 *
 * 规则:
 *  - 只有「工作现场任务完成」时打点,普通页面不显示绿点(替换原 implemented 标记);
 *  - 用户只要进入过(点击过)对应页面,绿点自动消失;
 *  - 任务完成时用户正停留在该页面,视为已读,不产生提示。
 */
const STORAGE_KEY = 'szyg.nav.work-done'
export function workIndicatorsEnabled(): boolean {
  return localStorage.getItem('szyg.work-indicators') !== 'off'
}

export function setWorkIndicators(enabled: boolean) {
  localStorage.setItem('szyg.work-indicators', enabled ? 'on' : 'off')
  if (!enabled) persist({})
}

export function desktopAlertsEnabled(): boolean {
  return localStorage.getItem('szyg.desktop-alerts') === 'on'
}

export function setDesktopAlerts(enabled: boolean) {
  localStorage.setItem('szyg.desktop-alerts', enabled ? 'on' : 'off')
}

const CHANGE_EVENT = 'szyg:nav-work-done-changed'

export type WorkDoneNotice = Record<string, number>

export function getWorkDoneNotices(): WorkDoneNotice {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') as WorkDoneNotice
  } catch {
    return {}
  }
}

function persist(notices: WorkDoneNotice) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(notices))
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new CustomEvent(CHANGE_EVENT))
}

/** 工作现场任务完成时调用。若用户正停留在此页面,视为已读,不显示提示。 */
export function notifyWorkDone(navPath: string) {
  const { pathname } = window.location
  if ((pathname !== navPath || document.hidden) && desktopAlertsEnabled() &&
      'Notification' in window && Notification.permission === 'granted') {
    try { new Notification(translateCurrent('任务执行完成'), { tag: navPath }) } catch { /* Navigation indicators remain available. */ }
  }
  if (pathname === navPath || !workIndicatorsEnabled()) return
  const notices = getWorkDoneNotices()
  notices[navPath] = Date.now()
  persist(notices)
}

/** 用户进入过对应页面后清除提示。 */
export function clearWorkDone(navPath: string) {
  const notices = getWorkDoneNotices()
  if (!(navPath in notices)) return
  delete notices[navPath]
  persist(notices)
}

/** Sidebar 订阅此事件以实时刷新绿点。 */
export { CHANGE_EVENT as WORK_DONE_CHANGE_EVENT }