/**
 * 工作现场完成的导航提示(绿点)。
 *
 * 规则:
 *  - 只有「工作现场任务完成」时打点,普通页面不显示绿点(替换原 implemented 标记);
 *  - 用户只要进入过(点击过)对应页面,绿点自动消失;
 *  - 任务完成时用户正停留在该页面,视为已读,不产生提示。
 */
const STORAGE_KEY = 'szyg.nav.work-done'
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
  if (pathname === navPath) return
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